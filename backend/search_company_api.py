import pandas as pd
import List, Dict, Tuple
import re

target= pd.read_csv("data/01_hokkaido_all_20251226.csv"),
encoding = "Shift_JIS",
useclos=[7,11]

subject = pd.read_csv("data/data-1768790126893.csv"),
encoding="utf-8",
useclos = pd.read_csv("data/data-1768790126893.csv")["company_name"].to_dict()

norm_name = pd.read_csv("data/norm_name.csv")["company_name"].to_dict()


def score_candidate():
    score = 0
    # いろいろ一致したら点数を足す
    return score

def suggest_companies(query_name: str, log_addr: str, name_index: dict, topk=8):
    
    key = norm_name(query_name)
    cands = name_index.get(key, [])  # 同名候補リスト

    ranked = []
    for c in cands:
        ranked.append((score_candidate(log_addr, query_name, c), c))

    ranked.sort(key=lambda x: x[0], reverse=True)

    # サジェスト表示用：法人番号/正式名/住所/郵便番号 を出すとユーザーが選びやすい
    out = []
    for sc, c in ranked[:topk]:
        out.append({
            "score": sc,
            "corp_number": c.get("corp_number"),
            "official_name": c.get("name"),
            "postal_code": c.get("postal_code"),
            "prefecture": c.get("prefecture"),
            "city": c.get("city"),
            "street": c.get("street"),
        })
    return out

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

def core_addr_tokens(addr: str) -> Dict[str, str]:
    """
    住所から「都道府県」「市区町村」「番地っぽい数字列」を抜く簡易版
    """
    a = norm_addr(addr)
    # 都道府県（超ざっくり）
    pref = ""
    m = re.search(r"(北海道|東京都|大阪府|京都府|.{2,3}県)", a)
    if m:
        pref = m.group(1)

    # 市区町村（ざっくり）
    city = ""
    m2 = re.search(r"(.*?[市区町村])", a)
    if m2:
        city = m2.group(1)

    # 数字（番地・丁目に効く）
    nums = re.findall(r"\d+", a)
    return {"pref": pref, "city": city, "nums": nums, "norm": a}

def judge_match(log_company: str, log_addr: str, cand: Dict) -> Tuple[str, Dict]:
    """
    return:
      verdict: "match" | "maybe" | "no"
      reason: デバッグ用の理由
    cand 想定キー:
      - postal_code (7桁)
      - prefecture
      - city
      - street
      - name
    """
    reason = {"rules_hit": []}

    la = core_addr_tokens(log_addr)
    lp = extract_postal(log_addr)

    cp = re.sub(r"\D", "", str(cand.get("postal_code", "") or ""))
    pref = str(cand.get("prefecture", "") or "")
    city = str(cand.get("city", "") or "")
    street = str(cand.get("street", "") or "")
    street_n = norm_addr(street)

    # -------------------------
    # 1) 強一致ルール（確定）
    # -------------------------

    # ルールA: 郵便番号7桁一致 → ほぼ確定
    if lp and cp and lp == cp:
        reason["rules_hit"].append("A:postal_exact")
        return "match", reason

    # ルールB: 住所核心（pref+city+streetが含まれる）→ かなり確定
    if pref and city and street_n:
        if (pref in la["norm"]) and (city in la["norm"]) and (street_n in la["norm"]):
            reason["rules_hit"].append("B:pref_city_street_contains")
            return "match", reason

    # ルールC: streetが完全に入らなくても、streetの数字列が多数一致 → 確度高め
    if street_n:
        nums = re.findall(r"\d+", street_n)
        hit = 0
        for n in nums[:6]:
            if n in la["nums"]:
                hit += 1
        if hit >= 3 and (pref in la["norm"]) and (city in la["norm"]):
            reason["rules_hit"].append(f"C:nums_hit_{hit}_with_pref_city")
            return "match", reason

    # -------------------------
    # 2) 弱一致（候補）ルール
    # -------------------------

    # ルールD: 都道府県 + 市区町村一致 → 候補
    if pref and city and (pref in la["norm"]) and (city in la["norm"]):
        reason["rules_hit"].append("D:pref_city")
        return "maybe", reason

    # ルールE: 郵便番号先頭3桁一致 + 市区町村一致 → 候補
    if lp and cp and lp[:3] == cp[:3] and city and (city in la["norm"]):
        reason["rules_hit"].append("E:postal_prefix3_plus_city")
        return "maybe", reason

    # -------------------------
    # 3) 不一致
    # -------------------------
    reason["rules_hit"].append("Z:no_rules")
    return "no", reason