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

# ★ student_id 指定時のみ有効になる
USE_AI = False


# ============================
# CSV 読み込み & 正規化
# ============================
def _read_report_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")

    # 列名クレンジング
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )

    col_set = set(df.columns)
    rename_map = {}

    mapping = {
        "学籍番号": ["student_no", "studentId", "student_id"],
        "企業名": ["company_name", "企業", "company"],
        "report_text": ["面接内容", "reportText", "text", "本文"],
        "start_datetime": ["開始日時", "start", "開始", "start_time"],
        "終了日時": ["end_datetime", "end", "終了", "end_time"],
        "result_status": ["結果種別", "result", "結果", "status"],
        "形式": ["format", "held_style", "形式種別"],
        "役職": ["post", "position", "面接官役職"],
    }

    for std, cands in mapping.items():
        if std not in col_set:
            for c in cands:
                if c in col_set:
                    rename_map[c] = std
                    break

    if rename_map:
        df = df.rename(columns=rename_map)

    required = ["学籍番号", "企業名", "report_text", "start_datetime", "終了日時"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSVに必要な列がありません: {missing}")

    # 補完
    for col in ["result_status", "形式", "役職"]:
        if col not in df.columns:
            df[col] = "不明"

    # 学籍番号正規化
    df["学籍番号"] = (
        df["学籍番号"]
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
            return f"（AI分析失敗: HTTP {res.status_code}）"

        data = res.json()
        return (data.get("response") or "").strip() or "（AI応答なし）"
    except Exception as e:
        return f"（AI分析失敗: {e}）"


# ============================
# メイン：学生別分析
# ============================
def build_student_analysis(
    student_id: Optional[str] = None,
    use_ai: bool = USE_AI,
    csv_path: Path = CSV_PATH,
) -> Dict[str, Any]:

    df = _read_report_csv(csv_path)

    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
    df["終了日時"] = pd.to_datetime(df["終了日時"], errors="coerce")

    # student_id 未指定時は AI 強制OFF
    if student_id:
        sid = student_id.strip().upper()
        df = df[df["学籍番号"] == sid].copy()
    else:
        use_ai = False

    if df.empty:
        return {}

    result: Dict[str, Any] = {}

    PASS_KEYWORDS = ["合格", "内定"]

    for sid, group in df.groupby("学籍番号"):
        total = len(group)

        passed = group["result_status"].astype(str).apply(
            lambda x: any(k in x for k in PASS_KEYWORDS)
        ).sum()

        pass_rate = round(passed / total * 100, 1) if total > 0 else None

        # AI分析
        if use_ai:
            joined = "\n\n".join(group["report_text"].fillna("").astype(str))
            prompt = f"""あなたは就職活動を支援するキャリアアドバイザーです。
以下は学籍番号 {sid} の面接レポートです。

【面接ログ】
{joined}

以下の形式を厳守してください。

■ 全体傾向
・
・

■ 強み
・
・

■ 注意点・改善点
・
・

■ 次回面接への具体的アクション
・
・
"""
            ai_summary = ask_ai(prompt)
        else:
            ai_summary = "（AI分析はOFFです）"

        g = group.copy()
        g["start_datetime"] = g["start_datetime"].apply(_to_iso_or_none)
        g["終了日時"] = g["終了日時"].apply(_to_iso_or_none)

        result[sid] = {
            "企業一覧": sorted(group["企業名"].dropna().unique().tolist()),
            "受験回数": total,
            "受験期間": f"{_to_iso_or_none(group['start_datetime'].min())} ～ {_to_iso_or_none(group['start_datetime'].max())}",
            "合格率": f"{pass_rate}%" if pass_rate is not None else "不明",
            "面接日程": g[
                ["企業名", "start_datetime", "終了日時", "result_status"]
            ].to_dict(orient="records"),
            "形式傾向": group["形式"].value_counts().to_dict(),
            "面接官傾向": group["役職"].value_counts().to_dict(),
            "AI分析レポート": ai_summary,
        }

    return result


# ============================
# CLI
# ============================
if __name__ == "__main__":
    data = build_student_analysis(use_ai=USE_AI)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])


# ============================
# 学籍番号サジェスト用（軽量）
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

        df.columns = (
            df.columns.astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
            .str.replace(" ", "", regex=False)
            .str.replace("　", "", regex=False)
        )

        if "学籍番号" not in df.columns:
            for c in ["student_no", "studentId", "student_id"]:
                if c in df.columns:
                    df = df.rename(columns={c: "学籍番号"})
                    break

        if "学籍番号" not in df.columns:
            return []

        ids = (
            df["学籍番号"]
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
