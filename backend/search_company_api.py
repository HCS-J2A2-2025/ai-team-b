from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional, Set

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache_api import router as cache_router

# =========================================================
# FastAPI
# =========================================================
app = FastAPI()

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
    s = s or ""
    if re.search(r"(有限会社|㈲|\(有\)|（有）)", s):
        return "YK"
    if re.search(r"(株式会社|㈱|\(株\)|（株）)", s):
        return "KK"
    return ""

def normalize_company_key(name: str) -> str:
    """会社名の同一判定用キー（法人格差は吸収）"""
    if not name:
        return ""
    s = str(name)

    s = s.strip().replace("　", "")
    s = re.sub(r"\s+", "", s)

    trans = str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    s = s.translate(trans)

    s = s.replace("−", "-").replace("ー", "-").replace("―", "-").replace("‐", "-")
    s = s.replace("･", "・")
    s = re.sub(r"[()（）【】\[\]{}<>＜＞「」『』]", "", s)

    s = _CORP_RE.sub("", s)
    s = s.replace("・", "")

    return s.lower()

# =========================================================
# CSV load helper
# =========================================================
def read_csv_safely(path: str, encoding_candidates: List[str], **kwargs) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in encoding_candidates:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to read {path} encodings={encoding_candidates}: {last_err}")

# =========================================================
# ✅ 説明会だけ企業ブロック（これ1個だけ）
#   - ここで作った is_blocked_company() を
#     Suggest / Search / Validate で共通利用する
# =========================================================
REPORT_PATH = "data/report_t_all.csv"  # ★実データのパスに合わせる
REPORT_ENCODINGS = ["utf-8-sig", "utf-8", "cp932", "shift_jis", "shift_jisx0213"]

EXPLAIN_WORDS = ["説明会", "会社説明会", "セミナー", "合同説明会", "企業説明", "ガイダンス"]

def _is_explain_stage(s: str) -> bool:
    t = str(s or "").strip()
    return any(w in t for w in EXPLAIN_WORDS)

def _detect_company_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["企業名", "company_name", "会社名"]:
        if c in df.columns:
            return c
    return None

def _detect_stage_col(df: pd.DataFrame) -> Optional[str]:
    # “説明会” が入りやすい列を優先順で探す（必要なら追加）
    candidates = [
        "選考段階",
        "イベント名",
        "イベント種別",
        "種別",
        "区分",
        "ステータス",
        "event_kind",
        "stage",
        "type",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _load_report_df_for_explain_block() -> Optional[pd.DataFrame]:
    """
    1) load_report_df_normalized が存在すればそれを使う
    2) 無ければ REPORT_PATH を read_csv_safely で読む
    """
    # 1) company_summary_batch 側ローダがある場合
    try:
        # 関数が存在する環境なら使える
        if "load_report_df_normalized" in globals() and callable(globals()["load_report_df_normalized"]):
            return globals()["load_report_df_normalized"]()
    except Exception as e:
        print("[WARN] explain-only: load_report_df_normalized failed:", e)

    # 2) 直接CSVから読む
    try:
        return read_csv_safely(REPORT_PATH, REPORT_ENCODINGS)
    except Exception as e:
        print("[WARN] explain-only: report csv read failed:", e)
        return None

def build_explain_only_keys_from_report_df(df: pd.DataFrame) -> Set[str]:
    company_col = _detect_company_col(df)
    stage_col = _detect_stage_col(df)

    if not company_col or not stage_col:
        print("[WARN] explain-only: missing cols -> company_col=", company_col, "stage_col=", stage_col)
        return set()

    tmp = df[[company_col, stage_col]].copy()
    tmp[company_col] = tmp[company_col].astype(str).fillna("")
    tmp[stage_col] = tmp[stage_col].astype(str).fillna("")

    tmp["key"] = tmp[company_col].map(normalize_company_key)
    tmp = tmp[tmp["key"] != ""]

    tmp["is_explain"] = tmp[stage_col].map(_is_explain_stage)

    # 「全レコードが説明会」 = 説明会だけ企業
    g = tmp.groupby("key")["is_explain"]
    return set(g.apply(lambda s: (len(s) > 0) and bool(s.all())).index)

def load_explain_only_keys() -> Set[str]:
    df = _load_report_df_for_explain_block()
    if df is None or df.empty:
        print("[WARN] explain-only: disabled (no report df)")
        return set()

    keys = build_explain_only_keys_from_report_df(df)
    print("[INFO] EXPLAIN_ONLY_KEYS size:", len(keys))
    return keys

EXPLAIN_ONLY_KEYS: Set[str] = load_explain_only_keys()

def is_blocked_company(name: str) -> bool:
    key = normalize_company_key(name)
    return bool(key) and (key in EXPLAIN_ONLY_KEYS)

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
# Load corp DB (company/address)
# =========================================================
target = read_csv_safely(
    "data/01_hokkaido_all_20251226.csv",
    ["cp932", "shift_jis", "shift_jisx0213", "utf-8-sig", "utf-8"],
    usecols=[7, 11],
)
print("target columns:", target.columns.tolist())

# =========================================================
# Build name_index
# =========================================================
def detect_name_col(df: pd.DataFrame) -> str:
    candidates = ["company_name", "企業名", "会社名", "名称", "商号", "法人名", "name"]
    for c in candidates:
        if c in df.columns:
            return c
    return df.columns[0]

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
            cand["name"] = raw_name
            cand["aliases"] = {raw_name}
            idx[key] = [cand]
        else:
            cur = idx[key][0]
            cur.setdefault("aliases", set()).add(raw_name)
            cur_name = str(cur.get("name", "") or "")
            if len(raw_name) > len(cur_name):
                cur["name"] = raw_name
    return idx

name_index = build_name_index(target, NAME_COL)
print("name_index size:", len(name_index))

def choose_display_name(query_name: str, cand: Dict) -> str:
    aliases = cand.get("aliases") or set()
    if isinstance(aliases, list):
        aliases = set(aliases)

    kind = detect_corp_kind(query_name)
    if kind == "YK":
        for a in aliases:
            if re.search(r"(有限会社|㈲|\(有\)|（有）)", a):
                return a
    if kind == "KK":
        for a in aliases:
            if re.search(r"(株式会社|㈱|\(株\)|（株）)", a):
                return a

    return str(cand.get("name") or query_name)

# =========================================================
# Match rules / scoring（ここから先は今のままでOK）
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

    if lp and cp and lp == cp:
        reason["rules_hit"].append("A:postal_exact")
        return "match", reason

    if pref and city and street_n:
        if (pref in la["norm"]) and (city in la["norm"]) and (street_n in la["norm"]):
            reason["rules_hit"].append("B:pref_city_street_contains")
            return "match", reason

    if pref and city and street_n:
        nums = re.findall(r"\d+", street_n)
        hit = 0
        for n in nums[:6]:
            if n in la["nums"]:
                hit += 1
        if hit >= 3 and (pref in la["norm"]) and (city in la["norm"]):
            reason["rules_hit"].append(f"C:nums_hit_{hit}_with_pref_city")
            return "match", reason

    if pref and city and (pref in la["norm"]) and (city in la["norm"]):
        reason["rules_hit"].append("D:pref_city")
        return "maybe", reason

    if lp and cp and lp[:3] == cp[:3] and city and (city in la["norm"]):
        reason["rules_hit"].append("E:postal_prefix3_plus_city")
        return "maybe", reason

    reason["rules_hit"].append("Z:no_rules")
    return "no", reason
