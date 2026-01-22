import pandas as pd
from typing import List, Dict, Tuple
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache_api import router as cache_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ★ ここが重要：フロントは /api/cache/company を叩いている
app.include_router(cache_router, prefix="/api/cache", tags=["cache"])


# =========================
# CSV load
# =========================
target = pd.read_csv(
    "data/01_hokkaido_all_20251226.csv",
    encoding="Shift_JIS",
    usecols=[7, 11],
)

subject = pd.read_csv(
    "data/data-1768790126893.csv",
    encoding="utf-8",
    usecols=["company_name"],
)

print("target columns:", target.columns.tolist())


# =========================
# Company name normalize
# =========================
_CORP_PATTERNS = [
    r"株式会社", r"（株）", r"\(株\)", r"㈱",
    r"有限会社", r"（有）", r"\(有\)", r"㈲",
    r"合同会社",
    r"合資会社", r"合名会社",
    r"一般社団法人", r"一般財団法人", r"公益社団法人", r"公益財団法人",
    r"医療法人", r"学校法人", r"社会福祉法人", r"宗教法人",
]
_CORP_RE = re.compile("|".join(_CORP_PATTERNS))

def normalize_company_key(name: str) -> str:
    """会社名を同一判定用のキーに正規化（前株/後株/株式会社の差は吸収）"""
    if not name:
        return ""
    s = str(name)

    # 1) 空白除去
    s = s.strip().replace("　", "")
    s = re.sub(r"\s+", "", s)

    # 2) 全角英数→半角
    trans = str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    )
    s = s.translate(trans)

    # 3) 記号ゆれ統一
    s = s.replace("−", "-").replace("ー", "-").replace("―", "-").replace("‐", "-")
    s = s.replace("･", "・")

    # 4) かっこ類を除去
    s = re.sub(r"[()（）【】\[\]{}<>＜＞「」『』]", "", s)

    # 5) 法人格を除去
    s = _CORP_RE.sub("", s)

    # 6) 中黒削除
    s = s.replace("・", "")

    # 7) 英字小文字
    s = s.lower()

    return s


# =========================
# Address normalize
# =========================
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


# =========================
# Build name_index
# =========================
def detect_name_col(df: pd.DataFrame) -> str:
    """
    usecols=[7,11] だと列名が company_name じゃないことがあるので推定する。
    """
    candidates = ["company_name", "企業名", "会社名", "名称", "商号", "法人名", "name"]
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return cols[0]

NAME_COL = detect_name_col(target)
print("Detected NAME_COL:", NAME_COL)

def pick_better_official_name(a: str, b: str) -> str:
    """
    同じキーに複数正式名が入りうる場合の代表名選び。
    基本は '株式会社' を含む方を優先、次に長い方。
    """
    a = a or ""
    b = b or ""
    a_has = "株式会社" in a
    b_has = "株式会社" in b
    if a_has and not b_has:
        return a
    if b_has and not a_has:
        return b
    # どっちも同じなら長い方（情報量が多い方）
    return a if len(a) >= len(b) else b

def build_name_index(df: pd.DataFrame, name_col: str) -> Dict[str, List[Dict]]:
    """
    key -> [cand]
    ただし 1キーにつき1cand（=1社）に統一して重複を絶対に出さない。
    """
    idx: Dict[str, List[Dict]] = {}

    for _, row in df.iterrows():
        raw_name = str(row.get(name_col, "") or "")
        key = normalize_company_key(raw_name)
        if not key:
            continue

        if key not in idx:
            cand = row.to_dict()
            cand["name"] = raw_name  # ★ target側の正式名
            idx[key] = [cand]
        else:
            # 既に入っている代表candと比較して、より良い正式名に更新だけする
            cur = idx[key][0]
            cur_name = str(cur.get("name", "") or "")
            better = pick_better_official_name(cur_name, raw_name)
            cur["name"] = better

            # 住所/郵便番号なども「空なら埋める」程度に更新（任意）
            for k in ["corp_number", "postal_code", "prefecture", "city", "street"]:
                if not cur.get(k) and row.get(k):
                    cur[k] = row.get(k)

    return idx

name_index = build_name_index(target, name_col=NAME_COL)
print("name_index size:", len(name_index))


# =========================
# Match rules
# =========================
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


# =========================
# Scoring
# =========================
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


# =========================
# Suggest: A/B確定なら「その1社だけ」 + 表示は常に target正式名
# =========================
def _is_ab_confirm(reason: Dict) -> bool:
    hits = reason.get("rules_hit", [])
    return any(h.startswith("A:") or h.startswith("B:") for h in hits)

def suggest_companies(query_name: str, log_addr: str, name_index: dict, topk: int = 8):
    key = normalize_company_key(query_name)
    cands = name_index.get(key, [])
    if not cands:
        return []

    # 1キー=1cand の設計なので基本ここは1件
    # ただし安全のため複数でも動くようにしておく
    for c in cands:
        verdict, reason = judge_match(query_name, log_addr, c)
        if verdict == "match" and _is_ab_confirm(reason):
            return [{
                "score": 9999,
                "corp_number": c.get("corp_number"),
                "official_name": c.get("name"),  # ★ 表示は常に target側の正式名
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
            "official_name": c.get("name"),  # ★ 表示は常に target側の正式名
            "postal_code": c.get("postal_code"),
            "prefecture": c.get("prefecture"),
            "city": c.get("city"),
            "street": c.get("street"),
        })
    return out


@app.get("/__routes")
def __routes():
    return sorted([getattr(r, "path", "") for r in app.routes])
