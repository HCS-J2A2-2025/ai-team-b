import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from company_summary_batch import generate_detailed_report

app = FastAPI()

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