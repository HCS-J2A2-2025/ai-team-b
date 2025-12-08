# company_summary_batch.py
# ------------------------------------------
# report_t_all.csv → company_summary_t.csv を作成し
# さらに generate_detailed_report() を呼んで自然文レポートを生成できる完全版
# ------------------------------------------
import os

import pandas as pd
import json
import re
from collections import Counter
from datetime import datetime

# ====== 設定 ======
BASE_DIR = os.path.dirname(__file__)
INPUT_CSV = os.path.join(BASE_DIR, "data", "report_t_all.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "company_summary_t.csv")
LATEST_RECORDS_LIMIT = 5


# ====== テキスト整形 ======
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"。+", "。", text)
    text = re.sub(r"、+", "、", text)
    return text.strip()


# ====== タグ抽出 ======
CONTENT_TAG_RULES = {
    "志望動機": ["志望動機", "なぜこの会社", "なぜ当社"],
    "学校で学んだこと": ["学校で", "授業で", "学んだ", "カリキュラム"],
    "チーム開発": ["チーム開発", "グループ開発", "共同開発"],
    "アルバイト経験": ["アルバイト", "バイト"],
    "強み・弱み": ["長所", "短所", "強み", "弱み"],
    "将来のキャリア": ["キャリア", "将来"],
    "成績": ["成績", "順位"],
    "家族・家庭": ["家族", "家庭"],
    "コミュニケーション": ["コミュニケーション"],
    "自己PR": ["自己PR"],
    "逆質問": ["逆質問"]
}

def detect_content_tags(text):
    if not isinstance(text, str):
        return []
    tags = []
    for tag, words in CONTENT_TAG_RULES.items():
        if any(w in text for w in words):
            tags.append(tag)
    return tags


def detect_format(text):
    if "オンライン" in text or "WEB" in text.upper():
        return "オンライン"
    if "対面" in text or "来社" in text:
        return "対面"
    return "不明"


def detect_dress_code(text):
    if "スーツ" in text:
        return "スーツ"
    if "私服" in text:
        return "私服"
    return "不明"


def detect_atmosphere_rule(text):
    score = {"穏やか": 0, "フランク": 0, "厳しめ": 0, "圧迫感あり": 0}
    if any(w in text for w in ["穏やか", "丁寧", "優しい"]):
        score["穏やか"] += 1
    if any(w in text for w in ["フランク", "話しやすい"]):
        score["フランク"] += 1
    if any(w in text for w in ["厳しい", "深掘り"]):
        score["厳しめ"] += 1
    if any(w in text for w in ["圧迫", "威圧"]):
        score["圧迫感あり"] += 1
    top = max(score, key=score.get)
    return top if score[top] > 0 else "不明"


# ====== 企業ごとサマリ作成 ======
def summarize_company(group_df):
    company_name = group_df["company_name"].iloc[0]

    formats, dresses, atmospheres = [], [], []
    content_tags_all, latest_records_list = [], []

    sorted_df = group_df.copy()
    sorted_df["start_dt_obj"] = pd.to_datetime(sorted_df["start_datetime"], errors="ignore")
    sorted_df = sorted_df.sort_values("start_dt_obj", ascending=False)

    for _, row in sorted_df.iterrows():
        text = clean_text(row["report_text"])
        fmt = detect_format(text)
        dress = detect_dress_code(text)
        atm = detect_atmosphere_rule(text)
        tags = detect_content_tags(text)

        formats.append(fmt)
        dresses.append(dress)
        atmospheres.append(atm)
        content_tags_all.extend(tags)

        latest_records_list.append(f"{row['start_datetime']} {row['event_kind']} {row['result_status']} {fmt}")

    def calc_dist(values):
        c = Counter(v for v in values if v != "不明")
        total = sum(c.values())
        if total == 0:
            return {}
        return {k: round(v / total, 3) for k, v in c.items()}

    return {
        "company_name": company_name,
        "content_top_tags": json.dumps([t for t, _ in Counter(content_tags_all).most_common(5)], ensure_ascii=False),
        "atmosphere_dist": json.dumps(calc_dist(atmospheres), ensure_ascii=False),
        "format_dist": json.dumps(calc_dist(formats), ensure_ascii=False),
        "dress_code_dist": json.dumps(calc_dist(dresses), ensure_ascii=False),
        "latest_records": json.dumps(latest_records_list[:LATEST_RECORDS_LIMIT], ensure_ascii=False),
    }


# ====== ★あなたの generate_detailed_report を統合 ======
def generate_detailed_report(row):
    import json
    import requests

    # -----------------------------
    # 1. CSV データを読み込み
    # -----------------------------
    company_name = row["company_name"]
    tags = json.loads(row["content_top_tags"])
    atmos = json.loads(row["atmosphere_dist"])
    form = json.loads(row["format_dist"])
    dress = json.loads(row["dress_code_dist"])
    latest = json.loads(row["latest_records"])

    # -----------------------------
    # 2. 高品質 system prompt（AIに性格と役割を与える）
    # -----------------------------
    SYSTEM_PROMPT = """
あなたは「日本語文章生成の専門家」かつ「キャリアセンターのプロアドバイザー」です。

【最重要ルール】
- 日本語として不自然・破綻した文を絶対に生成しない
- 固有名詞の捏造（例：フランク氏など）は絶対にしない
- CSV に存在する情報以外は推測しない
- 「読み物として自然な文章」を生成する
- 文体は必ず丁寧語（です・ます調）
- ロジックの整合性を保つ（論理の飛躍を禁止）

【文章構成（必ずこの順番）】
① 企業全体の特徴と面接傾向の総括
② よく聞かれる質問テーマと、その背景
③ 面接の雰囲気（割合をもとに自然に説明）
④ 面接形式（オンライン/対面の比率と理由）
⑤ 服装の傾向とそこから読み取れる企業文化
⑥ 直近の面接記録の傾向と読み取れるポイント
⑦ 評価されやすい人物像
⑧ 学生への具体的なアドバイス
⑨ 最後に 100〜200字のまとめ

【文体ルール】
- 明確・論理的・自然・破綻なし
- 無理に難しい言葉は使わない
- 感情表現は控えめ
"""

    # -----------------------------
    # 3. user prompt（CSV からのデータをそのまま渡す）
    # -----------------------------
    USER_PROMPT = f"""
以下は企業「{company_name}」に関する面接データです。
このデータのみを使い、800〜1500字で自然な日本語の面接傾向レポートを作成してください。

【質問内容の傾向】
{tags}

【面接の雰囲気の分布】
{atmos}

【面接形式】
{form}

【服装】
{dress}

【直近の面接記録】
{latest}

※データにない情報を推測して書かないこと。
※固有名詞の捏造は禁止。
"""

    # -----------------------------
    # 4. ローカル LLM に送信
    # -----------------------------
    response = requests.post(
        "http://localhost:11434/v1/chat/completions",
        json={
            "model": "phi3",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ],
            "temperature": 0.4,   # ←自然な文章に最適
        }
    )

    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"].strip()





# ====== main ======
def main():
    print("📁 report_t CSV 読み込み中...")
    df = pd.read_csv(INPUT_CSV)
    print(f"✅ 読み込み完了: {len(df)} 件")

    print("🏭 企業ごとの集計処理を開始...")
    summary_list = []
    for company, group in df.groupby("company_name"):
        print(f"  ├ 集計中: {company}（{len(group)} 件）")
        summary_list.append(summarize_company(group))

    summary_df = pd.DataFrame(summary_list)
    summary_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n🎉 完了！ company_summary_t を出力しました → {OUTPUT_CSV}")

    # ================================
    # ★ここから企業選択モードに変更
    # ================================

    print("\n--------------------------------------")
    name = input("自然文レポートを生成したい企業名を入力してください： ").strip()
    print("--------------------------------------\n")

    # 部分一致検索
    hit = summary_df[summary_df["company_name"].str.contains(name, na=False)]

    if hit.empty:
        print("❌ 該当する企業が見つかりません")
        return

    if len(hit) > 1:
        print(f"⚠ {len(hit)}件ヒットしました。最初の1件を使用します。")

    row = hit.iloc[0]

    print("\n==============================")
    print(f"📌 自然文レポート：{row['company_name']}")
    print("==============================\n")
    print(generate_detailed_report(row))


if __name__ == "__main__":
    main()
