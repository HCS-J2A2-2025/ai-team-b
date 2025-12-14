import pandas as pd
import json
import requests
from pathlib import Path

# ============================
#  CSV 読み込み
# ============================

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "report_t_all.csv"

print(f"読み込みパス: {CSV_PATH}")

df = pd.read_csv(CSV_PATH, encoding="utf-8")

# 日付変換（安全版）
df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
df["終了日時"] = pd.to_datetime(df["終了日時"], errors="coerce")

# JSON に書けるように文字列化
df["start_datetime"] = df["start_datetime"].astype(str)
df["終了日時"] = df["終了日時"].astype(str)

# 学籍番号ごとにグループ化
grouped = df.groupby("学籍番号")


# ============================
#  AI設定（Ollama）
# ============================

AI_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

USE_AI = False  # ★ AIを使わない（高速にする）


def ask_ai(prompt):
    """壊れても落ちない安全版"""
    try:
        res = requests.post(AI_URL, json={"model": MODEL, "prompt": prompt})
        try:
            return res.json().get("response", "")
        except:
            return res.text
    except:
        return "（AI分析に失敗しました）"

# ============================
#  学生ごとの AI 分析＋統計生成
# ============================

result = {}

for student_id, group in grouped:

    # レポート全文
    full_report = "\n\n".join(group["report_text"].astype(str).tolist())

    # プロンプト
    prompt = f"""
学生 {student_id} の面接レポートです。
受験傾向と強み・弱みを分析してください。

【データ】
{full_report}
"""

    # AIのON/OFFに対応（未定義エラーを完全回避）
    if USE_AI:
        ai_summary = ask_ai(prompt)
    else:
        ai_summary = "（AI分析はOFFです）"

    # 統計作成
    result[student_id] = {
        "企業一覧": group["企業名"].unique().tolist(),
        "面接日程": group[["企業名", "start_datetime", "終了日時", "result_status"]].to_dict(orient="records"),
        "受験回数": len(group),
        "受験期間": f"{group['start_datetime'].min()} ～ {group['start_datetime'].max()}",
        "形式傾向": group["形式"].value_counts().to_dict(),
        "面接官傾向": group["役職"].value_counts().to_dict(),
        "AI分析レポート": ai_summary
    }


# ============================
#  JSON 出力
# ============================

OUTPUT_PATH = BASE_DIR / "student_analysis.json"

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("🎉 student_analysis.json を生成しました！")
print(f"出力パス: {OUTPUT_PATH}")
