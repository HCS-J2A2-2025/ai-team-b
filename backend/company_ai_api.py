import os
import time
import uuid
import re
import pandas as pd
from pathlib import Path

import pandas as pd
import cache_api as capi

from cache_api import router as cache_router
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from analysis import build_student_analysis, suggest_student_ids
from company_summary_batch import generate_student_ai_summary
# 既存ルーター
from csv_api import router as csv_router
#from followup_api import router as followup_router

# =========================
# AI switches (NO .env)
# =========================
USE_LEFT_AI = True     # ← 左の企業AI要約を使うなら True
USE_RIGHT_AI = True    # ← 右の面接カードをAIで作るなら True


# company_summary_batch を「モジュールとして」import してスイッチ反映する
import company_summary_batch as csb

# 必要関数を取り込む（csb. を使ってもOK）
# report_t_all.csv の列名ゆれ/BOM/空白を吸収する
from company_summary_batch import (
    generate_detailed_report,
    build_interview_records_for_company,
    get_latest_interview_texts,
    get_company_names_cached,
    load_report_df as load_report_df_normalized,
    summarize_company,
    summarize_company_with_error,
    generate_student_ai_summary,
)

# ここが超重要：FastAPI側のスイッチを company_summary_batch 側へ反映
# （あなたが前に作った完成版 company_summary_batch.py が ENABLE_LEFT_AI / ENABLE_RIGHT_AI を持っている前提）
csb.ENABLE_LEFT_AI = bool(USE_LEFT_AI)
csb.ENABLE_RIGHT_AI = bool(USE_RIGHT_AI)

# =========================
# FastAPI (docs OFF)
# =========================
app = FastAPI()  # ← search_company_api.pyのためにdocs_urlを動かす

# ルーター登録
app.include_router(cache_router, prefix="/api/cache")
app.include_router(csv_router)
# app.include_router(followup_router)

# CORS
app.add_middleware( CORSMiddleware, allow_origins=[
    "http://10.11.33.225:8000",
    "http://10.11.33.225:3000",
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


class StudentAnalysisRequest(BaseModel):
    student_id: str
    use_ai: bool = True


class CompanyValidateRequest(BaseModel):
    name: str


# =========================
# helpers
# =========================
def _normalize_company_name(s: str) -> str:
    return re.sub(r"\s+", "", s or "").strip()


def _is_symbol_only(s: str) -> bool:
    return not re.search(r"[A-Za-z0-9ぁ-んァ-ン一-龥]", s or "")


SUGGEST_EVENT_KINDS = {"EXAM_INTERVIEW", "EXAM_APTITUDE"}
_suggest_names_cache: list[str] = []
_suggest_names_cache_mtime_ns: int | None = None


def _get_source_csv_mtime_ns() -> int | None:
    try:
        p = Path(csb.INPUT_CSV)
        return p.stat().st_mtime_ns if p.exists() else None
    except Exception:
        return None




def _get_company_names_from_report() -> list[str]:
    global _suggest_names_cache, _suggest_names_cache_mtime_ns

    mtime_ns = _get_source_csv_mtime_ns()
    if _suggest_names_cache and _suggest_names_cache_mtime_ns == mtime_ns:
        return _suggest_names_cache

    try:
        df = load_report_df_normalized()
    except Exception as e:
        print("[WARN] load_report_df_normalized failed:", e)
        return []

    col_candidates = ["企業名", "company_name"]
    target_col = next((c for c in col_candidates if c in df.columns), None)
    if not target_col:
        return []

    col_event = "イベント種別" if "イベント種別" in df.columns else "event_kind"
    if col_event in df.columns:
        event_kind = df[col_event].astype(str).str.strip().str.upper()
        df = df[event_kind.isin(SUGGEST_EVENT_KINDS)]
        if df.empty:
            _suggest_names_cache = []
            _suggest_names_cache_mtime_ns = mtime_ns
            return []

    names = (
        df[target_col]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    _suggest_names_cache = names
    _suggest_names_cache_mtime_ns = mtime_ns
    return names


def _try_get_company_from_json_cache(name: str) -> dict | None:
    """
    cache_updater が生成した company_cache_all.json から company を探して返す。
    found は company単位の dict: { company, report, records }
    """
    raw = (name or "").strip()
    if not raw:
        return None

    try:
        data = capi._load_all_cache_or_raise()
        comps = capi._get_companies_map(data)
        found, _ = capi._lookup_company(comps, raw)
        if found is None or not isinstance(found, dict):
            return None
        return found
    except Exception as e:
        # キャッシュがない/壊れてる等は「落とさず」オンデマンドへ
        print("[WARN] json cache read failed:", e)
        return None


# =========================
# Report build (internal)
# =========================
def _create_report(name: str, student_no: str | None = None):
    keyword = str(name or "").strip()
    if not keyword:
        return None, {"error": "企業名が空です"}

    # =========================================================
    # ✅ まず JSON キャッシュを参照（cache_updater 出力）
    # =========================================================
    cached = _try_get_company_from_json_cache(keyword)
    if cached is not None:
        company_name = str(cached.get("company") or keyword).strip()
        report = str(cached.get("report") or "").strip()

        # cache_updater は "records" で保存
        cached_records = cached.get("records", [])
        if not isinstance(cached_records, list):
            cached_records = []

        # student_no が無いならキャッシュだけで完結
        if student_no is None:
            return None, {
                "company": company_name,
                "report": report if USE_LEFT_AI else "",
                "interviews": cached_records,  # API内部は interviews に統一
                "texts": [],  # cache_updater は texts を保存していないので空
                "source": "json_cache",
            }

        # student_no 指定がある場合：
        # - 左はキャッシュ利用（高速）
        # - 右は個人指定で作り直す（企業全体recordsだと混ざるため）
        csb.ENABLE_LEFT_AI = bool(USE_LEFT_AI)
        csb.ENABLE_RIGHT_AI = bool(USE_RIGHT_AI)

        try:
            interviews = build_interview_records_for_company(company_name, student_no)
        except Exception as e:
            print("[WARN] build_interview_records_for_company failed:", e)
            interviews = []

        return None, {
            "company": company_name,
            "report": report if USE_LEFT_AI else "",
            "interviews": interviews,
            "texts": [],
            "source": "json_cache+student_filter",
        }

    # =========================================================
    # ❌ キャッシュが無い → 従来どおり CSV から生成
    # =========================================================
    try:
        df = load_report_df_normalized()
    except Exception as e:
        return None, {"error": f"report_t_all.csv の読み込みに失敗しました: {e}"}

    col_company = "企業名"
    if col_company not in df.columns:
        return None, {"error": f"report_t_all.csv に {col_company} 列がありません"}

    # 正規化（完全一致）
    norm_input = _normalize_company_name(keyword)

    df = df.copy()
    df["__norm_name"] = df[col_company].astype(str).apply(_normalize_company_name)

    hit = df[df["__norm_name"] == norm_input]
    if hit.empty:
        return None, {"error": "データに存在しません（完全一致が必要です）"}

    df_company = df[df["__norm_name"] == norm_input].copy()
    df_company = df_company.drop(columns=["__norm_name"])

    # summarize_company_with_error がある前提（あなたの import に合わせる）
    summary_row_dict, summary_err = summarize_company_with_error(df_company)
    if not summary_row_dict:
        reason = summary_err or "不明な理由"
        return None, {"error": f"この企業のサマリ生成に失敗しました: {reason}"}

    row = pd.Series(summary_row_dict)
    company_name = str(row.get("company_name", "") or "").strip()
    if not company_name:
        return None, {"error": "company_name が空です"}

    # スイッチ反映
    csb.ENABLE_LEFT_AI = bool(USE_LEFT_AI)
    csb.ENABLE_RIGHT_AI = bool(USE_RIGHT_AI)

    # 左：AI要約
    report = ""
    if USE_LEFT_AI:
        try:
            report = generate_detailed_report(row) or ""
        except Exception as e:
            print("[WARN] generate_detailed_report failed:", e)
            report = ""
        if isinstance(report, str) and report.startswith("[ERROR]"):
            return None, {"error": f"AI要約に失敗しました: {report}"}

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
        "source": "on_demand",
    }



# =========================
# In-memory cache (TTL)
# =========================
REPORT_CACHE: dict[str, dict] = {}
REPORT_CACHE_TS: dict[str, float] = {}

CACHE_TTL_SECONDS = 300

def _cache_cleanup() -> None:
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
    ts = REPORT_CACHE_TS.get(rid)
    if ts is None:
        return None
    if time.time() - ts > CACHE_TTL_SECONDS:
        REPORT_CACHE.pop(rid, None)
        REPORT_CACHE_TS.pop(rid, None)
        return None
    return REPORT_CACHE.get(rid)


# =========================
# API: company report (NO DATA RETURN)
# =========================
@app.post("/api/company/report")
def post_company_report(req: CompanyRequest):
    _, result = _create_report(req.name, req.student_no)

    if isinstance(result, dict) and result.get("error"):
        return {"error": result["error"]}

    request_id = _cache_put(result)
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
                "id": (r.get("id") or ""),
                "title": r.get("title", ""),
                "year": r.get("year", ""),
                "term": r.get("term", ""),
                "status": r.get("status", ""),
                "type": r.get("type", ""),
                "start_datetime": r.get("start_datetime", ""),
                "questions": r.get("questions", []),
                "memo": r.get("memo", ""),
                "question_content": r.get("question_content", ""),
            }
            for r in interviews
        ],
    }


# =========================
# Compat endpoints
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

    names = _get_company_names_from_report()
    if not names:
        return {"candidates": [], "suggestions": []}

    lower = keyword.lower()

    prefix_hits = [n for n in names if n.lower().startswith(lower)]
    contains_hits = [n for n in names if lower in n.lower() and n not in prefix_hits]

    out = (prefix_hits + contains_hits)[:15]
    return {"candidates": out, "suggestions": out}



# =========================
# Student analysis
# =========================
@app.get("/api/student/analysis")
def api_student_analysis(student_id: str | None = Query(default=None)):
    data = build_student_analysis(
        student_id=student_id,
        use_ai=False,  # GETではAI絶対OFF（方針通り）
    )

    if student_id:
        sid = str(student_id).strip()
        return {"student_id": sid, "data": data.get(sid, {})}

    return {"data": data}


@app.post("/api/student/analysis")
def api_student_analysis_post(req: StudentAnalysisRequest):
    data = build_student_analysis(
        student_id=req.student_id,
        use_ai=bool(req.use_ai),
    )
    sid = str(req.student_id).strip()
    return {"student_id": sid, "data": data.get(sid, {})}


class StudentSuggestRequest(BaseModel):
    keyword: str


@app.post("/api/student/suggest")
def api_student_suggest(req: StudentSuggestRequest):
    candidates = suggest_student_ids(req.keyword, limit=10)
    return {"candidates": candidates}


# =========================
# Company validate
# =========================
@app.post("/api/company/validate")
def post_company_validate(req: CompanyValidateRequest):
    keyword = str(req.name or "").strip()
    if not keyword:
        return {"ok": False, "error": "企業名が空です"}

    if _is_symbol_only(keyword):
        return {"ok": False, "error": "企業名に文字が含まれていません"}

    # ✅ 追加：JSONキャッシュ優先
    cached = _try_get_company_from_json_cache(keyword)
    if cached is not None:
        return {
            "ok": True,
            "company": str(cached.get("company") or keyword).strip(),
            "source": "json_cache",
        }

    # ---- キャッシュに無い場合だけCSVで確認 ----
    try:
        df = load_report_df_normalized()
    except Exception as e:
        return {"ok": False, "error": f"report_t_all.csv の読み込みに失敗しました: {e}"}

    col_company = "企業名"
    if col_company not in df.columns:
        return {"ok": False, "error": f"report_t_all.csv に {col_company} 列がありません"}

    norm_input = _normalize_company_name(keyword)

    df = df.copy()
    df["__norm_name"] = df[col_company].astype(str).apply(_normalize_company_name)

    hit = df[df["__norm_name"] == norm_input]
    if hit.empty:
        return {"ok": False, "error": "データに存在しません（完全一致が必要です）"}

    matched = hit.iloc[0][col_company]
    return {"ok": True, "company": str(matched).strip(), "source": "csv"}

@app.get("/__routes")
def __routes():
    return sorted([getattr(r, "path", "") for r in app.routes])

