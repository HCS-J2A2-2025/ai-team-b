# seed_generator_jobhunt.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd


# ==========
# 仕様定数（あなたの指定）
# ==========

JST = ZoneInfo("Asia/Tokyo")

EVENT_KINDS = [
    "説明会_単", "説明会_合", "セミナー", "インターン",
    "試験_面接", "試験_適正", "試験_他",
    "内定後活動", "内定式",
    "他",
]
RESULT_KINDS = [
    "結果待ち", "辞退", "継続 (合格)", "不合格",
    "内定", "内定辞退", "他",
]

BRIEFING_KINDS = {"説明会_単", "説明会_合", "セミナー", "インターン"}
TRIAL_KINDS = {"試験_面接", "試験_適正", "試験_他"}
OFFER_KINDS = {"内定後活動", "内定式"}

# duration (minutes)
DURATION_MIN = {
    "説明会_単": 60,
    "説明会_合": 60,
    "セミナー": 60,
    "インターン": 60,
    "試験_適正": 90,
    "試験_面接": 45,
    "試験_他": 30,
    "内定後活動": 60,
    "内定式": 90,
    "他": 30,
}

TIME_SLOTS = [(10, 0), (13, 0), (15, 0)]  # hours, minutes


# ==========
# 学籍番号（PK）ルール
# ==========

COURSE_CODE = {"J": "20", "S": "30", "R": "40"}

# 卒業年度（academic_year_start=Y）に対して「最終学年の入学年」を決める
# J(2年制):入学年=Y, S(3年制):Y-1, R(4年制):Y-2
ADMISSION_YEAR_OFFSET = {"J": 0, "S": -1, "R": -2}

# クラス定義（あなたの指定）
CLASS_BY_COURSE = {
    "J": ["J1A109", "J2A109"],                 # 2クラス
    "S": ["S1A109", "S2A109", "S3A109", "S4A109"],  # 4クラス
    "R": ["R1A109", "R2A109"],                 # 2クラス
}

# 年間200人の配分（あなたの指定）
HEADCOUNT_BY_COURSE = {"J": 50, "S": 60, "R": 90}  # 合計200


# ==========
# 層B：潜在タイプ（混合比）
# ==========

TYPES = ["E", "N", "L", "S", "G", "O"]  # Early, Normal, Late, Stagnant, GateStuck, OverInterview

MIX_RATIO_BY_COURSE = {
    "J": {"E": 0.05, "N": 0.45, "L": 0.20, "S": 0.15, "G": 0.10, "O": 0.05},
    "S": {"E": 0.10, "N": 0.50, "L": 0.15, "S": 0.15, "G": 0.05, "O": 0.05},
    "R": {"E": 0.20, "N": 0.45, "L": 0.05, "S": 0.10, "G": 0.05, "O": 0.15},
}

# 応募企業数：混合ポアソン（タイプ別 λ）、最大6でクリップ
LAMBDA_COMPANIES = {"E": 3.5, "N": 2.5, "L": 1.5, "S": 2.0, "G": 1.0, "O": 4.0}
MAX_COMPANIES = 6

# 面接ステージ数（企業ごと）
INTERVIEW_STAGE_VALUES = [1, 2, 3]
INTERVIEW_STAGE_PROBS = [0.25, 0.45, 0.30]
OVERINTERVIEW_PLUS1_PROB = 0.30  # Oタイプのみ、+1ステージの上乗せ確率
MAX_STAGES = 4  # 現実的制限（一次/二次/最終＋αまで）

# 説明会系：企業ごとに0〜2回（離散分布）
BRIEFING_COUNT_VALUES = [0, 1, 2]
BRIEFING_COUNT_PROBS = [0.30, 0.50, 0.20]

# 試験_適正を挟むか（企業ごと、現実的に0/1）
APTITUDE_PROB = 0.50

# 試験系 result_kind（確率）
# ※「継続(合格)なら次イベント必須」「不合格/辞退ならその企業は終了」
TRIAL_RESULT_VALUES = ["結果待ち", "継続 (合格)", "不合格", "辞退"]
TRIAL_RESULT_PROBS = [0.45, 0.30, 0.20, 0.05]

# 内定（企業の最終ステージでのみ発生）
OFFER_PROB_BY_TYPE = {"E": 0.45, "O": 0.45, "N": 0.30, "L": 0.15, "S": 0.15, "G": 0.15}

# ==========
# 層A：年×学科の就活カレンダー（academic_year_start=Y の期間：Y/04/01〜Y+1/03/31）
# ※あなたの学校の説明と、APIの年度範囲(4/1〜)を両立させるため、
#   J/Sは「翌年2〜4月」、Rは「当年秋〜翌年春」を中心に置く
# ==========

@dataclass(frozen=True)
class CalendarParams:
    # 開始中心日（datetime, JST）
    start_center: datetime
    start_sd_days: float
    # ピーク中心日（datetime, JST）
    peak_center: datetime
    peak_sd_days: float

def _calendar_for(academic_year_start: int, course: str, rng: np.random.Generator) -> CalendarParams:
    """
    academic_year_start=Y → 期間は Y/04/01〜Y+1/03/31 想定。
    年度ごとに微小シフト(±5日)を入れて、現実の揺れを再現。
    """
    year0 = academic_year_start
    year1 = academic_year_start + 1

    year_shift = int(rng.integers(-5, 6))  # [-5, +5]
    if course == "J":
        # 翌年2月中心で開始、翌年4月中心でピーク（Jは遅め・尖り気味）
        start_center = datetime(year1, 2, 19, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        peak_center = datetime(year1, 4, 10, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        return CalendarParams(start_center, 15.0, peak_center, 12.0)

    if course == "S":
        # 翌年2月上旬〜4月（JとRの中間・少し広め）
        start_center = datetime(year1, 2, 9, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        peak_center = datetime(year1, 4, 10, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        return CalendarParams(start_center, 20.0, peak_center, 18.0)

    if course == "R":
        # 当年10月中心で開始、翌年4月中心でピーク（早期＋広め）
        start_center = datetime(year0, 10, 27, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        peak_center = datetime(year1, 4, 10, 0, 0, tzinfo=JST) + timedelta(days=year_shift)
        return CalendarParams(start_center, 30.0, peak_center, 25.0)

    raise ValueError(f"Unknown course: {course}")


# ==========
# 名前・企業名の辞書（seed再現のため固定リスト）
# ==========

SURNAMES = [
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水",
    "山崎", "阿部", "森", "池田", "橋本", "石川", "山下", "中島", "前田", "藤田",
]
GIVEN = [
    "太郎", "花子", "健太", "美咲", "翔太", "結衣", "大輔", "彩香", "拓也", "優奈",
    "直樹", "遥", "優樹", "葵", "悠斗", "凛", "陸", "陽菜", "海斗", "杏奈",
]

COMPANIES = [
    "株式会社アルファ", "株式会社ベータ", "株式会社ガンマ", "株式会社デルタ", "株式会社イプシロン",
    "株式会社オメガ", "株式会社ネクスト", "株式会社フロンティア", "株式会社サンライズ", "株式会社スカイ",
    "株式会社ミライ", "株式会社テックワークス", "株式会社リンク", "株式会社グロース", "株式会社ユニオン",
    "株式会社イノベーション", "株式会社シグマ", "株式会社ノヴァ", "株式会社プライム", "株式会社アーク",
    "株式会社リーフ", "株式会社ブルーム", "株式会社オービット", "株式会社ステラ", "株式会社クレスト",
    "株式会社エッジ", "株式会社エコー", "株式会社クロス", "株式会社パルス", "株式会社ルミナス",
    "株式会社モデスト", "株式会社ビジョン", "株式会社レイヤー", "株式会社フォーカス", "株式会社ハーモニー",
    "株式会社ブリッジ", "株式会社ストリーム", "株式会社エンジン", "株式会社アトラス", "株式会社コア",
    "株式会社マーブル", "株式会社アセント", "株式会社フォース", "株式会社オーシャン", "株式会社グリーン",
    "株式会社ホライズン", "株式会社ライト", "株式会社クラフト", "株式会社シード", "株式会社アビリティ",
]


# ==========
# 乱数ユーティリティ
# ==========

def _choice(rng: np.random.Generator, items: List[str], probs: List[float]) -> str:
    p = np.array(probs, dtype=float)
    p = p / p.sum()
    return str(rng.choice(items, p=p))

def _choice_int(rng: np.random.Generator, items: List[int], probs: List[float]) -> int:
    p = np.array(probs, dtype=float)
    p = p / p.sum()
    return int(rng.choice(items, p=p))

def _trunc_normal_days(rng: np.random.Generator, center: datetime, sd_days: float,
                       min_dt: datetime, max_dt: datetime) -> datetime:
    # 正規→範囲外なら再抽選（truncated）
    for _ in range(2000):
        d = rng.normal(loc=0.0, scale=sd_days)
        dt = center + timedelta(days=float(d))
        if min_dt <= dt <= max_dt:
            return dt
    # どうしても入らなければクリップ
    if center < min_dt:
        return min_dt
    if center > max_dt:
        return max_dt
    return center

def _to_slot(rng: np.random.Generator, date_base: datetime) -> datetime:
    h, m = TIME_SLOTS[int(rng.integers(0, len(TIME_SLOTS)))]
    return date_base.replace(hour=h, minute=m, second=0, microsecond=0)

def _iso(dt: datetime) -> str:
    # 例：2025-04-10T10:00:00+09:00
    return dt.isoformat(timespec="seconds")


# ==========
# Student / Event
# ==========

@dataclass
class Student:
    user_no: str
    class_no: str
    user_name: str
    course: str
    stype: str  # E/N/L/S/G/O
    academic_year_start: int  # 卒業年度（分析の年度）

@dataclass
class EventRow:
    user_no: str
    class_no: str
    user_name: str
    start_dateTime: str
    end_dateTime: str
    company_name: str
    event_kind: str
    result_kind: str


# ==========
# 生成：学生
# ==========

def generate_students_for_year(academic_year_start: int, rng: np.random.Generator) -> List[Student]:
    students: List[Student] = []

    for course, n in HEADCOUNT_BY_COURSE.items():
        classes = CLASS_BY_COURSE[course]
        # クラスに均等割り当て（端数は前から）
        base = n // len(classes)
        rem = n % len(classes)
        class_assign = []
        for i, c in enumerate(classes):
            class_assign += [c] * (base + (1 if i < rem else 0))
        rng.shuffle(class_assign)

        # 潜在タイプ（学科別混合比）
        mix = MIX_RATIO_BY_COURSE[course]
        type_items = list(mix.keys())
        type_probs = [mix[t] for t in type_items]

        # 入学年：あなたの規則
        admission_year = academic_year_start + ADMISSION_YEAR_OFFSET[course]
        code = COURSE_CODE[course]

        for i in range(1, n + 1):
            seq = f"{i:02d}"
            user_no = f"{admission_year}{code}{seq}"

            class_no = class_assign[i - 1]

            surname = rng.choice(SURNAMES)
            given = rng.choice(GIVEN)
            user_name = f"{surname}{given}"

            stype = _choice(rng, type_items, type_probs)

            students.append(Student(
                user_no=user_no,
                class_no=class_no,
                user_name=user_name,
                course=course,
                stype=stype,
                academic_year_start=academic_year_start,
            ))
    return students


# ==========
# 生成：企業プロセス → イベント列
# ==========

def _sample_company_count(rng: np.random.Generator, stype: str) -> int:
    lam = float(LAMBDA_COMPANIES[stype])
    c = int(rng.poisson(lam=lam))
    c = max(0, min(MAX_COMPANIES, c))
    return c

def _sample_interview_stages(rng: np.random.Generator, stype: str) -> int:
    k = _choice_int(rng, INTERVIEW_STAGE_VALUES, INTERVIEW_STAGE_PROBS)
    if stype == "O" and rng.random() < OVERINTERVIEW_PLUS1_PROB:
        k += 1
    return int(max(1, min(MAX_STAGES, k)))

def _trial_result_for_stage(rng: np.random.Generator, is_last_stage: bool) -> str:
    """
    結果待ちは現実的に「その企業の最後（現時点で止まる）」として扱う。
    したがって、非最終ステージで結果待ちが出た場合は企業プロセスを停止する。
    （継続(合格)の“次イベント必須”制約を厳守）
    """
    return _choice(rng, TRIAL_RESULT_VALUES, TRIAL_RESULT_PROBS)

def _offer_happens(rng: np.random.Generator, stype: str) -> bool:
    p = float(OFFER_PROB_BY_TYPE.get(stype, 0.15))
    return bool(rng.random() < p)

def _make_event(rng: np.random.Generator, student: Student, dt_start: datetime,
                company_name: str, event_kind: str, result_kind: str) -> EventRow:
    dt_start = _to_slot(rng, dt_start)
    dur = int(DURATION_MIN[event_kind])
    dt_end = dt_start + timedelta(minutes=dur)
    return EventRow(
        user_no=student.user_no,
        class_no=student.class_no,
        user_name=student.user_name,
        start_dateTime=_iso(dt_start),
        end_dateTime=_iso(dt_end),
        company_name=company_name,
        event_kind=event_kind,
        result_kind=result_kind,
    )

def generate_events_for_student(student: Student,
                               cal: CalendarParams,
                               rng: np.random.Generator) -> List[EventRow]:
    """
    学生1人分の report_t 互換イベント行を生成
    """
    Y = student.academic_year_start
    year_start = datetime(Y, 4, 1, 0, 0, tzinfo=JST)
    year_end = datetime(Y + 1, 3, 31, 23, 59, tzinfo=JST)

    # 学生の「開始日」をtruncated normalで決める（層A）
    first_dt = _trunc_normal_days(rng, cal.start_center, cal.start_sd_days, year_start, year_end)

    # 応募企業数
    company_count = _sample_company_count(rng, student.stype)

    # GateStuckはさらに企業数を抑制（入口停滞の現実性）
    if student.stype == "G":
        company_count = min(company_count, 2)

    if company_count == 0:
        # 0社の学生：イベント無し（後で停滞系に刺さる）
        return []

    # 企業名は重複なしで抽選（現実的）
    company_names = rng.choice(COMPANIES, size=company_count, replace=False).tolist()

    rows: List[EventRow] = []
    got_offer = False

    # 企業ごとにプロセスを生成
    current_base = first_dt

    for ci, cname in enumerate(company_names):
        if got_offer:
            break

        # 説明会系：0〜2回
        bcnt = _choice_int(rng, BRIEFING_COUNT_VALUES, BRIEFING_COUNT_PROBS)

        # GateStuck: 説明会0〜1寄りに歪ませる（入口停滞）
        if student.stype == "G" and bcnt == 2 and rng.random() < 0.7:
            bcnt = 1

        # 説明会の日時は開始〜ピークの間に散らす（現実性）
        for _ in range(bcnt):
            ek = rng.choice(list(BRIEFING_KINDS))
            # 説明会日は peak_center より少し前に寄るようにサンプル
            dt = _trunc_normal_days(
                rng,
                center=cal.peak_center - timedelta(days=20),
                sd_days=cal.peak_sd_days,
                min_dt=year_start,
                max_dt=year_end,
            )
            # 説明会系は基本 result_kind="他"
            rows.append(_make_event(rng, student, dt, cname, ek, "他"))

        # インターンやセミナーだけで終わる企業もある（現実的）
        # GateStuckは試験へ進みにくい
        proceed_to_trial = True
        if student.stype == "G" and rng.random() < 0.75:
            proceed_to_trial = False

        # Lateは進むが遅い（企業プロセス自体は作る）
        # Stagnantはあとで空白注入するのでここでは通常生成

        if not proceed_to_trial:
            continue

        # 試験_適正（0/1）
        if rng.random() < APTITUDE_PROB:
            dt = _trunc_normal_days(
                rng,
                center=cal.peak_center - timedelta(days=10),
                sd_days=cal.peak_sd_days,
                min_dt=year_start,
                max_dt=year_end,
            )
            rk = _trial_result_for_stage(rng, is_last_stage=False)
            rows.append(_make_event(rng, student, dt, cname, "試験_適正", rk))
            # 結果待ち/不合格/辞退ならこの企業は停止（継続(合格)だけが次へ）
            if rk != "継続 (合格)":
                continue

        # 面接ステージ数
        stages = _sample_interview_stages(rng, student.stype)

        # 各面接ステージ
        ended = False
        for si in range(stages):
            is_last = (si == stages - 1)

            # 面接日はピークに寄る（面接は春集中）
            dt = _trunc_normal_days(
                rng,
                center=cal.peak_center,
                sd_days=cal.peak_sd_days,
                min_dt=year_start,
                max_dt=year_end,
            )
            rk = _trial_result_for_stage(rng, is_last_stage=is_last)

            rows.append(_make_event(rng, student, dt, cname, "試験_面接", rk))

            # 継続(合格)なら次へ進む
            if rk == "継続 (合格)":
                continue

            # 結果待ち・不合格・辞退で企業は止まる
            ended = True
            break

        if ended:
            continue

        # ここまで来た＝最終ステージまで「継続(合格)」で抜けた扱い
        # 最終でのみ内定が起き得る（仕様）
        if _offer_happens(rng, student.stype):
            # 内定イベントは“結果”として result_kind="内定" を付ける（event_kindは試験_他に寄せるのが自然）
            dt = _trunc_normal_days(
                rng,
                center=cal.peak_center + timedelta(days=7),
                sd_days=cal.peak_sd_days,
                min_dt=year_start,
                max_dt=year_end,
            )
            rows.append(_make_event(rng, student, dt, cname, "試験_他", "内定"))
            got_offer = True

            # 内定後活動・内定式（event_kindは指定に従い、result_kindは必ず内定）
            # 内定後活動（0〜1）
            if rng.random() < 0.7:
                dt2 = dt + timedelta(days=int(rng.integers(7, 28)))
                if dt2 <= year_end:
                    rows.append(_make_event(rng, student, dt2, cname, "内定後活動", "内定"))
            # 内定式（0〜1）
            if rng.random() < 0.6:
                dt3 = dt + timedelta(days=int(rng.integers(30, 120)))
                if dt3 <= year_end:
                    rows.append(_make_event(rng, student, dt3, cname, "内定式", "内定"))

    # 日付順にソート（API集計の前提に合う）
    rows.sort(key=lambda r: r.start_dateTime)
    return rows


# ==========
# 停滞（空白）注入【最重要】
# ==========

def _has_recent_progressing(rows: List[EventRow], ref_dt: datetime, window_days: int = 21) -> bool:
    """
    ref_dt の直近 window_days に、試験系で result_kind が「結果待ち」または「継続(合格)」があるか
    """
    start = ref_dt - timedelta(days=window_days)
    for r in rows:
        if r.event_kind not in TRIAL_KINDS and r.event_kind != "試験_面接":
            continue
        dt = datetime.fromisoformat(r.start_dateTime)
        if start <= dt <= ref_dt and r.result_kind in {"結果待ち", "継続 (合格)"}:
            return True
    return False

def inject_gaps(student: Student, rows: List[EventRow], rng: np.random.Generator) -> List[EventRow]:
    """
    空白注入（混合）
    A) 失速型（60%）：4月以降で gap_start を置き、それ以降を削除（強い停滞）
    B) 入口停滞型（40%）：説明会系だけ残し、試験系を削除
    progressing（直近21日で 継続/結果待ち）がある場合は注入回避（仕様）
    """
    if not rows:
        return rows

    Y = student.academic_year_start
    year_start = datetime(Y, 4, 1, 0, 0, tzinfo=JST)
    year_end = datetime(Y + 1, 3, 31, 23, 59, tzinfo=JST)

    # 内定持ちは空白注入しない（内定者はフォロー対象外の思想）
    if any(r.result_kind == "内定" for r in rows):
        return rows

    # 対象抽選：S/Gは必ず候補、他は0.25
    eligible = (student.stype in {"S", "G"}) or (rng.random() < 0.25)
    if not eligible:
        return rows

    # gap_start は「翌年4/20〜5/20」（ピーク直後の失速が最も“絶妙”）
    year1 = Y + 1
    gap_start_min = datetime(year1, 4, 20, 0, 0, tzinfo=JST)
    gap_start_max = datetime(year1, 5, 20, 0, 0, tzinfo=JST)

    # 年度範囲外になりうる場合は調整
    if gap_start_min < year_start:
        gap_start_min = year_start
    if gap_start_max > year_end:
        gap_start_max = year_end

    if gap_start_min >= gap_start_max:
        return rows

    # gap_start を一様ではなく「正規で中央寄せ」にする（現実性）
    gap_center = gap_start_min + (gap_start_max - gap_start_min) / 2
    gap_start = _trunc_normal_days(rng, gap_center, 6.0, gap_start_min, gap_start_max)

    # progressing が直近にあるなら空白注入回避
    if _has_recent_progressing(rows, gap_start, window_days=21):
        return rows

    # A/B 混合（60/40）
    mode = "A" if rng.random() < 0.60 else "B"

    if mode == "B":
        # 入口停滞：説明会系だけ残す（結果は基本"他"）
        kept = [r for r in rows if r.event_kind in BRIEFING_KINDS]
        kept.sort(key=lambda r: r.start_dateTime)
        return kept

    # mode A: 失速型
    # gap_len は対数正規（15〜60日中心、重い尻尾）
    # lognormal の中央値を ~28日に寄せる
    gap_len = int(np.clip(rng.lognormal(mean=np.log(28), sigma=0.45), 15, 60))

    # 仕様：4月以降のイベントを全削除（強い停滞）
    # “gap_start以降”を削除することで inactivity が必ず増える
    out = []
    for r in rows:
        dt = datetime.fromisoformat(r.start_dateTime)
        if dt >= gap_start:
            continue
        out.append(r)

    out.sort(key=lambda r: r.start_dateTime)
    return out


# ==========
# メイン：5年分×200人→CSV出力
# ==========

def generate_seed_csv(
    seed: int = 42,
    academic_year_starts: List[int] = None,
    out_csv_path: str = "report_seed.csv",
) -> pd.DataFrame:
    if academic_year_starts is None:
        # 過去5年分（例）：2021〜2025
        academic_year_starts = [2021, 2022, 2023, 2024, 2025]

    rng = np.random.default_rng(seed)

    all_rows: List[EventRow] = []

    for Y in academic_year_starts:
        students = generate_students_for_year(Y, rng)

        # 学科別カレンダー（年度×学科）
        cal_cache: Dict[str, CalendarParams] = {}
        for course in ["J", "S", "R"]:
            cal_cache[course] = _calendar_for(Y, course, rng)

        for st in students:
            cal = cal_cache[st.course]
            rows = generate_events_for_student(st, cal, rng)
            rows = inject_gaps(st, rows, rng)
            all_rows.extend(rows)

    # DataFrame化（列順は指定どおり）
    df = pd.DataFrame([r.__dict__ for r in all_rows], columns=[
        "user_no", "class_no", "user_name",
        "start_dateTime", "end_dateTime",
        "company_name", "event_kind", "result_kind"
    ])

    # start_dateTime順に全体ソート（見やすさ）
    df = df.sort_values(["start_dateTime", "user_no"]).reset_index(drop=True)

    # CSV出力（Excelで文字化けしにくい）
    df.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    df = generate_seed_csv(
        seed=42,
        academic_year_starts=[2021, 2022, 2023, 2024, 2025],
        out_csv_path="report_seed.csv",
    )
    print("generated:", len(df), "rows -> report_seed.csv")
    print(df.head(5).to_string(index=False))
