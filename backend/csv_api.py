from fastapi import APIRouter, UploadFile, File
import os
import pandas as pd
import csv
from pandas.errors import EmptyDataError

router = APIRouter()

UPLOAD_DIR = "data"
MASTER_CSV = os.path.join(UPLOAD_DIR, "data-1768790126893.csv")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 1行化対象（存在する列だけ処理する）
MULTILINE_COLUMNS = [
    "report_text",
    "面接内容",
    "report_content",
    "future_movement",
]

# 重複排除のキー候補（優先順）
DEDUP_KEYS = [
    "レポートID",
    "report_id",
    "exam_report_id",
]
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """BOM/空白などで列名がズレても当たるようにする"""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("　", "", regex=False)
    )
    return df


def _normalize_multiline_all_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    文字列列(object)のセル内改行を「\\n」に変換して、CSV上は必ず物理1行にする。
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    def norm(x) -> str:
        if x is None:
            return ""
        s = str(x)
        if s.strip().lower() in {"nan", "none"}:
            return ""
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        return s.replace("\n", "\\n")

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(norm)

    return df


def _read_csv_safe(fileobj) -> pd.DataFrame:
    """
    UploadFile.file を pandas で読む。
    dtype=str と keep_default_na=False で、勝手な NaN 化を抑える。
    """
    return pd.read_csv(
        fileobj,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )


def _normalize_multiline_cell(x) -> str:
    """
    セル内の改行を物理1行にする。
    - \r\n, \r, \n を \\n という2文字に変換（後でUIで復元可能）
    """
    if x is None:
        return ""
    s = str(x)
    # pandas の "nan" 文字なども来るので一応潰す
    if s.strip().lower() in {"nan", "none"}:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", "\\n")
    # タブ等を軽く正規化（任意）
    s = s.replace("\t", " ")
    return s


def _normalize_df_for_save(df: pd.DataFrame) -> pd.DataFrame:
    """
    保存前の正規化。
    - マルチライン列を1行化
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    for col in MULTILINE_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(_normalize_multiline_cell)

    return out


def _pick_dedup_key(df: pd.DataFrame) -> str | None:
    for k in DEDUP_KEYS:
        if k in df.columns:
            return k
    return None


def _drop_duplicates_safely(df: pd.DataFrame) -> pd.DataFrame:
    """
    可能ならレポートID等で重複排除。
    無ければ全列一致の drop_duplicates にフォールバック。
    """
    if df is None or df.empty:
        return df

    key = _pick_dedup_key(df)
    if key is None:
        return df.drop_duplicates()

    s = df[key].astype(str).str.strip()
    valid = (s != "") & (s.str.lower() != "nan") & (s.str.lower() != "none")

    df_valid = df[valid].copy()
    df_invalid = df[~valid].copy()

    # レポートIDがある行だけ key で重複排除
    df_valid = df_valid.drop_duplicates(subset=[key], keep="last")

    # レポートIDが無い行は全列一致で重複排除（保険）
    if not df_invalid.empty:
        df_invalid = df_invalid.drop_duplicates()

    return pd.concat([df_valid, df_invalid], ignore_index=True)


@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    # =========================
    # ① 拡張子チェック（必須）
    # =========================
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return {"status": "error", "message": "CSVファイル（.csv）のみアップロードできます"}

    # =========================
    # ② アップロードCSVを読み込み
    # =========================
    try:
        new_df = _read_csv_safe(file.file)
    except Exception as e:
        return {"status": "error", "message": f"CSVの読み込みに失敗しました: {e}"}

    # ★ 列名正規化 → 文字列列を全部1行化（future_movement含む）
    new_df = _normalize_columns(new_df)
    new_df = _normalize_multiline_all_text_columns(new_df)


    # =========================
    # ③ 既存マスターCSVを読む
    # =========================
    if os.path.exists(MASTER_CSV):
        try:
            # ★空ファイル(0バイト)だと read_csv が落ちるので先に判定
            if os.path.getsize(MASTER_CSV) == 0:
                base_df = pd.DataFrame()
            else:
                base_df = pd.read_csv(
                    MASTER_CSV,
                    encoding="utf-8-sig",
                    dtype=str,
                    keep_default_na=False,
                )
        except EmptyDataError:
            # ★ヘッダ無し/空扱い
            base_df = pd.DataFrame()
        except Exception as e:
            return {"status": "error", "message": f"既存CSVの読み込みに失敗しました: {e}"}
    else:
        base_df = pd.DataFrame()
    # ここを追加（重要）
    if not base_df.empty:
        base_df = _normalize_columns(base_df)
        base_df = _normalize_multiline_all_text_columns(base_df)

    # =========================
    # ④ 縦結合 → 重複削除
    # =========================
    merged_df = pd.concat([base_df, new_df], ignore_index=True, sort=False)
    merged_df = _drop_duplicates_safely(merged_df)

    # =========================
    # ⑤ マスターCSVとして保存
    # =========================
    try:
        merged_df.to_csv(
            MASTER_CSV,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_ALL,   # 重要：カンマ/改行/ダブルクォート対策
            lineterminator="\n",     # OS差で崩れにくく
        )
    except Exception as e:
        return {"status": "error", "message": f"CSVの保存に失敗しました: {e}"}

    return {
        "status": "ok",
        "message": "CSVをマスターCSVに統合しました（セル内改行は1行化済み）",
        "total_rows": len(merged_df),
        "master_csv": MASTER_CSV,
    }
