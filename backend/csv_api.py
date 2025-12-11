from fastapi import APIRouter, UploadFile, File
import os

router = APIRouter()

# 保存フォルダ
UPLOAD_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/api/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    # 拡張子チェック
    if not file.filename.lower().endswith(".csv"):
        return {"status": "error", "message": "CSVファイルのみアップロードできます"}

    save_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return {"status": "ok", "filename": file.filename}

