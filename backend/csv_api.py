from fastapi import APIRouter, UploadFile, File
import os
import pandas as pd

router = APIRouter()

UPLOAD_DIR = "data"
MASTER_CSV = os.path.join(UPLOAD_DIR, "取扱注意_過去の受験報告(生データ) (1).csv")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    # =========================
    # ① 拡張子チェック（必須）
    # =========================
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return {
            "status": "error",
            "message": "CSVファイル（.csv）のみアップロードできます"
        }

    # =========================
    # ② アップロードCSVを読み込み
    # =========================
    try:
        new_df = pd.read_csv(file.file, encoding="utf-8-sig")
    except Exception as e:
        return {
            "status": "error",
            "message": f"CSVの読み込みに失敗しました: {e}"
        }

    # =========================
    # ③ 既存 report_t_all.csv を読む
    # =========================
    if os.path.exists(MASTER_CSV):
        try:
            base_df = pd.read_csv(MASTER_CSV, encoding="utf-8-sig")
        except Exception as e:
            return {
                "status": "error",
                "message": f"既存CSVの読み込みに失敗しました: {e}"
            }
    else:
        base_df = pd.DataFrame()

    # =========================
    # ④ 縦結合 → 重複削除
    # =========================
    merged_df = pd.concat([base_df, new_df], ignore_index=True)
    merged_df = merged_df.drop_duplicates()

    # =========================
    # ⑤ report_t_all.csv として保存
    # =========================
    try:
        merged_df.to_csv(
            MASTER_CSV,
            index=False,
            encoding="utf-8-sig"
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"CSVの保存に失敗しました: {e}"
        }

    return {
        "status": "ok",
        "message": "CSVを report_t_all.csv に統合しました",
        "total_rows": len(merged_df)
    }
