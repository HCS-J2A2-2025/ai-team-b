from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache_api import router as cache_router

# =========================================================
# FastAPI
# =========================================================
app = FastAPI()

# ✅ 本番IPアクセスも想定するならここを増やす（例: 10.11.33.225:3000 など）
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    # "http://10.11.33.225:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# フロントは /api/cache/company を叩く前提
app.include_router(cache_router, prefix="/api/cache", tags=["cache"])

# =========================================================
# Patterns / Normalizers
# =========================================================
_CORP_PATTERNS = [
    r"株式会社", r"（株）", r"\(株\)", r"㈱",
    r"有限会社", r"（有）", r"\(有\)", r"㈲",
    r"合同会社",
    r"合資会社", r"合名会社",
    r"一般社団法人", r"一般財団法人", r"公益社団法人", r"公益財団法人",
    r"医療法人", r"学校法人", r"社会福祉法人", r"宗教法人",
]
_CORP_RE = re.compile("|".join(_CORP_PATTERNS))

def detect_corp_kind(s: str) -> str:
    """クエリが「有限会社」指定か「株式会社」指定かを判定。"""
    s = s or ""
    if re.search(r"(有限会社|㈲|\(有\)|（有）)", s):
        return "YK"  # 有限会社
    if re.search(r"(株式会社|㈱|\(株\)|（株）)", s):
        return "KK"  # 株式会社
    return ""       # 指定なし

def normalize_company_key(name: str) -> str:
    """同一判定用キー（法人格差は吸収）。"""
    if not name:
        return ""
    s = str(name)

    # 空白除去
    s = s.strip().replace("　", "")
    s = re.sub(r"\s+", "", s)

    # 全角英数→半角
    trans = str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    s = s.translate(trans)

    # 記号ゆれ統一
    s = s.replace("−", "-").replace("ー", "-").replace("―", "-").replace("‐", "-")
    s = s.replace("･", "・")

    # かっこ類除去
    s = re.sub(r"[()（）【】\[\]{}<>＜＞「」『』]", "", s)

    # 法人格を除去
    s = _CORP_RE.sub("", s)

    # 中黒削除
    s = s.replace("・", "")

    # 小文字
    s = s.lower()

    return s

# =========================================================
# Address helpers
# =========================================================
def extract_postal(s: str) -> str:
    s = s or ""
    m = re.search(r"(\d{3})-?(\d{4})", s)
    return (m.group(1) + m.group(2)) if m else ""

def norm_addr(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "", s).replace("　", "")
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(trans)
    s = s.replace("−", "-").replace("ー", "-").replace("―", "-").replace("‐", "-")
    return s

def core_addr_tokens(addr: str) -> Dict[str, object]:
    a = norm_addr(addr)

    pref = ""
    m = re.search(r"(北海道|東京都|大阪府|京都府|.{2,3}県)", a)
    if m:
        pref = m.group(1)

    city = ""
    m2 = re.search(r"(.*?[市区町村])", a)
    if m2:
        city = m2.group(1)

    nums = re.findall(r"\d+", a)
    return {"pref": pref, "city": city, "nums": nums, "norm": a}

# =========================================================
# CSV load (安全に)
# =========================================================
def read_csv_safely(path: str, encoding_candidates: List[str], **kwargs) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in encoding_candidates:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to read {path} with encodings={encoding_candidates}: {last_err}")

# ⚠ usecols=[7,11] は「列の意味が確定してる時だけ」おすすめ
target = read_csv_safely(
    "data/01_hokkaido_all_20251226.csv",
    ["cp932", "shift_jis", "shift_jisx0213", "utf-8-sig", "utf-8"],
    usecols=[7, 11],
)

# subject は現状使ってないなら消してOK（読み込みエラーの原因になりがち）
subject = read_csv_safely(
    "data/data-1768790126893.csv",
    ["utf-8-sig", "utf-8", "cp932"],
    usecols=["company_name"],
)

print("target columns:", target.columns.tolist())

# =========================================================
# Build name_index (有限会社が消えない “完璧版”)
#   - 1キー=1社（重複は出さない）
#   - ただし aliases に「株式会社/有限会社の両方の正式名」を保持
#   - 表示名は query の法人格に合わせて選ぶ
# =========================================================
def detect_name_col(df: pd.DataFrame) -> str:
    candidates = ["company_name", "企業名", "会社名", "名称", "商号", "法人名", "name"]
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return cols[0]  # 最後の保険

NAME_COL = detect_name_col(target)
print("Detected NAME_COL:", NAME_COL)

def build_name_index(df: pd.DataFrame, name_col: str) -> Dict[str, List[Dict]]:
    idx: Dict[str, List[Dict]] = {}

    for _, row in df.iterrows():
        raw_name = str(row.get(name_col, "") or "")
        key = normalize_company_key(raw_name)
        if not key:
            continue

        if key not in idx:
            cand = row.to_dict()
            cand["name"] = raw_name                 # 代表名（後で更新）
            cand["aliases"] = {raw_name}            # ★重要：別法人格も保持
            idx[key] = [cand]
        else:
            cur = idx[key][0]
            cur.setdefault("aliases", set()).add(raw_name)

            # ✅ 代表名の選び方：
            # 「株式会社優先」をやめる（これが有限会社が消える原因）
            # → 情報量が多い（長い）方を代表名にする
            cur_name = str(cur.get("name", "") or "")
            if len(raw_name) > len(cur_name):
                cur["name"] = raw_name

            # 空なら埋める（任意）
            for k in ["corp_number", "postal_code", "prefecture", "city", "street"]:
                if not cur.get(k) and row.get(k):
                    cur[k] = row.get(k)

    return idx

name_index = build_name_index(target, name_col=NAME_COL)
print("name_index size:", len(name_index))

def choose_display_name(query_name: str, cand: Dict) -> str:
    """クエリの法人格に合わせて aliases から表示名を選ぶ。"""
    aliases = cand.get("aliases") or set()
    if isinstance(aliases, list):
        aliases = set(aliases)

    kind = detect_corp_kind(query_name)

    if kind == "YK":
        # 有限会社を優先して返す
        for a in aliases:
            if re.search(r"(有限会社|㈲|\(有\)|（有）)", a):
                return a

    if kind == "KK":
        # 株式会社を優先して返す
        for a in aliases:
            if re.search(r"(株式会社|㈱|\(株\)|（株）)", a):
                return a

    # 指定なし or 見つからない：代表名
    return str(cand.get("name") or query_name)

# =========================================================
# Match rules / scoring
# =========================================================
def judge_match(log_company: str, log_addr: str, cand: Dict) -> Tuple[str, Dict]:
    reason = {"rules_hit": []}

    la = core_addr_tokens(log_addr)
    lp = extract_postal(log_addr)

    cp = re.sub(r"\D", "", str(cand.get("postal_code", "") or ""))
    pref = str(cand.get("prefecture", "") or "")
    city = str(cand.get("city", "") or "")
    street = str(cand.get("street", "") or "")
    street_n = norm_addr(street)

    # A: 郵便番号7桁一致
    if lp and cp and lp == cp:
        reason["rules_hit"].append("A:postal_exact")
        return "match", reason

    # B: pref+city+street が含まれる
    if pref and city and street_n:
        if (pref in la["norm"]) and (city in la["norm"]) and (street_n in la["norm"]):
            reason["rules_hit"].append("B:pref_city_street_contains")
            return "match", reason

    # C: A,Bで見つからなかった場合のみ
    if pref and city and street_n:
        nums = re.findall(r"\d+", street_n)
        hit = 0
        for n in nums[:6]:
            if n in la["nums"]:
                hit += 1
        if hit >= 3 and (pref in la["norm"]) and (city in la["norm"]):
            reason["rules_hit"].append(f"C:nums_hit_{hit}_with_pref_city")
            return "match", reason

    # D: pref+city
    if pref and city and (pref in la["norm"]) and (city in la["norm"]):
        reason["rules_hit"].append("D:pref_city")
        return "maybe", reason

    # E: 郵便番号先頭3桁 + city
    if lp and cp and lp[:3] == cp[:3] and city and (city in la["norm"]):
        reason["rules_hit"].append("E:postal_prefix3_plus_city")
        return "maybe", reason

    reason["rules_hit"].append("Z:no_rules")
    return "no", reason

def score_candidate(log_addr: str, query_name: str, cand: Dict) -> int:
    verdict, reason = judge_match(query_name, log_addr, cand)

    if verdict == "match":
        if any(r.startswith("A:") for r in reason["rules_hit"]):
            return 1000
        if any(r.startswith("B:") for r in reason["rules_hit"]):
            return 900
        if any(r.startswith("C:") for r in reason["rules_hit"]):
            return 800
        return 700

    if verdict == "maybe":
        if any(r.startswith("D:") for r in reason["rules_hit"]):
            return 200
        if any(r.startswith("E:") for r in reason["rules_hit"]):
            return 150
        return 100

    return 0

def _is_ab_confirm(reason: Dict) -> bool:
    hits = reason.get("rules_hit", [])
    return any(h.startswith("A:") or h.startswith("B:") for h in hits)

# =========================================================
# Suggest (有限会社が “表示される”)
#   - A/B確定なら1社だけ
#   - official_name は query の法人格に合わせて表示名を選ぶ
# =========================================================
def suggest_companies(query_name: str, log_addr: str, name_index: dict, topk: int = 8):
    key = normalize_company_key(query_name)
    cands = name_index.get(key, [])
    if not cands:
        return []

    # A/B 確定なら1件のみ返す
    for c in cands:
        verdict, reason = judge_match(query_name, log_addr, c)
        if verdict == "match" and _is_ab_confirm(reason):
            return [{
                "score": 9999,
                "corp_number": c.get("corp_number"),
                "official_name": choose_display_name(query_name, c),  # ✅ここが肝
                "postal_code": c.get("postal_code"),
                "prefecture": c.get("prefecture"),
                "city": c.get("city"),
                "street": c.get("street"),
                "verdict": verdict,
                "rules_hit": reason["rules_hit"],
            }]

    ranked = []
    for c in cands:
        ranked.append((score_candidate(log_addr, query_name, c), c))
    ranked.sort(key=lambda x: x[0], reverse=True)

    out = []
    for sc, c in ranked[:topk]:
        out.append({
            "score": sc,
            "corp_number": c.get("corp_number"),
            "official_name": choose_display_name(query_name, c),  # ✅ここも肝
            "postal_code": c.get("postal_code"),
            "prefecture": c.get("prefecture"),
            "city": c.get("city"),
            "street": c.get("street"),
        })
    return out

# =========================================================
# Debug routes
# =========================================================
@app.get("/__routes")
def __routes():
    return sorted([getattr(r, "path", "") for r in app.routes])

@app.get("/__debug/sample_names")
def __debug_sample_names(n: int = 30):
    # 有限会社が index に入ってるか即確認できる
    col = target[NAME_COL].astype(str)
    yk = col[col.str.contains("有限会社", na=False)].head(n).to_list()
    kk = col[col.str.contains("株式会社", na=False)].head(n).to_list()
    return {"NAME_COL": NAME_COL, "yk_sample": yk, "kk_sample": kk}
