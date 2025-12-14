# backend/followup/analysis.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple
import numpy as np

# event_kind分類：完全一致
EVENT_BRIEFING = {"説明会_単", "説明会_合", "セミナー", "インターン"}
EVENT_INTERVIEW = {"試験_面接"}
EVENT_TEST = {"試験_適正", "試験_他"}
EVENT_OFFER = {"内定後活動", "内定式"}

@dataclass
class StudentAgg:
    user_no: str
    user_name: str
    email: str
    class_no: str
    course_class: str
    events_count: int
    briefing_count: int
    interview_count: int
    offer_flag: bool
    first_event: Optional[datetime]
    last_event: Optional[datetime]
    gaps_days: List[int]
    last_gap_days: Optional[int]
    two_week_violation_rate: float
    interview_rate: float
    inactivity_days: int
    start_delay_days: int

    # 新規追加: イベント別の最初の実施日時
    briefing_first_event: Optional[datetime] = None
    """最初に実施した説明会系イベントの日時。存在しなければ None。"""
    interview_first_event: Optional[datetime] = None
    """最初に実施した面接系イベントの日時。存在しなければ None。"""

def academic_year_range(academic_year_start: int, tz: str = "Asia/Tokyo") -> Tuple[datetime, datetime]:
    z = ZoneInfo(tz)
    start = datetime(academic_year_start, 4, 1, tzinfo=z)
    end = datetime(academic_year_start + 1, 4, 1, tzinfo=z)
    return start, end

def _median_date(dts: List[datetime], tz: str = "Asia/Tokyo") -> Optional[datetime]:
    if not dts:
        return None
    z = ZoneInfo(tz)
    ords = np.array([dt.astimezone(z).date().toordinal() for dt in dts], dtype=float)
    med = float(np.median(ords))
    return datetime.fromordinal(int(round(med))).replace(tzinfo=z)

def _deviation(values: List[float]) -> List[float]:
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return []
    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=0))
    if sd == 0.0:
        return [50.0 for _ in values]
    return [50.0 + 10.0 * ((v - mu) / sd) for v in values]

def build_student_aggs(users: List[dict], reports: List[dict], year_start: datetime, now_dt: datetime) -> Dict[str, StudentAgg]:
    by_user: Dict[str, List[dict]] = {}
    for r in reports:
        by_user.setdefault(r["user_no"], []).append(r)

    aggs: Dict[str, StudentAgg] = {}
    for u in users:
        user_no = u["user_no"]
        reps = sorted(by_user.get(user_no, []), key=lambda x: x["start_dateTime"])
        reps = [x for x in reps if x.get("event_kind") != "面談"]

        events_count = len(reps)
        briefing_count = sum(1 for x in reps if x["event_kind"] in EVENT_BRIEFING)
        interview_count = sum(1 for x in reps if x["event_kind"] in EVENT_INTERVIEW)

        # 最初の説明会・面接イベントを抽出
        briefing_first: Optional[datetime] = None
        interview_first: Optional[datetime] = None
        for ev in reps:
            kind = ev.get("event_kind")
            if (kind in EVENT_BRIEFING) and briefing_first is None:
                briefing_first = ev["start_dateTime"]
            if (kind in EVENT_INTERVIEW) and interview_first is None:
                interview_first = ev["start_dateTime"]
            if briefing_first is not None and interview_first is not None:
                break

        # 内定辞退は内定扱いになりません。
        offer_flag = any(
            (x["event_kind"] in EVENT_OFFER) or ((x.get("result_kind") or "") == "内定")
            for x in reps
        )

        first_event = reps[0]["start_dateTime"] if reps else None
        last_event = reps[-1]["start_dateTime"] if reps else None

        gaps: List[int] = []
        for i in range(1, len(reps)):
            d = reps[i]["start_dateTime"].date() - reps[i - 1]["start_dateTime"].date()
            gaps.append(int(d.days))
        last_gap = gaps[-1] if gaps else None

        vio = sum(1 for g in gaps if g > 14)
        two_week_violation_rate = (vio / len(gaps)) if gaps else 0.0
        interview_rate = interview_count / max(briefing_count, 1)

        if last_event:
            inactivity_days = int((now_dt.date() - last_event.date()).days)
        else:
            inactivity_days = int((now_dt.date() - year_start.date()).days)

        aggs[user_no] = StudentAgg(
            user_no=user_no,
            user_name=u.get("user_name", ""),
            email=u.get("email", ""),
            class_no=u.get("class_no", ""),
            course_class=u.get("course_class") or (u.get("class_no", "")[:1]),
            events_count=events_count,
            briefing_count=briefing_count,
            interview_count=interview_count,
            offer_flag=offer_flag,
            first_event=first_event,
            last_event=last_event,
            gaps_days=gaps,
            last_gap_days=last_gap,
            two_week_violation_rate=two_week_violation_rate,
            interview_rate=interview_rate,
            inactivity_days=inactivity_days,
            start_delay_days=0,
            briefing_first_event=briefing_first,
            interview_first_event=interview_first,
        )
    return aggs

def compute_followup(aggs: Dict[str, StudentAgg], academic_year_start: int, now_dt: datetime) -> dict:
    year_start, _ = academic_year_range(academic_year_start, tz="Asia/Tokyo")
    groups: Dict[str, List[StudentAgg]] = {}
    for s in aggs.values():
        groups.setdefault(s.course_class, []).append(s)

    group_meta: Dict[str, dict] = {}
    students_out: List[dict] = []

    for course, items in groups.items():
        start_dates = [x.first_event for x in items if x.first_event is not None]
        t0 = _median_date(start_dates, tz="Asia/Tokyo")

        briefing_rel_days: List[int] = []
        interview_rel_days: List[int] = []
        for x in items:
            if t0 is None:
                x.start_delay_days = 0
            elif x.first_event:
                x.start_delay_days = int((x.first_event.date() - t0.date()).days)
            else:
                x.start_delay_days = int((now_dt.date() - t0.date()).days)

            if x.briefing_first_event is not None:
                briefing_rel_days.append((x.briefing_first_event.date() - year_start.date()).days)
            if x.interview_first_event is not None:
                interview_rel_days.append((x.interview_first_event.date() - year_start.date()).days)

        baseline_briefing = int(float(np.median(np.array(briefing_rel_days, dtype=float)))) if briefing_rel_days else None
        baseline_interview = int(float(np.median(np.array(interview_rel_days, dtype=float)))) if interview_rel_days else None

        inactivity_list = [float(x.inactivity_days) for x in items]
        q90 = float(np.percentile(np.array(inactivity_list, dtype=float), 90)) if inactivity_list else 0.0

        def excluded_good(x: StudentAgg) -> bool:
            if x.offer_flag:
                return True
            ok_run = 0
            best = 0
            for g in x.gaps_days:
                if g <= 14:
                    ok_run += 1
                    best = max(best, ok_run)
                else:
                    ok_run = 0
            if best >= 2:
                return True
            if x.last_gap_days is not None and x.last_gap_days <= 14:
                return True
            return False

        def followup_candidate(x: StudentAgg) -> bool:
            if x.offer_flag:
                return False
            if x.interview_count != 0:
                return False
            return (x.briefing_count == 0) or (x.briefing_count < 5)

        def stagnation(x: StudentAgg) -> bool:
            if x.offer_flag:
                return False
            if x.inactivity_days < q90:
                return False
            if x.last_event and (now_dt.date() - x.last_event.date()).days <= 14:
                return False
            if x.last_gap_days is not None and x.last_gap_days <= 14:
                return False
            return True

        m1 = [float(x.inactivity_days) for x in items]
        m2 = [float(x.start_delay_days) for x in items]
        m3 = [float(1.0 - x.interview_rate) for x in items]
        m4 = [float(-x.events_count) for x in items]
        m5 = [float(x.two_week_violation_rate) for x in items]
        d1, d2, d3, d4, d5 = _deviation(m1), _deviation(m2), _deviation(m3), _deviation(m4), _deviation(m5)

        for i, x in enumerate(items):
            stage_penalty = 25.0 if x.events_count == 0 else 0.0
            stagnation_bonus = 20.0 if stagnation(x) else 0.0
            score = (
                stage_penalty
                + stagnation_bonus
                + 1.8 * d1[i]
                + 1.0 * d2[i]
                + 0.9 * d3[i]
                + 0.7 * d4[i]
                + 0.6 * d5[i]
            )

            briefing_rel_day: Optional[int] = None
            if x.briefing_first_event is not None:
                briefing_rel_day = (x.briefing_first_event.date() - year_start.date()).days
            interview_rel_day: Optional[int] = None
            if x.interview_first_event is not None:
                interview_rel_day = (x.interview_first_event.date() - year_start.date()).days

            briefing_delay_days: Optional[int] = None
            briefing_delay_percent: Optional[float] = None
            if baseline_briefing is not None and briefing_rel_day is not None:
                briefing_delay_days = briefing_rel_day - baseline_briefing
                if baseline_briefing > 0:
                    raw_pct = (briefing_delay_days / baseline_briefing) * 100.0
                    briefing_delay_percent = raw_pct if raw_pct > 0 else 0.0

            interview_delay_days: Optional[int] = None
            interview_delay_percent: Optional[float] = None
            if baseline_interview is not None and interview_rel_day is not None:
                interview_delay_days = interview_rel_day - baseline_interview
                if baseline_interview > 0:
                    raw_pct = (interview_delay_days / baseline_interview) * 100.0
                    interview_delay_percent = raw_pct if raw_pct > 0 else 0.0

            briefing_status = judge_phase_status(
                delay_days=briefing_delay_days,
                delay_percent=briefing_delay_percent,
                not_started=(x.briefing_first_event is None),
            )
            interview_status = judge_phase_status(
                delay_days=interview_delay_days,
                delay_percent=interview_delay_percent,
                not_started=(x.interview_first_event is None),
            )

            severity_map = {"ok": 0, "warn": 1, "danger": 2}
            worst = None
            for name, status in (("説明会", briefing_status), ("面接", interview_status)):
                if status["status"] == "not_started":
                    sev = 2
                    pct = 100.0
                else:
                    sev = severity_map.get(status.get("level", "ok"), 0)
                    pct = float(status.get("delay_percent") or 0.0)
                if worst is None or sev > worst["sev"] or (sev == worst["sev"] and pct > worst["pct"]):
                    worst = {"name": name, "sev": sev, "pct": pct, "status": status["status"], "level": status.get("level")}

            if worst["status"] == "not_started":
                overall_level = "danger"
                overall_reason = f"{worst['name']}未開始"
            else:
                overall_level = worst["level"] or "ok"
                if overall_level == "ok":
                    overall_reason = "基準内"
                else:
                    overall_reason = f"{worst['name']}遅れ度{int(round(worst['pct']))}%"

            students_out.append({
                "user_no": x.user_no,
                "user_name": x.user_name,
                "email": x.email,
                "class_no": x.class_no,
                "course_class": x.course_class,
                "events_count": x.events_count,
                "briefing_count": x.briefing_count,
                "interview_count": x.interview_count,
                "offer_flag": x.offer_flag,
                "first_event": x.first_event.isoformat() if x.first_event else None,
                "last_event": x.last_event.isoformat() if x.last_event else None,
                "inactivity_days": x.inactivity_days,
                "start_delay_days": x.start_delay_days,
                "two_week_violation_rate": x.two_week_violation_rate,
                "interview_rate": x.interview_rate,
                "dev_inactivity": d1[i],
                "dev_start_delay": d2[i],
                "dev_risk_e": d3[i],
                "dev_events": d4[i],
                "dev_two_week_violation": d5[i],
                "excluded_good": excluded_good(x),
                "followup_candidate": followup_candidate(x),
                "stagnation": stagnation(x),
                "priority_score": score,

                # ===== B案: UI向け完成形 =====
                "briefing_first_date": x.briefing_first_event.date().isoformat() if x.briefing_first_event else None,
                "interview_first_date": x.interview_first_event.date().isoformat() if x.interview_first_event else None,
                "briefing_delay_days": briefing_delay_days,
                "briefing_delay_percent": briefing_delay_percent,
                "interview_delay_days": interview_delay_days,
                "interview_delay_percent": interview_delay_percent,
                "baseline_briefing_rel_day": baseline_briefing,
                "baseline_interview_rel_day": baseline_interview,
                "briefing_status": briefing_status,
                "interview_status": interview_status,
                "overall_level": overall_level,
                "overall_reason": overall_reason,

                # 旧API互換
                "delay_interview_days": interview_delay_days,

                # === classification ===
                # 緊急対応: 説明会も面接も両方危険(not_started または danger)
                # 要フォロー: 危険 (danger/warn) だが緊急ではない
                # 順調: overall_level が ok
                "classification": None,  # placeholder; will be filled below
            })

        # === 後処理: classification を決定する ===
        # classification は "urgent" "followup" "ok" のいずれか
        for rec in students_out:
            # rec には briefing_status / interview_status / overall_level が含まれている
            bs = rec.get("briefing_status") or {}
            ins = rec.get("interview_status") or {}
            # not_started は status=="not_started" かつ level=="danger" に相当
            def is_danger(stat):
                if not stat:
                    return False
                # not_started or danger level
                if stat.get("status") == "not_started":
                    return True
                return stat.get("level") == "danger"

            urgent = is_danger(bs) and is_danger(ins)
            if urgent:
                rec["classification"] = "urgent"
            else:
                overall = rec.get("overall_level") or "ok"
                if overall in ("danger", "warn"):
                    rec["classification"] = "followup"
                else:
                    rec["classification"] = "ok"

        group_meta[course] = {
            "academic_year_start": academic_year_start,
            "t0": t0.date().isoformat() if t0 else None,
            "q90_inactivity_days": q90,
            "baseline_briefing_rel_day": baseline_briefing,
            "baseline_interview_rel_day": baseline_interview,
        }

    students_out.sort(key=lambda r: r["priority_score"], reverse=True)
    return {"group_meta": group_meta, "students": students_out}

def judge_phase_status(
    delay_days: int | None,
    delay_percent: float | None,
    *,
    not_started: bool = False,
):
    if not_started:
        return {
            "status": "not_started",
            "level": "danger",
        }

    delay_days = delay_days or 0
    delay_percent = delay_percent or 0.0

    if delay_percent >= 90 or delay_days >= 10:
        level = "danger"
    elif delay_percent >= 70:
        level = "warn"
    else:
        level = "ok"

    return {
        "status": "started",
        "level": level,
        "delay_days": delay_days,
        "delay_percent": delay_percent,
    }
