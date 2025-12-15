import os
import time
import uuid
import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic import BaseModel

# 既存ルーター
from csv_api import router as csv_router
from followup.api import router as followup_router

# report_t_all.csv の列名ゆれ/BOM/空白を吸収する
from company_summary_batch import (
    generate_detailed_report,
    build_interview_records_for_company,
    get_latest_interview_texts,
    load_report_df as load_report_df_normalized,
)

# =========================
# FastAPI (docs OFF)
# =========================
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# ルーター登録
app.include_router(csv_router)
app.include_router(followup_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Models
# =========================
class CompanyRequest(BaseModel):
    name: str
    student_no: str | None = None


class SuggestRequest(BaseModel):
    keyword: str


class SuggestRequestCompat(BaseModel):
    q: str | None = None
    keyword: str | None = None


class SuggestResponseCompat(BaseModel):
    candidates: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class InterviewDetailRequest(BaseModel):
    report_id: str
    
class CompanyResultRequest(BaseModel):
    request_id: str


# =========================
# CSV helpers
# =========================
def _summary_csv_path() -> str:
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "data", "company_summary_t.csv")


def load_summary_df() -> pd.DataFrame:
    return pd.read_csv(_summary_csv_path(), encoding="utf-8-sig")


# =========================
# Report build (internal)
# =========================
def _create_report(name: str, student_no: str | None = None):
    keyword = str(name or "").strip()
    if not keyword:
        return None, {"error": "企業名が空です"}

    try:
        df = load_summary_df()
    except Exception as e:
        return None, {"error": f"company_summary_t.csv の読み込みに失敗しました: {e}"}

    if "company_name" not in df.columns:
        return None, {"error": "company_summary_t.csv に company_name 列がありません"}

    hit = df[df["company_name"].astype(str).str.contains(keyword, na=False, regex=False)]
    if hit.empty:
        return None, {"error": f"企業 '{keyword}' が見つかりません"}

    row = hit.iloc[0]
    company_name = str(row["company_name"]).strip()

    # 左：AI要約
    try:
        report = generate_detailed_report(row)
    except Exception as e:
        print("[WARN] generate_detailed_report failed:", e)
        report = f"[ERROR] 要約生成に失敗しました: {e}"

    # 右：面接一覧
    try:
        interviews = build_interview_records_for_company(company_name, student_no)
    except Exception as e:
        print("[WARN] build_interview_records_for_company failed:", e)
        interviews = []

    # 参考：最新の生テキスト
    try:
        texts = get_latest_interview_texts(company_name, limit=5)
    except Exception as e:
        print("[WARN] get_latest_interview_texts failed:", e)
        texts = []

    return row, {
        "company": company_name,
        "report": report,
        "interviews": interviews,
        "texts": texts,
    }


# =========================
# In-memory cache (TTL)
# =========================
REPORT_CACHE: dict[str, dict] = {}         # request_id -> payload
REPORT_CACHE_TS: dict[str, float] = {}     # request_id -> epoch seconds
CACHE_TTL_SECONDS = int(os.getenv("REPORT_CACHE_TTL", "300"))  # 5分デフォ

def _cache_cleanup():
    now = time.time()
    expired = [rid for rid, ts in REPORT_CACHE_TS.items() if now - ts > CACHE_TTL_SECONDS]
    for rid in expired:
        REPORT_CACHE.pop(rid, None)
        REPORT_CACHE_TS.pop(rid, None)


def _cache_put(payload: dict) -> str:
    _cache_cleanup()
    rid = uuid.uuid4().hex
    REPORT_CACHE[rid] = payload
    REPORT_CACHE_TS[rid] = time.time()
    return rid


def _cache_get(rid: str) -> dict | None:
    _cache_cleanup()
    if rid in REPORT_CACHE and rid in REPORT_CACHE_TS:
        # TTL内なら返す
        if time.time() - REPORT_CACHE_TS[rid] <= CACHE_TTL_SECONDS:
            return REPORT_CACHE[rid]
        # TTL切れ
        REPORT_CACHE.pop(rid, None)
        REPORT_CACHE_TS.pop(rid, None)
    return None


# =========================
# API: company report (NO DATA RETURN)
# =========================
@app.post("/api/company/report")
def post_company_report(req: CompanyRequest):
    _, result = _create_report(req.name, req.student_no)

    # error だけは返していい（中身ではない）
    if isinstance(result, dict) and result.get("error"):
        return {"error": result["error"]}

    request_id = _cache_put(result)

    # ★ 中身を返さない：IDだけ返す
    return {"request_id": request_id}


@app.post("/api/company/report/result")
def post_company_report_result(req: CompanyResultRequest):
    data = _cache_get(req.request_id)
    if not data:
        raise HTTPException(status_code=404, detail="not found or expired")

    interviews = data.get("interviews") or []

    return {
        "company": data.get("company", ""),
        "report": data.get("report", ""),
        "records": [
            {
                "id": (r.get("id") or ""),   # public_id
                "title": r.get("title", ""),
                "year": r.get("year", ""),
                "term": r.get("term", ""),
                "status": r.get("status", ""),
                "type": r.get("type", ""),
                "start_datetime": r.get("start_datetime", ""),

                # ★ 最短で詳細もここで返す（フロントの詳細API不要にできる）
                "questions": r.get("questions", []),
                "memo": r.get("memo", ""),
                "question_content": r.get("question_content", ""),
            }
            for r in interviews
        ],
    }

# =========================
# 互換: /company も同じ挙動にする（うっかり全文返し防止）
# =========================
@app.post("/company")
def post_company(req: CompanyRequest):
    _, result = _create_report(req.name, req.student_no)
    if isinstance(result, dict) and result.get("error"):
        return {"error": result["error"]}
    request_id = _cache_put(result)
    return {"request_id": request_id}


@app.get("/company/result")
def get_company_result(request_id: str = Query(...)):
    data = _cache_get(request_id)
    if not data:
        raise HTTPException(status_code=404, detail="not found or expired")
    return data


# =========================
# Interview detail
# =========================
def _fetch_interview_detail(report_id: str):
    rid = str(report_id or "").strip()
    if not rid:
        return {"error": "report_id が空です"}

    try:
        df = load_report_df_normalized()
    except Exception as e:
        return {"error": f"report_t_all.csv の読み込みに失敗しました: {e}", "report_id": rid}

    col_report_id = "レポートID"
    col_content = "面接内容"

    if col_report_id not in df.columns:
        return {"error": f"CSVに '{col_report_id}' 列がありません", "report_id": rid}

    hit = df[df[col_report_id].astype(str).str.strip() == rid]
    if hit.empty:
        return {"error": "not found", "report_id": rid}

    row = hit.iloc[0]
    interview_text = str(row.get(col_content, "") or "").strip()

    return {
        "report_id": rid,
        "question_content": interview_text,
        "questions": [],
        "memo": "",
    }


@app.get("/api/interview/detail")
def get_interview_detail(report_id: str = Query(..., description="レポートID（例: P20233026）")):
    return _fetch_interview_detail(report_id)


@app.post("/api/interview/detail")
def post_interview_detail(req: InterviewDetailRequest):
    return _fetch_interview_detail(req.report_id)


# =========================
# Suggest
# =========================
@app.post("/api/company/suggest", response_model=SuggestResponseCompat)
def api_company_suggest(body: SuggestRequest):
    keyword = (body.keyword or "").strip()
    if not keyword:
        return {"candidates": [], "suggestions": []}

    try:
        df = load_summary_df()
    except Exception:
        return {"candidates": [], "suggestions": []}

    if "company_name" not in df.columns:
        return {"candidates": [], "suggestions": []}

    lower = keyword.lower()
    names = df["company_name"].dropna().drop_duplicates().astype(str).tolist()

    prefix_hits = [n for n in names if n.lower().startswith(lower)]
    contains_hits = [n for n in names if lower in n.lower() and n not in prefix_hits]

    out = (prefix_hits + contains_hits)[:15]
    return {"candidates": out, "suggestions": out}


@app.post("/company_suggest", response_model=SuggestResponseCompat)
def company_suggest(body: SuggestRequestCompat):
    q = (body.q or body.keyword or "").strip()
    if not q:
        return {"candidates": [], "suggestions": []}

    try:
        df = load_summary_df()
    except Exception:
        return {"candidates": [], "suggestions": []}

    if "company_name" not in df.columns:
        return {"candidates": [], "suggestions": []}

    lower = q.lower()
    names = df["company_name"].dropna().drop_duplicates().astype(str).tolist()

    prefix_hits = [n for n in names if n.lower().startswith(lower)]
    contains_hits = [n for n in names if lower in n.lower() and n not in prefix_hits]

    out = (prefix_hits + contains_hits)[:15]
    return {"candidates": out, "suggestions": out}
