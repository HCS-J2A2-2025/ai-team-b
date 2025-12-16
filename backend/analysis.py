import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests


# ============================
# 設定
# ============================
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "report_t_all.csv"

AI_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b-instruct"
USE_AI = False  # ★必要な時だけ True


# ============================
# 共通ユーティリティ
# ============================
def _read_report_csv(path: Path) -> pd.DataFrame:
    """列名ゆれ/BOM/空白に強く、必要列を正規化して返す"""
    df = pd.read_csv(path, encoding="utf-8-sig")

    # 列名正規化（BOM/空白/全角空白など）
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )

    # 列名ゆれ吸収（英語→日本語）
    col_set = set(df.columns)
    rename_map = {}

    # 学籍番号
    if "学籍番号" not in col_set:
        for cand in ["student_no", "studentId", "student_id"]:
            if cand in col_set:
                rename_map[cand] = "学籍番号"
                break

    # 企業名
    if "企業名" not in col_set:
        for cand in ["company_name", "企業", "company"]:
            if cand in col_set:
                rename_map[cand] = "企業名"
                break

    # 面接本文
    if "report_text" not in col_set and "面接内容" in col_set:
        rename_map["面接内容"] = "report_text"
    if "report_text" not in col_set:
        for cand in ["reportText", "text", "本文"]:
            if cand in col_set:
                rename_map[cand] = "report_text"
                break

    # 開始日時
    if "start_datetime" not in col_set and "開始日時" in col_set:
        rename_map["開始日時"] = "start_datetime"
    if "start_datetime" not in col_set:
        for cand in ["start", "開始", "start_time"]:
            if cand in col_set:
                rename_map[cand] = "start_datetime"
                break

    # 終了日時
    if "終了日時" not in col_set and "end_datetime" in col_set:
        rename_map["end_datetime"] = "終了日時"
    if "終了日時" not in col_set:
        for cand in ["end", "終了", "end_time"]:
            if cand in col_set:
                rename_map[cand] = "終了日時"
                break

    # 結果
    if "result_status" not in col_set and "結果種別" in col_set:
        rename_map["結果種別"] = "result_status"
    if "result_status" not in col_set:
        for cand in ["result", "結果", "status"]:
            if cand in col_set:
                rename_map[cand] = "result_status"
                break

    # 形式
    if "形式" not in col_set:
        for cand in ["format", "held_style", "形式種別"]:
            if cand in col_set:
                rename_map[cand] = "形式"
                break

    # 役職
    if "役職" not in col_set:
        for cand in ["post", "position", "面接官役職"]:
            if cand in col_set:
                rename_map[cand] = "役職"
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    # 必須列チェック
    required = ["学籍番号", "企業名", "report_text", "start_datetime", "終了日時", "result_status", "形式", "役職"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSVに必要な列がありません: {missing}\n"
            f"今ある列: {df.columns.tolist()}\n"
            f"CSV_PATH: {path}"
        )

    return df


def _to_iso_or_none(x) -> Optional[str]:
    """Timestamp/NaTをJSON向けに ISO文字列 or None にする"""
    if pd.isna(x):
        return None
    # minutes粒度で十分なら timespec="minutes"
    try:
        return x.isoformat(sep=" ", timespec="minutes")
    except Exception:
        return str(x)


def ask_ai(prompt: str) -> str:
    """壊れても落ちない安全版（timeout付き）"""
    try:
        res = requests.post(
            AI_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        if not res.ok:
            return f"（AI分析に失敗: {res.status_code}）"

        try:
            data = res.json()
            return (data.get("response", "") or "").strip()
        except Exception:
            return res.text.strip() or "（AI分析の解析に失敗しました）"
    except Exception as e:
        return f"（AI分析に失敗しました: {e}）"


# ============================
# メイン：学生別分析（保存しない）
# ============================
def build_student_analysis(
    student_id: Optional[str] = None,
    use_ai: bool = USE_AI,
    csv_path: Path = CSV_PATH,
) -> Dict[str, Any]:
    """
    呼ぶたびにCSVを読み直して、学生別の統計を dict で返す（保存しない）。
    student_id を指定すると、その学生だけ返す。
    """

    df = _read_report_csv(csv_path)

    # 日付変換（安全）
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
    df["終了日時"] = pd.to_datetime(df["終了日時"], errors="coerce")

    # student_id フィルタ（指定がある場合）
    if student_id is not None:
        sid = str(student_id).strip()
        df = df[df["学籍番号"].astype(str).str.strip() == sid].copy()

    if df.empty:
        # 返却は仕様次第だが、API向けなら空dictが扱いやすい
        return {}

    grouped = df.groupby(df["学籍番号"].astype(str).str.strip(), dropna=False)

    result: Dict[str, Any] = {}

    for sid, group in grouped:
        sid_str = str(sid).strip() if sid is not None else "UNKNOWN"

        # レポート全文（AI用）
        full_report = "\n\n".join(group["report_text"].fillna("").astype(str).tolist())

        prompt = f"""学生 {sid_str} の面接レポートです。
受験傾向と強み・弱みを分析してください。

【データ】
{full_report}
"""

        ai_summary = ask_ai(prompt) if use_ai else "（AI分析はOFFです）"

        # 日付はJSON向けにISO or None
        g = group.copy()
        g["start_datetime"] = g["start_datetime"].apply(_to_iso_or_none)
        g["終了日時"] = g["終了日時"].apply(_to_iso_or_none)

        # 期間（NaT混じりでも崩れない）
        start_min = group["start_datetime"].min()
        start_max = group["start_datetime"].max()
        period = f"{_to_iso_or_none(start_min)} ～ {_to_iso_or_none(start_max)}"

        result[sid_str] = {
            "企業一覧": sorted(group["企業名"].dropna().astype(str).str.strip().unique().tolist()),
            "面接日程": g[["企業名", "start_datetime", "終了日時", "result_status"]].to_dict(orient="records"),
            "受験回数": int(len(group)),
            "受験期間": period,
            "形式傾向": group["形式"].fillna("不明").astype(str).value_counts().to_dict(),
            "面接官傾向": group["役職"].fillna("不明").astype(str).value_counts().to_dict(),
            "AI分析レポート": ai_summary,
        }

    return result


# ============================
# CLI実行（保存しない）
# ============================
if __name__ == "__main__":
    print(f"読み込みパス: {CSV_PATH}")

    # 全員分（保存しない）
    data = build_student_analysis(use_ai=USE_AI)

    # 画面に出す（大きすぎる場合は一部だけにする）
    print("🎉 学生別分析を生成しました（保存はしません）")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])  # 長いので先頭だけ表示
