from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db import get_conn
from followup.analysis import academic_year_range, build_student_aggs, compute_followup

router = APIRouter(prefix="/followup", tags=["followup"])
logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")

# 修業年限（年）
COURSE_DURATION = {"J": 2, "S": 3, "R": 4}


def _require_teacher_or_admin(x_role: str | None):
    role = (x_role or "").strip().lower()
    if role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")


class AnalysisFilter(BaseModel):
    academic_year_start: int = Field(..., description="例: 2025は2025/04/01〜2026/03/31")

    # 選択された学科（J/S/R）
    course_classes: List[str] = Field(default_factory=list)
    # 選択されたクラス番号プレフィックス（例: j2, s3）
    class_nos: List[str] = Field(default_factory=list)

    # 対象外（順調）も表示
    # true: classification == 'ok' だけ表示
    include_excluded_good: bool = False
    # 要フォロー入口のみ
    # true: classification == 'followup' だけ表示
    only_followup_candidate: bool = False


class ExportRequest(AnalysisFilter):
    export_kind: str = Field(default="all", pattern="^(inactive|followup|all)$")


class PhaseStatus(BaseModel):
    status: Literal["not_started", "started"]
    level: Literal["danger", "warn", "ok"]
    delay_days: int | None = None
    delay_percent: float | None = None


class StudentOut(BaseModel):
    user_no: str
    user_name: Optional[str] = None
    email: Optional[str] = None
    course_class: str
    class_no: str

    # ===== B案: UIが欲しい完成形 =====
    overall_level: Literal["danger", "warn", "ok"]
    overall_reason: str

    briefing_first_date: Optional[str] = None
    interview_first_date: Optional[str] = None

    briefing_delay_days: Optional[int] = None
    briefing_delay_percent: Optional[float] = None
    interview_delay_days: Optional[int] = None
    interview_delay_percent: Optional[float] = None

    baseline_briefing_rel_day: Optional[int] = None
    baseline_interview_rel_day: Optional[int] = None

    briefing_status: PhaseStatus
    interview_status: PhaseStatus

    # 画面で使ってる “実数” 系
    events_count: Optional[int] = None
    briefing_count: Optional[int] = None
    interview_count: Optional[int] = None
    inactivity_days: Optional[int] = None
    start_delay_days: Optional[int] = None
    two_week_violation_rate: Optional[float] = None

    # 偏差
    dev_inactivity: Optional[float] = None
    dev_start_delay: Optional[float] = None
    dev_risk_e: Optional[float] = None
    dev_events: Optional[float] = None
    dev_two_week_violation: Optional[float] = None

    excluded_good: Optional[bool] = None
    followup_candidate: Optional[bool] = None

    # 便利：並び替え・デバッグ用（フロントで使わなければ無視される）
    priority_score: Optional[float] = None

    # 分類: 'urgent' (緊急対応), 'followup' (要フォロー), 'ok' (順調)
    classification: Literal['urgent', 'followup', 'ok']


class FollowupAnalysisResponse(BaseModel):
    group_meta: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    students: List[StudentOut] = Field(default_factory=list)


def _fetch_users(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                user_no,
                NULL::text AS email,
                class_no,
                UPPER(LEFT(class_no, 1)) AS course_class,
                user_name,
                authority,
                status
            FROM public.user_m
            WHERE authority='student' AND status='valid';
            """
        )
        return cur.fetchall()


def _fetch_reports(conn, *, time_min: datetime | None = None, time_max: datetime | None = None):
    """
    report_t を取得。time_min/time_max を指定した場合は start_datetime で範囲絞り。
    """
    with conn.cursor() as cur:
        if time_min and time_max:
            cur.execute(
                """
                SELECT
                    user_no,
                    class_no,
                    user_name,
                    start_datetime AS "start_dateTime",
                    end_datetime   AS "end_dateTime",
                    company_name,
                    event_kind,
                    result_kind
                FROM public.report_t
                WHERE start_datetime >= %s AND start_datetime < %s
                """,
                (time_min, time_max),
            )
        else:
            cur.execute(
                """
                SELECT
                    user_no,
                    class_no,
                    user_name,
                    start_datetime AS "start_dateTime",
                    end_datetime   AS "end_dateTime",
                    company_name,
                    event_kind,
                    result_kind
                FROM public.report_t
                """
            )
        return cur.fetchall()


def _iter_csv_rows(rows: List[Dict[str, Any]]):
    fieldnames = [
        "user_no", "user_name", "class_no", "course_class",
        "overall_level", "overall_reason",
        "briefing_first_date", "interview_first_date",
        "baseline_briefing_rel_day", "baseline_interview_rel_day",
        "briefing_delay_days", "briefing_delay_percent",
        "interview_delay_days", "interview_delay_percent",
        "events_count", "briefing_count", "interview_count",
        "inactivity_days", "start_delay_days", "two_week_violation_rate",
        "dev_inactivity", "dev_start_delay", "dev_risk_e", "dev_events", "dev_two_week_violation",
        "excluded_good", "followup_candidate",
        "priority_score",
        "classification",
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    for r in rows:
        writer.writerow(r)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)


def _enroll_year_from_user_no(user_no: Any) -> Optional[int]:
    """
    user_no先頭4桁=入学年（例: 2024xxxx）
    """
    s = str(user_no or "").strip()
    if len(s) < 4:
        return None
    head = s[:4]
    if not head.isdigit():
        return None
    return int(head)


def _is_target_student_for_year(*, academic_year_start: int, user_no: Any, course_class: Any) -> bool:
    """
    対象学生の判定（バックエンドで固定）

    - S/R: 「卒業学年」と「そのひとつ前」のみ（低学年除外）
    - J  : 例外で「今年度1年生も表示」（Jは2年制なので結果的に Y or Y-1）
    """
    enroll_year = _enroll_year_from_user_no(user_no)
    if enroll_year is None:
        return False

    c = (str(course_class or "")).strip().upper()
    dur = COURSE_DURATION.get(c)
    if not dur:
        return False

    y = academic_year_start

    if c == "J":
        return enroll_year in (y, y - 1)

    final_enroll = y - (dur - 1)
    prev_enroll = y - (dur - 2)
    return enroll_year in (final_enroll, prev_enroll)


def _apply_ui_filters(students: List[dict], f: AnalysisFilter) -> List[dict]:
    # 学科
    if f.course_classes:
        allowed = set(map(str, f.course_classes))
        students = [s for s in students if str(s.get("course_class")) in allowed]
    # クラス番号プレフィックス
    if f.class_nos:
        allowed_prefixes = set(map(str, f.class_nos))
        students = [s for s in students if any(str(s.get("class_no", "")).lower().startswith(p.lower()) for p in allowed_prefixes)]

    # 分類によるフィルタ
    # only_followup_candidate: followup だけ
    # include_excluded_good: ok だけ
    # 両方false: urgentとfollowup
    # 両方true: followup と ok
    if f.only_followup_candidate and not f.include_excluded_good:
        students = [s for s in students if s.get("classification") == "followup"]
    elif f.include_excluded_good and not f.only_followup_candidate:
        students = [s for s in students if s.get("classification") == "ok"]
    elif f.include_excluded_good and f.only_followup_candidate:
        students = [s for s in students if s.get("classification") in ("followup", "ok")]
    else:
        students = [s for s in students if s.get("classification") in ("urgent", "followup")]

    return students


PhaseStatus.model_rebuild()
StudentOut.model_rebuild()
FollowupAnalysisResponse.model_rebuild()


@router.post("/analysis", response_model=FollowupAnalysisResponse)
def post_followup_analysis(
    f: AnalysisFilter,
    x_role: str | None = Header(default=None, alias="X-ROLE"),
):
    logger.info("POST /followup/analysis role=%s filters=%s", x_role, f.model_dump())

    try:
        _require_teacher_or_admin(x_role)

        now_dt = datetime.now(JST)
        year_start_dt, _ = academic_year_range(f.academic_year_start, tz="Asia/Tokyo")

        with get_conn() as conn:
            users_all = _fetch_users(conn)
            # ★ report は当年度だけ（4/1〜now）
            reports_year = _fetch_reports(conn, time_min=year_start_dt, time_max=now_dt)

        # ★ 対象学生を “user_no入学年 + course_class” で固定
        target_users = [
            u for u in users_all
            if _is_target_student_for_year(
                academic_year_start=f.academic_year_start,
                user_no=u.get("user_no"),
                course_class=u.get("course_class"),
            )
        ]

        aggs = build_student_aggs(target_users, reports_year, year_start_dt, now_dt)
        out = compute_followup(aggs, f.academic_year_start, now_dt)

        students = out.get("students", [])
        if not isinstance(students, list):
            raise HTTPException(status_code=500, detail="Invalid students format")

        students = _apply_ui_filters(students, f)

        # ===== 二重判定ゼロ：analysis.py が返した完成形をそのまま返す =====
        result_students = [StudentOut(**s) for s in students]

        return FollowupAnalysisResponse(
            group_meta=out.get("group_meta", {}),
            students=result_students,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("followup analysis failed: %s", e)
        raise HTTPException(status_code=500, detail="followup analysis failed") from e


@router.post("/export")
def post_followup_export(
    req: ExportRequest,
    x_role: str | None = Header(default=None, alias="X-ROLE"),
):
    logger.info("POST /followup/export role=%s kind=%s filters=%s", x_role, req.export_kind, req.model_dump())

    try:
        _require_teacher_or_admin(x_role)

        now_dt = datetime.now(JST)
        year_start_dt, _ = academic_year_range(req.academic_year_start, tz="Asia/Tokyo")

        with get_conn() as conn:
            users_all = _fetch_users(conn)
            reports_year = _fetch_reports(conn, time_min=year_start_dt, time_max=now_dt)

        target_users = [
            u for u in users_all
            if _is_target_student_for_year(
                academic_year_start=req.academic_year_start,
                user_no=u.get("user_no"),
                course_class=u.get("course_class"),
            )
        ]

        aggs = build_student_aggs(target_users, reports_year, year_start_dt, now_dt)
        out = compute_followup(aggs, req.academic_year_start, now_dt)

        students = out.get("students", [])
        if not isinstance(students, list):
            raise HTTPException(status_code=500, detail="Invalid students format")

        students = _apply_ui_filters(students, req)

        if req.export_kind == "inactive":
            students = [s for s in students if int(s.get("events_count") or 0) == 0]
        elif req.export_kind == "followup":
            students = [
                s for s in students
                if bool(s.get("followup_candidate", False))
                and int(s.get("events_count") or 0) > 0
            ]

        filename = f"followup_{req.export_kind}_{req.academic_year_start}.csv"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

        return StreamingResponse(
            _iter_csv_rows(students),
            media_type="text/csv; charset=utf-8",
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("followup export failed: %s", e)
        raise HTTPException(status_code=500, detail="followup export failed") from e
