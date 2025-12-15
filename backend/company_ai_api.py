import os
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 既存ルーター
from csv_api import router as csv_router
from followup.api import router as followup_router

# 会社要約・面接一覧系（あなたの既存実装に合わせて import）
from company_summary_batch import (
    generate_detailed_report,
    build_interview_records_for_company,
    get_latest_interview_texts,
)

app = FastAPI()

# ルーター登録
app.include_router(csv_router)
app.include_router(followup_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========= モデル =========
class CompanyRequest(BaseModel):
    name: str
    student_no: str | None = None  # ← /api/company/report 用にも /company 用にも使えるようにする


# 旧: /api/company/suggest 用（keyword）
class SuggestRequest(BaseModel):
    keyword: str


# 互換: /company_suggest 用（q でも keyword でも受ける）
class SuggestRequestCompat(BaseModel):
    q: str | None = None
    keyword: str | None = None


# 返却は両方のキーを持たせて互換性を最大化
class SuggestResponseCompat(BaseModel):
    candidates: list[str] = []
    suggestions: list[str] = []


# ========= 共通：CSVロード =========
def _summary_csv_path() -> str:
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "data", "company_summary_t.csv")


def _report_csv_path() -> str:
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "data", "report_t_all.csv")


def load_summary_df() -> pd.DataFrame:
    return pd.read_csv(_summary_csv_path())


def load_report_df() -> pd.DataFrame:
    return pd.read_csv(_report_csv_path())


# ========= 共通ロジック：会社レポート作成 =========
def _create_report(name: str, student_no: str | None = None):
    df = load_summary_df()

    hit = df[df["company_name"].astype(str).str.contains(name, na=False)]
    if hit.empty:
        return None, {"error": f"企業 '{name}' が見つかりません"}

    row = hit.iloc[0]

    # 左：AI要約
    report = generate_detailed_report(row)

    # 右：面接一覧（存在すれば返す）
    interviews = []
    try:
        interviews = build_interview_records_for_company(row["company_name"], student_no)
    except Exception:
        # 関数が未整備でも /company が死なないように
        interviews = []

    # 右：最新テキスト（存在すれば返す）
    texts = []
    try:
        texts = get_latest_interview_texts(row["company_name"], limit=5)
    except Exception:
        texts = []

    return row, {
        "company": row["company_name"],
        "report": report,
        "interviews": interviews,
        "texts": texts,
    }


# ========= 互換：/company（フロントが POST /company を呼ぶ場合） =========
@app.post("/company")
def post_company(req: CompanyRequest):
    _, result = _create_report(req.name, req.student_no)
    return result


# ========= 推奨：/api/company/report（Result.jsx が使う） =========
@app.post("/api/company/report")
def post_company_report(req: CompanyRequest):
    _, result = _create_report(req.name, req.student_no)
    return result


# ========= 面接詳細：/api/interview/detail =========
@app.get("/api/interview/detail")
def get_interview_detail(
    report_id: str = Query(..., description="レポートID（例: P20233026）")
):
    df = load_report_df()

    col_report_id = "レポートID"
    col_content = "面接内容"  # もしくは "report_text" 等に変更可
    col_memo = "メモ"        # 無ければ空

    if col_report_id not in df.columns:
        return {"error": f"CSVに '{col_report_id}' 列がありません", "report_id": report_id}

    hit = df[df[col_report_id].astype(str) == str(report_id)]
    if hit.empty:
        return {"error": "not found", "report_id": report_id}

    row = hit.iloc[0]

    interview_text = str(row.get(col_content, "")).strip()
    memo_text = str(row.get(col_memo, "")).strip() if col_memo in df.columns else ""

    return {
        "report_id": str(report_id),
        "question_content": interview_text,
        "memo": memo_text,
    }


# ========= 既存：/api/company/suggest（keywordで受ける） =========
@app.post("/api/company/suggest", response_model=SuggestResponseCompat)
def api_company_suggest(body: SuggestRequest):
    df = load_summary_df()
    keyword = (body.keyword or "").strip()

    if not keyword:
        return {"candidates": [], "suggestions": []}

    lower = keyword.lower()
    names = df["company_name"].dropna().drop_duplicates().astype(str).tolist()

    prefix_hits = [n for n in names if n.lower().startswith(lower)]
    contains_hits = [n for n in names if lower in n.lower() and n not in prefix_hits]

    out = (prefix_hits + contains_hits)[:15]
    return {"candidates": out, "suggestions": out}


# ========= 互換：/company_suggest（q or keyword どちらでもOK） =========
@app.post("/company_suggest", response_model=SuggestResponseCompat)
def company_suggest(body: SuggestRequestCompat):
    df = load_summary_df()

    q = (body.q or body.keyword or "").strip()
    if not q:
        return {"candidates": [], "suggestions": []}

    lower = q.lower()
    names = df["company_name"].dropna().drop_duplicates().astype(str).tolist()

    prefix_hits = [n for n in names if n.lower().startswith(lower)]
    contains_hits = [n for n in names if lower in n.lower() and n not in prefix_hits]

    out = (prefix_hits + contains_hits)[:15]
    # フロント互換のため両方返す
    return {"candidates": out, "suggestions": out}
