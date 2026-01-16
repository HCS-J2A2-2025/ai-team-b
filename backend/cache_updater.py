# cache_updater.py
from __future__ import annotations

import json
import time
import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable

import pandas as pd

import company_summary_batch as csb
from company_summary_batch import (
    load_report_df,  # 既存の列ゆれ吸収ローダーがあるなら活用
    summarize_company,
    generate_detailed_report,
    build_interview_records_for_company,
)

# =========================
# Paths
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = BASE_DIR / "data" / "report_t_all.csv"

CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ALL_CACHE_PATH = CACHE_DIR / "company_cache_all.json"


# =========================
# Utilities
# =========================
def _now_jst_iso() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).isoformat(timespec="seconds")


def _mtime_key(mtime: float) -> int:
    """mtime 比較用キー（環境差で小数がブレるのでミリ秒単位で丸め）"""
    return int(round(float(mtime) * 1000))


def write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    """途中で落ちても壊れにくい atomic write。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)

    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(
            obj,
            f,
            ensure_ascii=False,
            indent=2,        # ✅ 1行にならない
            sort_keys=False,
        )
        f.write("\n")

    os.replace(str(tmp), str(path))


def _guess_csv_path() -> Optional[Path]:
    """CSVが既定位置に無いときでも探す（バックなしで確実に動く用）"""
    candidates = [
        DEFAULT_CSV_PATH,
        BASE_DIR / "data" / "Report_t_all.csv",
        BASE_DIR / "report_t_all.csv",
        BASE_DIR.parent / "data" / "report_t_all.csv",
        BASE_DIR.parent / "backend" / "data" / "report_t_all.csv",
    ]
    for p in candidates:
        if p.exists():
            return p

    for p in BASE_DIR.rglob("report_t_all.csv"):
        return p

    return None


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """列名のBOM/空白除去 + 主要列のゆれを吸収"""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )

    col_set = set(df.columns)
    rename: Dict[str, str] = {}

    if "企業名" not in col_set:
        for cand in ["企業", "company_name", "CompanyName", "会社名"]:
            if cand in col_set:
                rename[cand] = "企業名"
                break

    if "イベント種別" not in col_set and "event_kind" in col_set:
        rename["event_kind"] = "イベント種別"

    if "面接内容" not in col_set:
        for cand in ["report_text", "面接", "内容", "interview_text"]:
            if cand in col_set:
                rename[cand] = "面接内容"
                break

    if "開始日時" not in col_set and "start_datetime" in col_set:
        rename["start_datetime"] = "開始日時"

    if rename:
        df = df.rename(columns=rename)

    return df


def _safe_company_key(s: str) -> str:
    """dictキー用（余計な空白だけ潰す）"""
    return re.sub(r"\s+", " ", (s or "").strip())


def _read_previous_meta() -> Dict[str, Any]:
    if not ALL_CACHE_PATH.exists():
        return {}
    try:
        with ALL_CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("meta") or {}
    except Exception:
        return {}


def _read_csv_safely(csv_path: Path) -> pd.DataFrame:
    """
    ✅ 文字化け対策：
    utf-8-sig / utf-8 / cp932(Shift-JIS) を順に試す
    """
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            return df
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("CSV read failed")


def _load_df(csv_path: Path) -> pd.DataFrame:
    """
    なるべく既存の load_report_df を活かしつつ、位置違い・文字化けにも耐えるローダー。
    """
    # 1) まず指定パスを安全に読む（ここが一番確実）
    try:
        df = _read_csv_safely(csv_path)
        return _normalize_cols(df)
    except Exception as e:
        print("[cache_updater] direct read failed -> fallback load_report_df:", e)

    # 2) 既存の load_report_df にフォールバック
    df = load_report_df()
    return _normalize_cols(df)


# =========================
# Main updater
# =========================
def run_update(
    force: bool = False,
    enable_left_ai: bool = True,
    enable_right_ai: bool = True,
) -> None:
    """CSV→集計→AI→ 単一JSON(company_cache_all.json)を書き換える"""
    csv_path = _guess_csv_path()
    if not csv_path:
        print("[cache_updater] CSV not found (searched). Expected like:", DEFAULT_CSV_PATH)
        return

    csv_mtime = csv_path.stat().st_mtime
    csv_mtime_key = _mtime_key(csv_mtime)

    if not force:
        prev_meta = _read_previous_meta()
        prev_key = prev_meta.get("source_csv_mtime_key")
        if isinstance(prev_key, int) and prev_key == csv_mtime_key:
            print("[cache_updater] CSV unchanged -> skip update")
            return

    print(f"[cache_updater] CSV: {csv_path}")
    print("[cache_updater] loading csv...")

    try:
        df = _load_df(csv_path)
    except Exception as e:
        print("[cache_updater] failed to load df:", e)
        return

    if df.empty:
        print("[cache_updater] empty df (0 rows)")
        return
    if "企業名" not in df.columns:
        print("[cache_updater] missing column '企業名'. columns =", df.columns.tolist())
        return

    # ✅ updater時に作るものは「キャッシュ」なので、ここでAI可否を固定
    csb.ENABLE_LEFT_AI = bool(enable_left_ai)
    csb.ENABLE_RIGHT_AI = bool(enable_right_ai)

    companies: Dict[str, Dict[str, Any]] = {}

    for company, group in df.groupby("企業名"):
        company_name = _safe_company_key(str(company))
        if not company_name:
            continue

        try:
            row_dict = summarize_company(group)
        except Exception as e:
            print("[cache_updater] summarize_company failed:", company_name, e)
            continue

        if not row_dict:
            continue

        # ✅ generate_detailed_report が company_name 参照する実装対策
        row_dict["company_name"] = row_dict.get("company_name") or company_name
        row = pd.Series(row_dict)

        report = ""
        if enable_left_ai:
            try:
                report = (generate_detailed_report(row) or "").strip()
            except Exception as e:
                print("[cache_updater] generate_detailed_report failed:", company_name, e)
                report = ""

        records = []
        try:
            records = build_interview_records_for_company(company_name) or []
        except Exception as e:
            print("[cache_updater] build_interview_records_for_company failed:", company_name, e)
            records = []

        companies[company_name] = {
            "company": company_name,
            "report": report,
            "records": records,
        }

    payload = {
        "meta": {
            "updated_at": _now_jst_iso(),
            "source_csv_path": str(csv_path),
            "source_csv_mtime": float(csv_mtime),
            "source_csv_mtime_key": csv_mtime_key,
            "company_count": len(companies),
            "enable_left_ai": bool(enable_left_ai),
            "enable_right_ai": bool(enable_right_ai),
        },
        "companies": companies,
        "company_names": sorted(companies.keys()),
    }

    write_json_atomic(ALL_CACHE_PATH, payload)
    print(f"[cache_updater] wrote: {ALL_CACHE_PATH} (companies={len(companies)})")


if __name__ == "__main__":
    INTERVAL_SEC = 180  # ✅ 3分に1回

    print(f"[cache_updater] watch mode ON (interval={INTERVAL_SEC}s)")

    while True:
        try:
            # force=False が超重要：
            # CSVが変わっていなければ自動で skip update される
            run_update(
                force=False,
                enable_left_ai=True,
                enable_right_ai=True,
            )
        except Exception as e:
            print("[cache_updater] unexpected error:", e)

        time.sleep(INTERVAL_SEC)