import pandas as pd
import json
import requests

# === CSV 読み込み ===
df = pd.read_csv(
    r"C:\Users\01120\OneDrive\デスクトップ\AI-team-B\backend\data\report_t_all.csv",
    encoding="utf-8"
)

# === 日付列をパース ===
df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")
df["終了日時"] = pd.to_datetime(df["終了日時"], errors="coerce")

# === グループ化 ===
grouped = df.groupby("学籍番号")

# === AI API 設定（Ollama）===
AI_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"   # 好きなモデルに変更可

def ask_ai(prompt):
    """Ollama に問い合わせて要約を取得する"""
    try:
        res = requests.post(
            AI_URL,
            json={"model": MODEL, "prompt": prompt}
        )
        data = res.json()
        return data.get("response", "（AI 出力なし）")
    except Exception as e:
        print("AI 接続エラー:", e)
        return "（AI 分析に失敗しました）"


# === 学生ごとに処理 ===
result = {}

for student_id, group in grouped:

    # AI へ渡す面接レポート全文
    full_report_text = "\n\n".join(group["report_text"].astype(str).tolist())

    # AI プロンプト
    prompt = f"""
以下は学生 {student_id} が受験した複数の面接レポートです。
この学生の『受験傾向』『強み』『弱点』『向いている企業タイプ』『改善点』を総合的に分析してください。

【出力フォーマット】
1. 受験企業の特徴
2. 面接日程の傾向
3. 合格しやすいパターン
4. 不合格になりやすいパターン
5. 強み
6. 改善点
7. この学生に向いている企業タイプ
8. 総評（200〜400文字）

【面接レポート】
{full_report_text}
"""

    ai_summary = ask_ai(prompt)

    # JSON 用データ生成
    result[student_id] = {
        "企業一覧": group["企業名"].unique().tolist(),
        "面接日程": group[["企業名", "start_datetime", "終了日時", "result_status"]].to_dict(orient="records"),
        "受験回数": len(group),
        "受験期間": f"{group['start_datetime'].min()} ～ {group['start_datetime'].max()}",
        "形式傾向": group["形式"].value_counts().to_dict(),
        "面接官傾向": group["役職"].value_counts().to_dict(),
        "AI分析レポート": ai_summary
    }

# === JSON 書き込み ===
with open("student_analysis.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("🎉 student_analysis.json を AI 分析付きで生成しました！")
