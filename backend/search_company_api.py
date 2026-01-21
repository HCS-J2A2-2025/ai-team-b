from fastapi import FastAPI, Query
from typing import List
from pydantic import BaseModel
import csv,json
import unicodedata
import re

app = FastAPI()


# CSV から JSON へ変換（1回だけ実行）
with open("data/01_hokkaido_all_20251226.csv", encoding="Shift_JIS") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

with open("frontend/companies.json", "w", encoding="Shift_JIS") as f:
    json.dump(rows, f, ensure_ascii=False)

# 起動時にロード
with open("frontend/companies.json", encoding="Shift_JIS") as f:
    companies = json.load(f)

KABUSHIKI_PATTERNS = [
    r"株式会社",
    r"\(株\)",
    r"（株）",
    r"㈱",
    r"株",
]


@app.get("/api/companies/suggest")
def suggest_companies(
    q: str = Query(..., min_length=2),
    limit: int = 10
):
    q_norm = normalize_text(q)

    results = [
        c["company_name"]

        for c in companies
        if normalize_text(c["company_name"]).startswith(q_norm)
    ]

    return results[:limit]

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).lower().strip()
    text = re.sub(r"\s+", " ", text)  # Replace multiple spaces with a single space
    return text

@app.get("/api/companies/search")
def search_companies(
    q: str = Query(..., min_length=2),
    limit: int = 10,
    offset: int = 0
):
    q_norm = normalize_text(q)

    matched_companies = []
    for c in companies:
        company_name_norm = normalize_text(c["company_name"])
        if q_norm in company_name_norm:
            matched_companies.append({
                "companyName": c["company_name"]
            })
            
            return matched_companies[offset:offset + limit]

class ValidateRequest(BaseModel):
    name: str

@app.post("/api/company/validate")
def validate_company(req: ValidateRequest):
    raw = req.name.strip()
    if not raw:
        return {
            "ok": False,
            "error": "会社名が入力されていません"
        }

    key = normalize_text(raw)

    # ① 完全一致（正規化後）
    exact_matches = [
        c["company_name"]
        for c in companies
        if normalize_text(c["company_name"]) == key
    ]

    if len(exact_matches) == 1:
        return {
            "ok": True,
            "company": exact_matches[0]
        }

    # ② 前方一致で1件だけ
    prefix_matches = [
        c["company_name"]
        for c in companies
        if normalize_text(c["company_name"]).startswith(key)
    ]

    if len(prefix_matches) == 1:
        return {
            "ok": True,
            "company": prefix_matches[0]
        }

    # ③ 見つからない / 複数
    if len(prefix_matches) == 0:
        return {
            "ok": False,
            "error": "企業が見つかりません"
        }

    return {
        "ok": False,
        "error": "候補が複数あります。サジェストから選択してください"
    }