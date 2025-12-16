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
    df = pd.read_csv(path, encoding="utf-8-sig")

    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )

    col_set = set(df.columns)
    rename_map = {}

    if "学籍番号" not in col_set:
        for c in ["student_no", "studentId", "student_id"]:
            if c in col_set:
                rename_map[c] = "学籍番号"
                break

    if "企業名" not in col_set:
        for c in ["company_name", "企業", "company"]:
            if c in col_set:
                rename_map[c] = "企業名"
                break

    if "report_text" not in col_set:
        for c in ["面接内容", "reportText", "text", "本文"]:
            if c in col_set:
                rename_map[c] = "report_text"
                break

    if "start_datetime" not in col_set:
        for c in ["開始日時", "start", "開始", "start_time"]:
            if c in col_set:
                rename_map[c] = "start_datetime"
                break

    if "終了日時" not in col_set:
        for c in ["end_datetime", "end", "終了", "end_time"]:
            if c in col_set:
                rename_map[c] = "終了日時"
                break

    if "result_status" not in col_set:
        for c in ["結果種別", "result", "結果", "status"]:
            if c in col_set:
                rename_map[c] = "result_status"
                break

    if "形式" not in col_set:
        for c in ["format", "held_style", "形式種別"]:
            if c in col_set:
                rename_map[c] = "形式"
                break

    if "役職" not in col_set:
        for c in ["post", "position", "面接官役職"]:
            if c in col_set:
                rename_map[c] = "役職"
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    required = ["学籍番号", "企業名", "report_text", "start_datetime", "終了日時"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSVに必要な列がありません: {missing}")

    if "result_status" not in df.columns:
        df["result_status"] = "不明"
    if "形式" not in df.columns:
        df["形式"] = "不明"
    if "役職" not in df.columns:
        df["役職"] = "不明"

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

    df = _read_report_csv(csv_path)

    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
    df["終了日時"] = pd.to_datetime(df["終了日時"], errors="coerce")

    # 全件取得時は AI 強制OFF（事故防止）
    if student_id is None:
        use_ai = False
    else:
        sid = str(student_id).strip()
        df = df[df["学籍番号"].astype(str).str.strip() == sid].copy()

    if df.empty:
        return {}

    result: Dict[str, Any] = {}

    for sid, group in df.groupby(df["学籍番号"].astype(str).str.strip()):
        sid_str = str(sid).strip()

        if use_ai:
            full_report = "\n\n".join(
                group["report_text"].fillna("").astype(str).tolist()
            )
            prompt = f"""学生 {sid_str} の面接レポートです。
受験傾向と強み・弱みを分析してください。

【データ】
{full_report}
"""
            ai_summary = ask_ai(prompt)
        else:
            ai_summary = "（AI分析はOFFです）"

        g = group.copy()
        g["start_datetime"] = g["start_datetime"].apply(_to_iso_or_none)
        g["終了日時"] = g["終了日時"].apply(_to_iso_or_none)

        start_min = group["start_datetime"].min()
        start_max = group["start_datetime"].max()

        result[sid_str] = {
            "企業一覧": sorted(
                group["企業名"].dropna().astype(str).str.strip().unique().tolist()
            ),
            "面接日程": g[
                ["企業名", "start_datetime", "終了日時", "result_status"]
            ].to_dict(orient="records"),
            "受験回数": int(len(group)),
            "受験期間": f"{_to_iso_or_none(start_min)} ～ {_to_iso_or_none(start_max)}",
            "形式傾向": group["形式"].value_counts().to_dict(),
            "面接官傾向": group["役職"].value_counts().to_dict(),
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
