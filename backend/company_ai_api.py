import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from company_summary_batch import generate_detailed_report
from csv_api import router as csv_router


app = FastAPI()

app.include_router(csv_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# POST で受け取るリクエストボディ
class CompanyRequest(BaseModel):
    name: str

class SuggestRequest(BaseModel):
    keyword: str

class SuggestResponse(BaseModel):
    candidates: list[str]

def _create_report(name: str):
    BASE_DIR = os.path.dirname(__file__)
    SUMMARY_PATH = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

    df = pd.read_csv(SUMMARY_PATH)

    hit = df[df["company_name"].str.contains(name, na=False)]

    if hit.empty:
        return None, {"error": f"企業 '{name}' が見つかりません"}

    row = hit.iloc[0]
    report = generate_detailed_report(row)

    return row, {
        "company": row["company_name"],
        "report": report
    }
    # 新しく POST 版を追加
@app.post("/company")
def post_company_report(req: CompanyRequest):
    row, result = _create_report(req.name)
    return result
@app.post("/company_suggest", response_model=SuggestResponse)
def company_suggest(body: SuggestRequest):
    BASE_DIR = os.path.dirname(__file__)
    SUMMARY_PATH = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

    df = pd.read_csv(SUMMARY_PATH)
    keyword = body.keyword.strip()

    if not keyword:
        return {"candidates": []}

    lower = keyword.lower()

    names = (
        df["company_name"]
        .dropna()
        .drop_duplicates()
        .astype(str)
        .tolist()
    )

    prefix_hits = [n for n in names if n.lower().startswith(lower)]

    contains_hits = [
        n for n in names
        if lower in n.lower() and n not in prefix_hits
    ]

    # 最大10件
    filtered = (prefix_hits + contains_hits)[:15]

    return {"candidates": filtered}

# POST 版
@app.post("/company")
def post_company_report(req: CompanyRequest):
    row, result = _create_report(req.name, req.student_no)
    return result