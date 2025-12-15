# company_summary_batch.py
# ------------------------------------------
# data/report_t_all.csv → data/company_summary_t.csv を作成し、
# さらに generate_detailed_report() で自然文レポートを生成する。
# フロント右側用の面接履歴（最新10人分）/ 質問抽出 / 回次ごとの傾向も返せる。
# ------------------------------------------
import os
import re
import json
from collections import Counter

import pandas as pd

import hmac
import hashlib
import base64

# ★ これを .env / 環境変数で必ず上書きする（dev用デフォルトは仮）
PUBLIC_ID_SECRET = os.getenv("PUBLIC_ID_SECRET", "dev-secret-change-me")

def make_public_id(report_id: str) -> str:
    """
    内部の report_id を安全な公開用IDに変換する（復元不可）
    - 同じ report_id → 常に同じ public_id
    - SECRET が漏れない限り総当たりで推測されにくい
    """
    if not report_id:
        return ""

    msg = str(report_id).encode("utf-8")
    key = PUBLIC_ID_SECRET.encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()

    # URLでも安全な短めID
    return base64.urlsafe_b64encode(digest[:16]).decode("utf-8").rstrip("=")

# ====== 設定 ======
BASE_DIR = os.path.dirname(__file__)
INPUT_CSV = os.path.join(BASE_DIR, "data", "report_t_all.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

LATEST_RECORDS_LIMIT = 5
DISPLAY_RECORD_LIMIT = 10  # 右側に出す最大件数（= 最新10人分）


# -----------------------------
# CSVを読み込んでカラム名を正規化（BOM / 空白 / 表記揺れなど）
# -----------------------------
def load_report_df():
    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")

    # 1) BOM / 前後の空白 / 中のスペースを削る
    fixed_cols = []
    for c in df.columns:
        s = str(c)
        s = s.lstrip("\ufeff")
        s = s.strip()
        s = s.replace(" ", "")
        fixed_cols.append(s)
    df.columns = fixed_cols

    # 2) 英語列名 → 日本語列名 にそろえる（どちらで来てもOK）
    rename_map = {}
    col_set = set(df.columns)

    if "企業名" not in col_set:
        if "企業" in col_set:
            rename_map["企業"] = "企業名"
        elif "company_name" in col_set:
            rename_map["company_name"] = "企業名"

    if "レポートID" not in col_set:
        if "report_id" in col_set:
            rename_map["report_id"] = "レポートID"
        elif "reportId" in col_set:
            rename_map["reportId"] = "レポートID"

    if "イベント種別" not in col_set and "event_kind" in col_set:
        rename_map["event_kind"] = "イベント種別"

    if "結果種別" not in col_set and "result_status" in col_set:
        rename_map["result_status"] = "結果種別"

    if "開始日時" not in col_set and "start_datetime" in col_set:
        rename_map["start_datetime"] = "開始日時"

    if "終了日時" not in col_set and "end_datetime" in col_set:
        rename_map["end_datetime"] = "終了日時"

    if "形式" not in col_set and "format" in col_set:
        rename_map["format"] = "形式"

    # 面接内容
    if "面接内容" not in col_set and "report_text" in col_set:
        rename_map["report_text"] = "面接内容"

    if "学籍番号" not in col_set and "student_no" in col_set:
        rename_map["student_no"] = "学籍番号"

    if "メールアドレス" not in col_set:
        for cand in ["email", "mail", "メール", "Email", "e-mail"]:
            if cand in col_set:
                rename_map[cand] = "メールアドレス"
                break

    if rename_map:
        df = df.rename(columns=rename_map)

    print("★ 正規化後カラム一覧:", df.columns.tolist())
    return df


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
    "逆質問": ["逆質問"],
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
    if not isinstance(text, str):
        return "不明"
    if "オンライン" in text or "WEB" in text.upper():
        return "オンライン"
    if "対面" in text or "来社" in text:
        return "対面"
    return "不明"


def detect_dress_code(text):
    if not isinstance(text, str):
        return "不明"
    if "スーツ" in text:
        return "スーツ"
    if "私服" in text or "オフィスカジュアル" in text:
        return "私服"
    return "不明"


def detect_atmosphere_rule(text):
    if not isinstance(text, str):
        return "不明"
    score = {"穏やか": 0, "フランク": 0, "厳しめ": 0, "圧迫感あり": 0}
    if any(w in text for w in ["穏やか", "丁寧", "優しい", "和やか"]):
        score["穏やか"] += 1
    if any(w in text for w in ["フランク", "話しやすい", "雑談"]):
        score["フランク"] += 1
    if any(w in text for w in ["厳しい", "深掘り", "シビア"]):
        score["厳しめ"] += 1
    if any(w in text for w in ["圧迫", "威圧"]):
        score["圧迫感あり"] += 1
    top = max(score, key=score.get)
    return top if score[top] > 0 else "不明"


# ====== 質問抽出 ======
def extract_questions(text: str, max_q: int = 6) -> list[str]:
    if not isinstance(text, str):
        return []

    t = text.replace("\r\n", "\n").strip()
    if not t:
        return []

    candidates: list[str] = []

    # ① 行内の「？」優先
    for line in t.split("\n"):
        line = line.strip().strip(" ・-　\t")
        if not line:
            continue
        if "？" in line or "?" in line:
            candidates.append(line)

    # ② 文中「？」分割
    if not candidates:
        parts = re.split(r"[？?]", t)
        for p in parts[:-1]:
            s = p.strip()
            if len(s) >= 6:
                candidates.append(s + "？")

    # ③ 話題羅列→質問文
    if not candidates:
        sep_normalized = t
        for sep in ["、", "・", "／", "/", "，", ",", "　"]:
            sep_normalized = sep_normalized.replace(sep, "|")
        topics = [x.strip() for x in sep_normalized.split("|") if x.strip()]

        cleaned_topics = []
        for x in topics:
            x = re.sub(r"(など|等|について|に関して)$", "", x).strip()
            if 2 <= len(x) <= 25:
                cleaned_topics.append(x)

        deny_words = ["オンライン", "対面", "面接", "分", "形式", "雰囲気", "服装"]
        cleaned_topics = [x for x in cleaned_topics if not any(w in x for w in deny_words)]

        for x in cleaned_topics:
            candidates.append(f"{x}について教えてください。")
            if len(candidates) >= max_q:
                break

    # ④ uniq + max
    uniq: list[str] = []
    seen = set()
    for q in candidates:
        q = re.sub(r"\s+", " ", q).strip()
        if q and q not in seen:
            uniq.append(q)
            seen.add(q)
        if len(uniq) >= max_q:
            break

    # ⑤ 0ならタグテンプレ
    if not uniq:
        tag_map = {
            "志望動機": "志望動機を教えてください。",
            "学校で学んだこと": "学校で学んだことを教えてください。",
            "チーム開発": "チーム開発の経験について教えてください。",
            "アルバイト経験": "アルバイト経験について教えてください。",
            "強み・弱み": "あなたの強み・弱みを教えてください。",
            "将来のキャリア": "将来のキャリアについて教えてください。",
            "成績": "成績や取り組みについて教えてください。",
            "コミュニケーション": "コミュニケーションで工夫したことを教えてください。",
            "自己PR": "自己PRをしてください。",
            "逆質問": "最後に逆質問はありますか？",
        }
        tags = detect_content_tags(t)
        for tag in tags[:max_q]:
            if tag in tag_map:
                uniq.append(tag_map[tag])

    return uniq


# ============================================================
# ★重要：回次ラベル（2回目が最終になるケース対応）
# ============================================================
def calc_round_label(round_index: int, total_rounds: int) -> str:
    """
    round_index : 1,2,3...
    total_rounds: その学生がその企業で受けた面接総数
    """
    try:
        round_index = int(round_index)
    except Exception:
        round_index = 1
    try:
        total_rounds = int(total_rounds)
    except Exception:
        total_rounds = round_index if round_index > 0 else 1

    if total_rounds <= 0:
        total_rounds = 1
    if round_index <= 0:
        round_index = 1

    # 最後の回は必ず最終
    if round_index == total_rounds:
        return "最終面接"

    if round_index == 1:
        return "一次面接"
    if round_index == 2:
        return "二次面接"
    if round_index == 3:
        return "三次面接"
    return f"{round_index}次面接"


# ====== 企業ごとサマリ作成（company_summary_t用） ======
def summarize_company(group_df: pd.DataFrame) -> dict:
    col_company = "企業名"
    col_event = "イベント種別"
    col_result = "結果種別"
    col_start = "開始日時"
    col_text = "面接内容"

    if not {col_company, col_event, col_result, col_start, col_text}.issubset(group_df.columns):
        print("[WARN] summarize_company: 必須カラム不足:", group_df.columns)
        return {}

    company_name = str(group_df[col_company].iloc[0])

    formats, dresses, atmospheres = [], [], []
    content_tags_all, latest_records_list = [], []

    sorted_df = group_df.copy()
    sorted_df["start_dt_obj"] = pd.to_datetime(sorted_df[col_start], errors="coerce")
    sorted_df = sorted_df.sort_values("start_dt_obj", ascending=False)

    for _, row in sorted_df.iterrows():
        text = clean_text(row.get(col_text, ""))
        fmt = detect_format(text)
        dress = detect_dress_code(text)
        atm = detect_atmosphere_rule(text)
        tags = detect_content_tags(text)

        formats.append(fmt)
        dresses.append(dress)
        atmospheres.append(atm)
        content_tags_all.extend(tags)

        latest_records_list.append(f"{row.get(col_start,'')} {row.get(col_event,'')} {row.get(col_result,'')} {fmt}")

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


# ====== LLM による自然文レポート生成 ======
def generate_detailed_report(row: pd.Series) -> str:
    import requests

    company_name = row["company_name"]
    tags = json.loads(row["content_top_tags"])
    atmos = json.loads(row["atmosphere_dist"])
    form = json.loads(row["format_dist"])
    dress = json.loads(row["dress_code_dist"])
    latest = json.loads(row["latest_records"])

    SYSTEM_PROMPT = """
あなたは「日本語文章生成の専門家」かつ「キャリアセンターのプロアドバイザー」です。

【最重要ルール】
- 出力は「日本語のみ」。英単語・英文・( ) 内の英語訳などを一切書かない
- タグや元データに英語が含まれていても、そのまま写さず日本語に言い換える
- 固有名詞の捏造（例：〇〇氏など）は絶対にしない
- CSV に存在する情報以外は推測しない
- 文体は必ず丁寧語（です・ます調）
- 出力フォーマットを絶対に守る

【出力フォーマット】
以下の４つのブロックをこの順番・この見出しで出力してください。

■ 雰囲気
1〜3文で、面接の雰囲気を自然な日本語で説明してください。

■ よく聞かれる質問
箇条書き（「・」または「-」）で3〜6個程度、よく聞かれる質問テーマを書いてください。
テーマ名のみを日本語で書いてください（英語訳は禁止）。

■ 服装
1〜2文で、服装の基本方針を自然な日本語で説明してください。

■ 面接形式
1〜2文で、オンライン・対面の割合などを説明してください。

※データにない情報を無理に推測して書かないこと。
※英語は禁止。出力はすべて自然な日本語のみとすること。
"""

    USER_PROMPT = f"""
以下は企業「{company_name}」に関する面接データです。
このデータだけをもとに、指定された４ブロック構成でレポートを作成してください。

【質問内容の傾向（タグ）】
{tags}

【面接の雰囲気の分布】
{atmos}

【面接形式の分布】
{form}

【服装の分布】
{dress}

【直近の面接記録】
{latest}
"""

    base = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "http://" + base
    url = base.rstrip("/") + "/api/generate"
    prompt = SYSTEM_PROMPT.strip() + "\n\n" + USER_PROMPT.strip()

    try:
        response = requests.post(
            url,
            json={
                "model": "qwen2.5:14b-instruct",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4},
            },
            timeout=600,
        )
    except Exception as e:
        return f"[ERROR] Ollama への接続に失敗しました: {e}"

    if not response.ok:
        return f"[ERROR] Ollama API error {response.status_code}: {response.text}"

    data = response.json()
    return data.get("response", "").strip() or "[ERROR] Ollama から空の応答が返されました"


# ============================================================
# ★右側：最新10人分（学籍番号ごとの最新1件）を records として返す
#   ただし title は「その人の総回数」を見て最終判定する
# ============================================================
def build_interview_records_for_company(company_name: str, student_no: str | None = None):
    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_result = "結果種別"
    col_start = "開始日時"
    col_format = "形式"
    col_student = "学籍番号"
    col_text = "面接内容"
    col_report_id = "レポートID"

    required = [col_company, col_event, col_result, col_start, col_format, col_text]
    if not set(required).issubset(df.columns):
        print("[WARN] build_interview_records_for_company: 必須カラム不足:", df.columns.tolist())
        return []

    target_name = str(company_name).strip()
    company_series = df[col_company].astype(str).str.strip()

    # 企業フィルタ（完全一致→ダメなら部分一致）
    df_company = df[company_series == target_name].copy()
    if df_company.empty:
        df_company = df[company_series.str.contains(target_name, na=False, regex=False)].copy()
        if df_company.empty:
            return []

    # 学籍番号指定があれば、その人だけ（互換）
    if student_no is not None and col_student in df_company.columns:
        df_company = df_company[df_company[col_student].astype(str).str.strip() == str(student_no).strip()].copy()
        if df_company.empty:
            return []

    # 面接のみ（筆記などは除外）
    df_iv = df_company[df_company[col_event].astype(str).str.strip() == "試験_面接"].copy()
    if df_iv.empty:
        return []

    # 日付
    df_iv["start_dt_obj"] = pd.to_datetime(df_iv[col_start], errors="coerce")
    df_iv = df_iv.dropna(subset=["start_dt_obj"]).copy()
    if df_iv.empty:
        return []

    # 学籍番号キー
    if col_student in df_iv.columns:
        df_iv["_student_key"] = df_iv[col_student].astype(str).fillna("").str.strip()
        df_iv.loc[df_iv["_student_key"] == "", "_student_key"] = "UNKNOWN"
    else:
        df_iv["_student_key"] = "UNKNOWN"

    # 何回目（学籍番号ごと）
    df_iv = df_iv.sort_values(["_student_key", "start_dt_obj"])
    df_iv["round_index"] = df_iv.groupby("_student_key").cumcount() + 1

    # 総回数（学籍番号ごと）
    total_rounds_map = df_iv.groupby("_student_key")["round_index"].max().to_dict()

    # 最新10人（各人の最新1件）
    latest_each_student = (
        df_iv.sort_values("start_dt_obj")
            .groupby("_student_key", as_index=False)
            .tail(1)
            .copy()
    )
    latest_each_student = latest_each_student.sort_values("start_dt_obj", ascending=False).head(DISPLAY_RECORD_LIMIT)
    latest_each_student = latest_each_student.sort_values("start_dt_obj")  # 表示順は古→新

    records = []
    for i, row in latest_each_student.reset_index(drop=True).iterrows():
        result = str(row.get(col_result, "")).strip()
        status_label = "合格" if result in ["継続（合格）", "内定"] else "落選"

        fmt_val = str(row.get(col_format, ""))
        type_label = "オンライン" if "オンライン" in fmt_val else "対面"

        start_dt = row.get("start_dt_obj", pd.NaT)
        year_str = f"{start_dt.year}年" if not pd.isna(start_dt) else ""

        report_id = str(row.get(col_report_id, "")).strip()
        if not report_id:
            report_id = f"{target_name}_{row.get(col_start,'')}_{i}"

        # ★ public_id（外に出すID）
        public_id = make_public_id(report_id)

        raw_text = str(row.get(col_text, "") or "")
        questions = extract_questions(raw_text, max_q=6)

        memo = clean_text(raw_text)
        memo = memo[:180] + ("…" if len(memo) > 180 else "")

        r_idx = int(row.get("round_index", 1))
        student_key = str(row.get("_student_key", "UNKNOWN"))
        total_rounds = int(total_rounds_map.get(student_key, r_idx))

        title = calc_round_label(r_idx, total_rounds)

        # ✅ 内部用：report_idは保持（後でdetailで逆引きに使う）
        records.append(
            {
                "id": public_id,                 # ← 外に出す
                "_report_id": report_id,         # ← 外に出さない（先頭_にして分かりやすく）
                "student_no": str(row.get(col_student, "")).strip() if col_student in latest_each_student.columns else "",
                "round_index": r_idx,
                "total_rounds": total_rounds,
                "title": title,
                "year": year_str,
                "term": "",
                "status": status_label,
                "type": type_label,
                "questions": questions,          # ← resultで返さないなら残してOK（内部用）
                "memo": memo,                    # ← resultで返さないなら残してOK（内部用）
                "start_datetime": str(row.get(col_start, "")),
            }
        )

    return records



# ============================================================
# ★企業ごと：一次→二次→三次→最終 の順で「傾向」を返す
#   ※ round_index==4 を最終と決め打ちしない（2回で最終もある）
# ============================================================
def summarize_latest_trends_by_round(company_name: str, limit_records: int = 50) -> dict:
    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_text = "面接内容"
    col_student = "学籍番号"

    required = [col_company, col_event, col_start, col_text]
    if not set(required).issubset(df.columns):
        return {}

    df = df[
        (df[col_company].astype(str).str.strip() == str(company_name).strip()) &
        (df[col_event].astype(str).str.strip() == "試験_面接")
    ].copy()

    if df.empty:
        return {}

    df["start_dt_obj"] = pd.to_datetime(df[col_start], errors="coerce")
    df = df.dropna(subset=["start_dt_obj"]).copy()
    if df.empty:
        return {}

    # 学籍番号キー
    if col_student in df.columns:
        df["_student_key"] = df[col_student].astype(str).fillna("").str.strip()
        df.loc[df["_student_key"] == "", "_student_key"] = "UNKNOWN"
    else:
        df["_student_key"] = "UNKNOWN"

    # 何回目（学籍番号ごと）
    df = df.sort_values(["_student_key", "start_dt_obj"])
    df["round_index"] = df.groupby("_student_key").cumcount() + 1

    # 総回数（学籍番号ごと）
    total_rounds_map = df.groupby("_student_key")["round_index"].max().to_dict()

    # 直近 limit_records 件（新しい順）
    df_latest = df.sort_values("start_dt_obj", ascending=False).head(limit_records).copy()

    # ★各行を「一次/二次/三次/最終」に分類（総回数を見て最終判定）
    def classify_row(r) -> str:
        key = str(r.get("_student_key", "UNKNOWN"))
        total = int(total_rounds_map.get(key, int(r.get("round_index", 1))))
        idx = int(r.get("round_index", 1))
        return calc_round_label(idx, total)

    df_latest["round_label"] = df_latest.apply(classify_row, axis=1)

    ordered_labels = ["一次面接", "二次面接", "三次面接", "最終面接"]

    result = {}
    for label in ordered_labels:
        sub = df_latest[df_latest["round_label"] == label]
        if sub.empty:
            continue

        atmospheres, formats, dresses = [], [], []
        question_tags, extracted_questions = [], []

        for _, r in sub.iterrows():
            text = clean_text(str(r.get(col_text, "") or ""))
            atmospheres.append(detect_atmosphere_rule(text))
            formats.append(detect_format(text))
            dresses.append(detect_dress_code(text))
            question_tags.extend(detect_content_tags(text))
            extracted_questions.extend(extract_questions(text, max_q=3))

        result[label] = {
            "atmosphere": [k for k, _ in Counter(atmospheres).most_common(2)],
            "format": [k for k, _ in Counter(formats).most_common(2)],
            "dress": [k for k, _ in Counter(dresses).most_common(2)],
            "question_tags": [k for k, _ in Counter(question_tags).most_common(5)],
            "sample_questions": list(dict.fromkeys(extracted_questions))[:5],
            "count": int(len(sub)),
        }

    return result


# ====== 最新 N 件の生テキスト取得 ======
def get_latest_interview_texts(company_name: str, limit: int = 5):
    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_text = "面接内容"

    if not {col_company, col_event, col_start, col_text}.issubset(df.columns):
        print("[WARN] get_latest_interview_texts: 必須カラム不足:", df.columns)
        return []

    df = df[
        df[col_company].astype(str).str.contains(company_name, na=False, regex=False) &
        (df[col_event].astype(str).str.strip() == "試験_面接")
    ].copy()

    if df.empty:
        return []

    df["start_dt_obj"] = pd.to_datetime(df[col_start], errors="coerce")
    df = df.dropna(subset=["start_dt_obj"]).copy()
    if df.empty:
        return []

    df = df.sort_values("start_dt_obj", ascending=False)
    texts = df[col_text].fillna("").head(limit).tolist()
    print("get_latest_interview_texts 件数:", len(texts))
    return texts


# ====== main ======
def main():
    print("📁 report_t_all CSV 読み込み中...")
    df = load_report_df()
    print(f"✅ 読み込み完了: {len(df)} 件")

    col_company = "企業名"
    if col_company not in df.columns:
        print("[ERROR] 企業名カラムが見つかりません:", df.columns)
        return

    print("🏭 企業ごとの集計処理を開始...")
    summary_list = []
    for company, group in df.groupby(col_company):
        print(f"  ├ 集計中: {company}（{len(group)} 件）")
        row_dict = summarize_company(group)
        if row_dict:
            summary_list.append(row_dict)

    summary_df = pd.DataFrame(summary_list)
    summary_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n🎉 完了！ company_summary_t を出力しました → {OUTPUT_CSV}")

    print("\n--------------------------------------")
    name = input("自然文レポートを生成したい企業名を入力してください： ").strip()
    print("--------------------------------------\n")

    hit = summary_df[summary_df["company_name"].astype(str).str.contains(name, na=False)]
    if hit.empty:
        print("❌ 該当する企業が見つかりません")
        return

    row = hit.iloc[0]
    print("\n==============================")
    print(f"📌 自然文レポート：{row['company_name']}")
    print("==============================\n")
    print(generate_detailed_report(row))

    # おまけ：傾向を表示したい場合
    trends = summarize_latest_trends_by_round(str(row["company_name"]), limit_records=50)
    if trends:
        print("\n==============================")
        print("📌 回次ごとの最新傾向（一次→二次→三次→最終）")
        print("==============================")
        print(json.dumps(trends, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
