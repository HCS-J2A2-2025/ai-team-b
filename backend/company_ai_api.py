import os
from fastapi import FastAPI
import pandas as pd
from company_summary_batch import generate_detailed_report

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/company/{name}")
def get_company_report(name: str):

    # CSV のパスを backend/data/company_summary_t.csv に統一
    BASE_DIR = os.path.dirname(__file__)
    SUMMARY_PATH = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

    # CSV 読み込み
    df = pd.read_csv(SUMMARY_PATH)

    # 部分一致で企業を検索
    hit = df[df["company_name"].str.contains(name, na=False)]

    # 見つからない時
    if hit.empty:
        return {"error": f"企業 '{name}' が見つかりません"}

    # 最初の1件を使う
    row = hit.iloc[0]

    # レポート生成
    report = generate_detailed_report(row)

    return {
        "company": row["company_name"],
        "report": report
    }
