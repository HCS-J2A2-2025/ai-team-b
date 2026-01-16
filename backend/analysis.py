import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests

# ============================
# 設定
# ============================
BASE_DIR = Path(__file__).resolve().parent
CSV_CANDIDATES = [
    BASE_DIR / "data" / "取扱注意_過去の受験報告(生データ) (1).csv",
    BASE_DIR / "data" / "report_t_all.csv",
]


def _default_csv_path() -> Path:
    for path in CSV_CANDIDATES:
        if path.exists():
            return path
    return CSV_CANDIDATES[0]


CSV_PATH = _default_csv_path()

AI_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b-instruct"

# student_id 指定時のみ有効になる
USE_AI = False


# ============================
# CSV 読み込み & 正規化
# ============================
_COL_MAPPING = {
    "student_id": ["学籍番号", "student_no", "studentId", "student_id", "user_no"],
    "company_name": ["企業名", "会社名", "企業", "company_name", "company"],
    "report_text": ["面接内容", "報告内容", "report_text", "reportText", "text", "report_content"],
    "start_datetime": ["開始日時", "start_datetime", "start", "開始", "start_time", "start_date_time"],
    "end_datetime": ["終了日時", "end_datetime", "end", "終了", "end_time", "end_date_time"],
    "result_status": ["結果種別", "result", "結果", "status", "result_kind"],
    "exam_format": ["形式", "format", "held_style", "形式種別", "exam_format"],
    "positions": ["役職", "post", "position", "面接官役職", "positions"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )

    col_set = set(df.columns)
    rename_map = {}

    for std, cands in _COL_MAPPING.items():
        if std in col_set:
            continue
        for c in cands:
            if c in col_set:
                rename_map[c] = std
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def _read_report_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = _normalize_columns(df)

    required = ["student_id", "company_name", "report_text", "start_datetime", "end_datetime"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSVに必要な列がありません: {missing}")

    # 補完
    for col in ["result_status", "exam_format", "positions"]:
        if col not in df.columns:
            df[col] = "不明"

    # 学籍番号正規化
    df["student_id"] = (
        df["student_id"]
        .astype(str)
        .str.replace("\u3000", "", regex=False)
        .str.replace("\t", "", regex=False)
        .str.strip()
        .str.upper()
    )

    return df


# ============================
# ユーティリティ
# ============================
def _to_iso_or_none(x) -> Optional[str]:
    if pd.isna(x):
        return None
    try:
        return x.isoformat(sep=" ", timespec="minutes")
    except Exception:
        return str(x)


def ask_ai(prompt: str) -> str:
    try:
        res = requests.post(
            AI_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        if not res.ok:
            return f"AI生成に失敗しました: HTTP {res.status_code}"

        data = res.json()
        return (data.get("response") or "").strip() or "AI応答なし"
    except Exception as e:
        return f"AI生成に失敗しました: {e}"


# ============================
# メイン：学生別集計
# ============================
def build_student_analysis(
    student_id: Optional[str] = None,
    use_ai: bool = USE_AI,
    csv_path: Path = CSV_PATH,
) -> Dict[str, Any]:
    df = _read_report_csv(csv_path)

    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
    df["end_datetime"] = pd.to_datetime(df["end_datetime"], errors="coerce")

    # student_id 未指定時は AI 強制OFF
    if student_id:
        sid = student_id.strip().upper()
        df = df[df["student_id"] == sid].copy()
    else:
        use_ai = False

    if df.empty:
        return {}

    result: Dict[str, Any] = {}

    PASS_KEYWORDS = ["合格", "内定", "通過"]

    for sid, group in df.groupby("student_id"):
        total = len(group)

        passed = group["result_status"].astype(str).apply(
            lambda x: any(k in x for k in PASS_KEYWORDS)
        ).sum()

        pass_rate = round(passed / total * 100, 1) if total > 0 else None

        # AI集計
        if use_ai:
            joined = "\n\n".join(group["report_text"].fillna("").astype(str))
            prompt = f"""
あなたは就職活動を支援するキャリアアドバイザーです。
以下は学籍番号 {sid} の面接レポートです。

【面接ログ】
{joined}

# 出力ルール（最重要）
- 必ず日本語で出力する
- 出力は「指定テンプレートの4セクションのみ」。前置き・結論・補足・挨拶は禁止
- 見出しは「■ セクション名」形式で統一（他の見出し記号は禁止）
- 箇条書きは「- 」のみを使用（「・」「*」は禁止）
- 箇条書きは次の形式で書く
  - **要点となる短い言葉** その根拠・背景・評価理由を具体的に説明する文章
- 太字の見出し記号（**...**）以外の強調は禁止
- 箇条書きの説明文は「具体的な根拠・評価の背景・面接官視点」を含め、丁寧に書く
- 抽象的な表現（「良かった」「評価された」だけで終わる表現）は避ける
- 箇条書き中で改行やネストをしない
- 罫線や余計な空行は禁止

# 指定テンプレート（この形を厳守）
■ 全体傾向
- ...: ...
- ...: ...
- ...: ...

■ 強み
- ...: ...
- ...: ...
- ...: ...

■ 注意点・改善
- ...: ...
- ...: ...
- ...: ...

■ 次回面接への具体的アクション
- ...: ...
- ...: ...
- ...: ...
""".strip()
            ai_summary = ask_ai(prompt)
        else:
            ai_summary = "AI生成はOFFです"

        g = group.copy()
        g["start_datetime"] = g["start_datetime"].apply(_to_iso_or_none)
        g["end_datetime"] = g["end_datetime"].apply(_to_iso_or_none)

        result[sid] = {
            "企業一覧": sorted(group["company_name"].dropna().unique().tolist()),
            "受験回数": total,
            "受験期間": f"{_to_iso_or_none(group['start_datetime'].min())} ～ {_to_iso_or_none(group['start_datetime'].max())}",
            "合格率": f"{pass_rate}%" if pass_rate is not None else "不明",
            "面接日時": g[
                ["company_name", "start_datetime", "end_datetime", "result_status"]
            ].to_dict(orient="records"),
            "形式傾向": group["exam_format"].value_counts().to_dict(),
            "面接官傾向": group["positions"].value_counts().to_dict(),
            "AI集計レポート": ai_summary,
        }

    return result


# ============================
# CLI
# ============================
if __name__ == "__main__":
    data = build_student_analysis(use_ai=USE_AI)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])


# ============================
# 学籍番号サジェスト用：軽量
# ============================
_STUDENT_IDS_CACHE: list[str] = []
_STUDENT_IDS_MTIME: float | None = None


def suggest_student_ids(
    prefix: str,
    limit: int = 10,
    csv_path: Path = CSV_PATH,
) -> list[str]:
    """
    入力途中の prefix から学籍番号候補を返す
    """
    global _STUDENT_IDS_CACHE, _STUDENT_IDS_MTIME

    kw = (prefix or "").strip().upper()
    if not kw:
        return []

    try:
        mtime = csv_path.stat().st_mtime
    except FileNotFoundError:
        return []

    # CSVが更新されていなければキャッシュ使用
    if _STUDENT_IDS_CACHE and _STUDENT_IDS_MTIME == mtime:
        ids = _STUDENT_IDS_CACHE
    else:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        df = _normalize_columns(df)

        if "student_id" not in df.columns:
            return []

        ids = (
            df["student_id"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .drop_duplicates()
            .tolist()
        )
        ids.sort()

        _STUDENT_IDS_CACHE = ids
        _STUDENT_IDS_MTIME = mtime

    return [sid for sid in ids if sid.startswith(kw)][:limit]
