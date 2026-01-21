# cache_api.py
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/cache", tags=["cache"])


# =========================================================
# Path resolution (IMPORTANT)
# =========================================================
def _find_cache_file() -> Path:
    """
    cache_api.py の置き場所がどこでも、
    backend/data/cache/company_cache_all.json をなるべく確実に見つける。
    """
    here = Path(__file__).resolve()

    # 1) まず「このファイルの近く」を上に辿って data/cache を探す
    for p in [here.parent, *here.parents]:
        cand = p / "data" / "company_cache_all.json"
        if cand.exists():
            return cand

    # 2) 最後にフォールバック（存在しない可能性もあるが meta で確認できる）
    return here.parent / "data" / "company_cache_all.json"


ALL_CACHE_PATH = _find_cache_file()


# =========================================================
# helpers: normalization
# =========================================================
_SPACE_RE = re.compile(r"\s+", re.UNICODE)

# ゼロ幅・BOM など「見えないけど一致を壊す」文字
_ZERO_WIDTH = ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"]

# いろんなハイフン/マイナスを統一
_DASHES = {
    "－": "-",
    "−": "-",
    "‐": "-",
    "-": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
}


def _norm_name(s: str, *, remove_inner_spaces: bool = True) -> str:
    """
    会社名の表記ゆれ吸収（強化版）
    - Unicode正規化(NFKC)
    - ゼロ幅/BOM除去
    - 全角空白 -> 半角
    - 連続空白
    - ハイフン類統一
    - (option) 内部空白削除
    """
    s = s or ""
    if not s:
        return ""

    # Unicode正規化（全角英数や記号の揺れに強い）
    s = unicodedata.normalize("NFKC", s)

    # ゼロ幅/BOMなど除去
    for z in _ZERO_WIDTH:
        s = s.replace(z, "")

    # 全角空白→半角
    s = s.replace("\u3000", " ").strip()
    if not s:
        return ""

    # ハイフン/マイナス統一
    for a, b in _DASHES.items():
        s = s.replace(a, b)

    # 空白処理
    if remove_inner_spaces:
        s = _SPACE_RE.sub("", s)
    else:
        s = _SPACE_RE.sub(" ", s)

    return s


def _load_all_cache_or_raise() -> Dict[str, Any]:
    """
    キャッシュを読み込み。ない/壊れてる場合は明確にHTTPエラー。
    """
    if not ALL_CACHE_PATH.exists():
        raise HTTPException(status_code=404, detail=f"cache file not found: {ALL_CACHE_PATH}")

    try:
        with ALL_CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=503, detail="cache file is corrupted (json decode error)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"cache read error: {e}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="cache format invalid (root is not dict)")

    return data


def _get_companies_map(data: Dict[str, Any]) -> Dict[str, Any]:
    comps = data.get("companies")
    return comps if isinstance(comps, dict) else {}


def _get_company_names(data: Dict[str, Any]) -> List[str]:
    """
    company_names が無い/壊れてる場合でも companies から復元。
    """
    names_raw = data.get("company_names")
    if isinstance(names_raw, list) and names_raw:
        names = [str(x).strip() for x in names_raw if str(x).strip()]
    else:
        comps = _get_companies_map(data)
        names = [str(k).strip() for k in comps.keys() if str(k).strip()]

    return sorted(set(names))


def _best_candidates(nkey: str, keys: List[str], limit: int = 20) -> List[str]:
    """
    debug 用：候補を「近い順っぽく」返す（簡易スコア）
    """
    scored: List[Tuple[int, str]] = []
    for k in keys:
        nk = _norm_name(k)
        if not nk:
            continue

        score = 9999
        if nkey == nk:
            score = 0
        elif nk.startswith(nkey) or nkey.startswith(nk):
            score = 10 + abs(len(nk) - len(nkey))
        elif nkey in nk or nk in nkey:
            score = 50 + abs(len(nk) - len(nkey))
        else:
            score = 200 + abs(len(nk) - len(nkey))

        scored.append((score, k))

    scored.sort(key=lambda x: x[0])
    return [k for _, k in scored[:limit]]


# =========================================================
# ✅ normalized index cache (speed-up)
#  - companies のキーを毎回 for で回すと遅いので、
#    「正規化名 → 元キー」をメモ化して高速化
#  - company_cache_all.json が更新されたら自動再構築
# =========================================================
_norm_index: Dict[str, str] = {}         # normalized -> original_key
_last_mtime_ns: Optional[int] = None     # file mtime to detect update


def _ensure_norm_index(comps: Dict[str, Any]) -> None:
    global _norm_index, _last_mtime_ns

    try:
        mtime_ns = ALL_CACHE_PATH.stat().st_mtime_ns
    except Exception:
        mtime_ns = None

    # 初回 or ファイル更新されたら再構築
    if _last_mtime_ns != mtime_ns or not _norm_index:
        idx: Dict[str, str] = {}
        for k in comps.keys():
            nk = _norm_name(str(k))
            if nk and nk not in idx:
                idx[nk] = str(k)
        _norm_index = idx
        _last_mtime_ns = mtime_ns


def _lookup_company(comps: Dict[str, Any], raw: str) -> Tuple[Optional[Any], str]:
    """
    会社名 raw を comps から探す。
    戻り値: (value or None, normalized_key)
    """
    # 1) 完全一致
    if raw in comps:
        return comps[raw], _norm_name(raw)

    # 2) 正規化一致（indexを使用）
    nkey = _norm_name(raw)
    if not nkey:
        return None, ""

    _ensure_norm_index(comps)
    original = _norm_index.get(nkey)
    if original is not None and original in comps:
        return comps[original], nkey

    return None, nkey


# =========================================================
# endpoints
# =========================================================
@router.get("/meta")
def get_cache_meta():
    data = _load_all_cache_or_raise()
    meta = data.get("meta")
    meta_out = dict(meta) if isinstance(meta, dict) else {}

    # デバッグしやすく
    meta_out["cache_path"] = str(ALL_CACHE_PATH)
    meta_out["cache_exists"] = ALL_CACHE_PATH.exists()
    meta_out["cache_size_bytes"] = ALL_CACHE_PATH.stat().st_size if ALL_CACHE_PATH.exists() else 0
    meta_out["has_companies"] = isinstance(data.get("companies"), dict)
    meta_out["company_names_count"] = len(_get_company_names(data))
    return meta_out


@router.get("/companies")
def list_company_names(limit: int = Query(200, ge=1, le=5000)):
    data = _load_all_cache_or_raise()
    names = _get_company_names(data)
    return {"companies": names[:limit], "count": len(names)}


# ---------------------------------------------------------
# ✅ GET: 互換用（残してOK）
# ---------------------------------------------------------
@router.get("/company")
def get_company_cache(
    name: str = Query(..., description="企業名（完全一致推奨）"),
    debug: bool = Query(False, description="見つからない時に候補を返す"),
):
    data = _load_all_cache_or_raise()
    comps = _get_companies_map(data)

    raw = (name or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="name is empty")

    found, nkey = _lookup_company(comps, raw)
    if found is not None:
        return found

    if debug:
        keys = [str(k) for k in comps.keys()]
        cands = _best_candidates(nkey, keys, limit=20)
        return JSONResponse(
            status_code=404,
            content={
                "detail": "company not found",
                "requested": raw,
                "normalized": nkey,
                "cache_path": str(ALL_CACHE_PATH),
                "candidates": cands,
            },
        )

    raise HTTPException(status_code=404, detail="company not found")


# ---------------------------------------------------------
# ✅ POST: 推奨（フロントはこっち）
# ---------------------------------------------------------
@router.post("/company")
def post_company_cache(payload: Dict[str, Any]):
    """
    body: { "name": "北海道コカ・コーラ株式会社", "debug": true }

    ✅ 返り値仕様
    - ヒット: 企業データ(dict) をそのまま返す（従来互換）
    - ミス: 200 で {"found": false, ...} を返す（404を出さない）
    """
    data = _load_all_cache_or_raise()
    comps = _get_companies_map(data)

    raw = str(payload.get("name") or "").strip()
    debug = bool(payload.get("debug") or False)

    if not raw:
        # 入力ミスは 400 のままでOK
        raise HTTPException(status_code=400, detail="name is empty")

    found, nkey = _lookup_company(comps, raw)
    if found is not None:
        # ✅ 従来通りそのまま返す（フロントの既存実装を壊しにくい）
        return found

    # ✅ 404 を返さない：キャッシュミスは「正常系」
    out: Dict[str, Any] = {
        "found": False,
        "detail": "company not found",
        "requested": raw,
        "normalized": nkey,
        "cache_path": str(ALL_CACHE_PATH),
    }

    if debug:
        keys = [str(k) for k in comps.keys()]
        out["candidates"] = _best_candidates(nkey, keys, limit=20)

    return out


@router.get("/search")
def search_company_names(
    q: str = Query(..., description="部分一致検索キーワード"),
    limit: int = Query(15, ge=1, le=200),
):
    """
    サジェスト用：prefix優先→contains
    - q は正規化（空白除去/Unicode正規化）して照合
    """
    data = _load_all_cache_or_raise()
    names = _get_company_names(data)

    kw_raw = (q or "").strip()
    if not kw_raw:
        return {"candidates": [], "count": 0}

    kw = _norm_name(kw_raw)

    # 正規化インデックス（names用）
    norm_index: Dict[str, str] = {}
    for n in names:
        nk = _norm_name(n)
        if nk and nk not in norm_index:
            norm_index[nk] = n

    prefix: List[str] = []
    contain: List[str] = []

    for nk, original in norm_index.items():
        if nk.startswith(kw):
            prefix.append(original)
        elif kw in nk:
            contain.append(original)

    out = (prefix + contain)[:limit]
    return {"candidates": out, "count": len(out)}
