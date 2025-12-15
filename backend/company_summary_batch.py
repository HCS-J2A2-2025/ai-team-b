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
# ====== 質問に出したくない話題（合否・内定など） ======
QUESTION_NG_WORDS = [
    "内定", "採用", "合格", "不合格", "落選", "結果", "通過", "辞退",
    "合否", "選考結果", "内々定", "オファー"
]


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

    ルール:
    - 表示は「一次面接 / 二次面接 / 三次面接 / 最終面接」の4種類に統一
    - total_rounds >= 4 の場合:
        1->一次, 2->二次, 3->三次, 4以降->最終
    - total_rounds <= 3 の場合:
        最後の回は必ず最終（2回で最終などに対応）
        それ以外は一次/二次/三次を割当
    """

    # --- 入力を安全にする ---
    try:
        round_index = int(round_index)
    except Exception:
        round_index = 1

    try:
        total_rounds = int(total_rounds)
    except Exception:
        total_rounds = round_index if round_index > 0 else 1

    if round_index <= 0:
        round_index = 1
    if total_rounds <= 0:
        total_rounds = 1

    # round_index が total を超える異常値も最後扱いに寄せる
    if round_index > total_rounds:
        round_index = total_rounds

    # --- 4回以上は「一次/二次/三次/最終」に丸める ---
    if total_rounds >= 4:
        if round_index == 1:
            return "一次面接"
        if round_index == 2:
            return "二次面接"
        if round_index == 3:
            return "三次面接"
        return "最終面接"

    # --- 1〜3回のとき：最後は必ず最終（2回で最終など） ---
    if round_index == total_rounds:
        return "最終面接"

    # 最後以外は順番通り
    if round_index == 1:
        return "一次面接"
    if round_index == 2:
        return "二次面接"
    return "三次面接"



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
                "model": "",
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

    # 学籍番号指定（個人モード）
    if student_no is not None and col_student in df_company.columns:
        df_company = df_company[df_company[col_student].astype(str).str.strip() == str(student_no).strip()].copy()
        if df_company.empty:
            return []

    # 面接のみ
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

    # 回次（学籍番号ごとに古→新で 1,2,3...）
    df_iv = df_iv.sort_values(["_student_key", "start_dt_obj"])
    df_iv["round_index"] = df_iv.groupby("_student_key").cumcount() + 1
    total_rounds_map = df_iv.groupby("_student_key")["round_index"].max().to_dict()

    # ---------------------------------------------------
    # ★ 10人分を集計する（最新10人）
    # ---------------------------------------------------
    latest_dt_per_student = (
        df_iv.groupby("_student_key")["start_dt_obj"]
            .max()
            .sort_values(ascending=False)
    )
    latest_student_keys = latest_dt_per_student.head(DISPLAY_RECORD_LIMIT).index.tolist()
    df_top = df_iv[df_iv["_student_key"].isin(latest_student_keys)].copy()
    if df_top.empty:
        return []

    # ラベル付け（一次/二次/三次/最終）
    def _round_label(row):
        key = str(row.get("_student_key", "UNKNOWN"))
        total = int(total_rounds_map.get(key, int(row.get("round_index", 1))))
        idx = int(row.get("round_index", 1))
        return calc_round_label(idx, total)

    df_top["round_label"] = df_top.apply(_round_label, axis=1)

    ordered_labels = ["一次面接", "二次面接", "三次面接", "最終面接"]

    records = []
    for label in ordered_labels:
        sub = df_top[df_top["round_label"] == label].copy()
        if sub.empty:
            continue

        # よくある形式（オンライン/対面）
        types = []
        all_questions = []
        memos = []

        for _, r in sub.iterrows():
            # type
            fmt_val = str(r.get(col_format, ""))
            types.append("オンライン" if "オンライン" in fmt_val else "対面")

            # questions
            raw_text = str(r.get(col_text, "") or "")
            qs_raw = extract_questions(raw_text, max_q=10)  # 少し多めに拾ってから落とす

            qs = []
            for q in qs_raw:
                # 内定/合否系は除外
                if any(w in q for w in QUESTION_NG_WORDS):
                    continue

                q2 = normalize_to_question(q)

                # 変なのを軽く除外（短すぎ/長すぎ）
                if 8 <= len(q2) <= 60 and (not any(w in q2 for w in QUESTION_NG_WORDS)):
                    qs.append(q2)

            # ここで上位5つだけにする
            qs = qs[:5]

            all_questions.extend(qs)

            # memo（雰囲気的な要約を短く：上位の内容をつなぐ）
            t = clean_text(raw_text)
            if t:
                memos.append(t[:120])

        # 質問：頻出順に並べる（最大5個）
        q_counter = Counter([q.strip() for q in all_questions if q.strip()])
        top_questions = [q for q, _ in q_counter.most_common(5)]

        # type：多数決
        type_label = Counter(types).most_common(1)[0][0] if types else ""

        # memo：代表文（長すぎないように）
        memo_text = " / ".join(memos[:2])
        memo_text = memo_text[:180] + ("…" if len(memo_text) > 180 else "")

        # UI互換で返す（4枚になる）
        records.append(
            {
                "id": label,                 # 4枚なので label をIDに
                "title": label,              # 一次/二次/三次/最終
                "year": "",                  # 必要なら後で入れる
                "term": "",
                "status": f"{len(sub)}件",   # 右のバッジを件数に
                "type": type_label,          # 多数派の形式
                "questions": top_questions,  # ← ここが「質問内容」に出る
                "memo": memo_text,           # 代表メモ
                "start_datetime": "",        # 使わないなら空でOK
            }
        )

    return records

def normalize_to_question(sentence: str) -> str:
    """
    文章を「面接で聞かれた質問文」っぽく正規化する
    - すでに質問なら整形だけ
    - 「〜について教えてください」などの重複を防ぐ
    """
    if not isinstance(sentence, str):
        return ""

    s = re.sub(r"\s+", " ", sentence).strip()
    if not s:
        return ""

    # 末尾の句点/読点などを軽く整理
    s = s.rstrip("。．!！")

    # すでに質問っぽい終わり方の定型
    already_question = (
        "教えてください" in s
        or "伺えますか" in s
        or "お願いします" in s
        or "ありますか" in s
        or "できますか" in s
        or s.endswith("か")
        or "？" in s
        or "?" in s
    )

    # すでに「〜について教えてください」が入ってるなら余計な付与をしない
    if "について教えてください" in s or "について教えて下さい" in s:
        # 「。について教えてください。」みたいな変な連結があれば修正
        s = s.replace("。について教えてください", "について教えてください")
        s = s.replace("。について教えて下さい", "について教えて下さい")
        # 「について教えてください。について教えてください」重複除去
        s = re.sub(r"(について教えてください。?)+$", "について教えてください", s)
        return s if s.endswith("？") or s.endswith("。") else s + "。"

    # すでに質問文なら、最後だけ整える
    if already_question:
        if ("？" not in s) and ("?" not in s) and not s.endswith("。"):
            # 「〜ですか」系は「？」に寄せる
            if s.endswith("か"):
                return s + "？"
            return s + "。"
        return s

    # 評価/感想っぽい語尾を除去
    s = re.sub(r"(が評価された|が確認された|が見られた|が高い|が強い|が必要|と感じた|と思った)$", "", s).strip()

    # 「〜について」だけで終わってたら「教えてください」を付ける
    if s.endswith("について") or s.endswith("に関して"):
        return s + "教えてください。"

    # それ以外はテンプレ質問にする
    return f"{s}について教えてください。"


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

def summarize_questions_by_round_for_latest_students(
    company_name: str,
    latest_students: int = 10,
    max_questions_per_record: int = 6,
    top_k: int = 5,
) -> dict:
    """
    企業×回次で、最新N人分の質問を集計して返す
    - 頻出質問: 人数カウント付き
    - 特徴的質問: 低頻度（1〜2人）だが内容が具体的なもの
    """

    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_text = "面接内容"
    col_student = "学籍番号"

    required = [col_company, col_event, col_start, col_text]
    if not set(required).issubset(df.columns):
        return {}

    # 対象企業・面接のみ
    df = df[
        (df[col_company].astype(str).str.strip() == str(company_name).strip()) &
        (df[col_event].astype(str).str.strip() == "試験_面接")
    ].copy()
    if df.empty:
        return {}

    # 日付整形
    df["start_dt_obj"] = pd.to_datetime(df[col_start], errors="coerce")
    df = df.dropna(subset=["start_dt_obj"]).copy()
    if df.empty:
        return {}

    # 学籍番号キー
    if col_student in df.columns:
        df["_student_key"] = df[col_student].astype(str).fillna("").str.strip()
        df.loc[df["_student_key"] == "", "_student_key"] = "UNKNOWN"
    else:
        # 学籍番号が無いなら「全員UNKNOWN」になり10人集計ができないので注意
        df["_student_key"] = "UNKNOWN"

    # round_index付与
    df = df.sort_values(["_student_key", "start_dt_obj"])
    df["round_index"] = df.groupby("_student_key").cumcount() + 1
    total_rounds_map = df.groupby("_student_key")["round_index"].max().to_dict()

    # 最新N人を決める（各人の最新日時でランキング）
    latest_dt_per_student = df.groupby("_student_key")["start_dt_obj"].max().sort_values(ascending=False)
    latest_student_keys = latest_dt_per_student.head(latest_students).index.tolist()

    df = df[df["_student_key"].isin(latest_student_keys)].copy()
    if df.empty:
        return {}

    # round_label付与（最終判定は総回数ベース）
    def classify_row(r) -> str:
        key = str(r.get("_student_key", "UNKNOWN"))
        total = int(total_rounds_map.get(key, int(r.get("round_index", 1))))
        idx = int(r.get("round_index", 1))
        return calc_round_label(idx, total)

    df["round_label"] = df.apply(classify_row, axis=1)

    ordered_labels = ["一次面接", "二次面接", "三次面接", "最終面接"]
    out = {}

    # ★質問を軽く正規化（見た目違いをまとめる）
    def normalize_question(q: str) -> str:
        q = re.sub(r"\s+", " ", str(q)).strip()
        q = q.replace("？", "?")
        q = re.sub(r"[?]+$", "？", q)  # 末尾は「？」に統一
        q = re.sub(r"^(Q\d+\.?\s*)", "", q, flags=re.IGNORECASE)
        return q

    for label in ordered_labels:
        sub = df[df["round_label"] == label].copy()
        if sub.empty:
            continue

        # 質問 -> その質問を出した学生集合（人数カウント）
        q_to_students = {}

        for _, r in sub.iterrows():
            key = str(r.get("_student_key", "UNKNOWN"))
            text = clean_text(str(r.get(col_text, "") or ""))

            qs = extract_questions(text, max_q=max_questions_per_record)
            for q in qs:
                nq = normalize_question(q)
                if not nq:
                    continue
                q_to_students.setdefault(nq, set()).add(key)

        # 頻出順
        freq = [(q, len(students)) for q, students in q_to_students.items()]
        freq.sort(key=lambda x: x[1], reverse=True)

        top_questions = []
        for q, cnt in freq[:top_k]:
            top_questions.append({"q": q, "count": cnt})

        # 特徴的（例：1人 or 2人、かつ長めで具体的な質問）
        unique_questions = []
        for q, cnt in freq:
            if cnt <= 2 and len(q) >= 14:
                unique_questions.append({"q": q, "count": cnt})
            if len(unique_questions) >= top_k:
                break

        out[label] = {
            "student_count": int(sub["_student_key"].nunique()),
            "top_questions": top_questions,
            "unique_questions": unique_questions,
        }

    return out



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