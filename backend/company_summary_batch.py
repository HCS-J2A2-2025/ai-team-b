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
from pathlib import Path

import pandas as pd
import requests

import hmac
import hashlib
import base64

# これを .env / 環境変数で必ず上書きする（dev用デフォルトは仮）
PUBLIC_ID_SECRET = os.getenv("PUBLIC_ID_SECRET", "dev-secret-change-me")

# =========================
# AI switches（右も左も動かす）
# =========================
ENABLE_LEFT_AI = True
ENABLE_RIGHT_AI = True

# ====== 設定 ======
BASE_DIR = os.path.dirname(__file__)
INPUT_CSV = os.path.join(BASE_DIR, "data", "report_t_all.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

LATEST_RECORDS_LIMIT = 5
DISPLAY_RECORD_LIMIT = 10  # 右側に出す最大件数（= 最新10人分）

# ====== 質問に出したくない話題（合否・内定など） ======
QUESTION_NG_WORDS = [
    "内定", "採用", "合格", "不合格", "落選", "結果", "通過", "辞退",
    "合否", "選考結果", "内々定", "オファー"
]

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


# ============================================================
# 共通：CSV読み込み（BOM / 空白 / 表記揺れの吸収）
# ============================================================
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

    return df


# ============================================================
# テキスト整形
# ============================================================
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"。+", "。", text)
    text = re.sub(r"、+", "、", text)
    return text.strip()


# ============================================================
# ルール抽出（タグ/形式/服装/雰囲気）
# ============================================================
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


# ============================================================
# 質問抽出（ルール）
# ============================================================
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
# 回次ラベル（2回目が最終になるケース対応）
# ============================================================
def calc_round_label(round_index: int, total_rounds: int) -> str:
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

    if round_index > total_rounds:
        round_index = total_rounds

    if total_rounds >= 4:
        if round_index == 1:
            return "一次面接"
        if round_index == 2:
            return "二次面接"
        if round_index == 3:
            return "三次面接"
        return "最終面接"

    if round_index == total_rounds:
        return "最終面接"

    if round_index == 1:
        return "一次面接"
    if round_index == 2:
        return "二次面接"
    return "三次面接"


# ============================================================
# 公開ID
# ============================================================
def make_public_id(report_id: str) -> str:
    if not report_id:
        return ""
    msg = str(report_id).encode("utf-8")
    key = PUBLIC_ID_SECRET.encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:16]).decode("utf-8").rstrip("=")


# ============================================================
# AI 呼び出し（統一：system + user 対応）
# ============================================================
def ask_ai(user_prompt: str, system_prompt: str | None = None) -> str:
    base = str(os.getenv("OLLAMA_HOST", "http://localhost:11434") or "").strip()
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    url = base.rstrip("/") + "/api/generate"

    model = str(os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct") or "").strip()
    if not model:
        model = "qwen2.5:14b-instruct"

    prompt = user_prompt if not system_prompt else (system_prompt.strip() + "\n\n" + user_prompt.strip())

    try:
        r = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4},
            },
            timeout=600,
        )
    except Exception as e:
        return f"[ERROR] Ollama への接続に失敗しました: {e}"

    if not r.ok:
        return f"[ERROR] Ollama API error {r.status_code}: {r.text}"

    data = r.json() or {}
    return (data.get("response") or "").strip()


# ============================================================
# JSON取り出し（LLMが前後に余計な文章を付けても救う）
# ============================================================
def _extract_json_object(text: str) -> dict | None:
    if not isinstance(text, str):
        return None
    s = text.strip()

    # 1) まず素直に
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) ```json ... ``` の中
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", s, flags=re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        try:
            obj = json.loads(inner)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # 3) 最初の { と最後の } で切り出す
    l = s.find("{")
    r = s.rfind("}")
    if l != -1 and r != -1 and r > l:
        inner = s[l:r+1]
        try:
            obj = json.loads(inner)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None

    return None


# ============================================================
# 質問文っぽく正規化
# ============================================================
def normalize_to_question(sentence: str) -> str:
    if not isinstance(sentence, str):
        return ""

    s = re.sub(r"\s+", " ", sentence).strip()
    if not s:
        return ""

    s = s.rstrip("。．!！")

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

    if "について教えてください" in s or "について教えて下さい" in s:
        s = s.replace("。について教えてください", "について教えてください")
        s = s.replace("。について教えて下さい", "について教えて下さい")
        s = re.sub(r"(について教えてください。?)+$", "について教えてください", s)
        return s if s.endswith("？") or s.endswith("。") else s + "。"

    if already_question:
        if ("？" not in s) and ("?" not in s) and not s.endswith("。"):
            if s.endswith("か"):
                return s + "？"
            return s + "。"
        return s

    s = re.sub(r"(が評価された|が確認された|が見られた|が高い|が強い|が必要|と感じた|と思った)$", "", s).strip()

    if s.endswith("について") or s.endswith("に関して"):
        return s + "教えてください。"

    return f"{s}について教えてください。"


# ============================================================
# 右AI：質問TOP + memo を LLM で生成
# ============================================================
def build_right_ai_questions_and_memo(
    company_name: str,
    round_label: str,
    texts: list[str],
    top_k: int = 5,
) -> tuple[list[str], str]:
    cleaned = [clean_text(t) for t in texts if isinstance(t, str) and t.strip()]
    if not cleaned:
        return [], ""

    joined = "\n\n".join(f"- {t[:700]}" for t in cleaned[:8])
    joined = joined[:6000]

    system = f"""
あなたはキャリアセンターの面接分析アシスタントです。

【絶対ルール】
- 出力は日本語のみ
- 推測で事実を足さない
- 評価文（「〜が評価された」「〜が不足」等）を質問に変換しない
- 面接で“聞かれる形”に言い換えはOKだが、ログから逸脱しない
- 合否/内定/結果の話題は質問に出さない

【出力フォーマット（JSONのみ）】
{{
  "questions": ["..."],
  "memo": "..."
}}

- questions は最大 {top_k} 個
- memo は1〜2文（短く）
""".strip()

    user = f"""
企業: {company_name}
回次: {round_label}

【面接ログ】
{joined}
""".strip()

    raw = ask_ai(user, system_prompt=system)

    obj = _extract_json_object(raw)
    if not obj:
        return [], ""

    qs = obj.get("questions", [])
    memo = obj.get("memo", "")

    if not isinstance(qs, list):
        qs = []

    out_qs = []
    for q in qs:
        s = re.sub(r"\s+", " ", str(q)).strip()
        if not s:
            continue
        if any(w in s for w in QUESTION_NG_WORDS):
            continue
        s = normalize_to_question(s)
        out_qs.append(s)

    out_qs = out_qs[:top_k]
    memo = re.sub(r"\s+", " ", str(memo)).strip()

    return out_qs, memo


# ============================================================
# 左AI：企業の自然文レポート
# ============================================================
def generate_detailed_report(row: pd.Series) -> str:
    if not ENABLE_LEFT_AI:
        return ""

    company_name = str(row.get("company_name", "") or "").strip()
    if not company_name:
        return ""

    def _load_json(val, default):
        try:
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return val
            s = str(val).strip()
            if not s:
                return default
            return json.loads(s)
        except Exception:
            return default

    tags = _load_json(row.get("content_top_tags"), [])
    atmos = _load_json(row.get("atmosphere_dist"), {})
    form = _load_json(row.get("format_dist"), {})
    dress = _load_json(row.get("dress_code_dist"), {})
    latest = _load_json(row.get("latest_records"), [])

    system = """
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
""".strip()

    user = f"""
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
""".strip()

    out = ask_ai(user, system_prompt=system)
    # 左側はエラー文字列を出したくないならここで "" にしてもOK
    if out.startswith("[ERROR]"):
        return out
    return out.strip()


# ============================================================
# 学生AI：学生の面接ログ要約
# ============================================================
def generate_student_ai_summary(student_id: str, max_records: int = 8) -> str:
    df = load_report_df()
    sid = str(student_id).strip()

    if "学籍番号" not in df.columns:
        return ""
    if "開始日時" not in df.columns or "面接内容" not in df.columns:
        return ""

    df = df[df["学籍番号"].astype(str).str.strip() == sid]
    if df.empty:
        return ""

    df["開始日時"] = pd.to_datetime(df["開始日時"], errors="coerce")
    df = df.dropna(subset=["開始日時"]).sort_values("開始日時", ascending=False)

    texts = df["面接内容"].dropna().astype(str).tolist()[:max_records]
    joined = "\n\n".join(f"- {t}" for t in texts)[:6000]

    system = "あなたは就職活動を支援するキャリアアドバイザーです。出力は日本語のみ。推測で事実を足さない。"

    user = f"""
以下は学籍番号 {sid} の面接レポートです。

【面接ログ】
{joined}

次の観点で日本語で簡潔にまとめてください。
1. 全体傾向
2. 強み
3. 注意点・改善点
4. 次回面接への具体的アクション
""".strip()

    out = ask_ai(user, system_prompt=system)
    if out.startswith("[ERROR]"):
        return out
    return out.strip()


# ============================================================
# 企業サマリ（company_summary_t の1行を作る）
# ============================================================
def summarize_company(group: pd.DataFrame) -> dict | None:
    if group is None or group.empty:
        return None

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_result = "結果種別"
    col_format = "形式"
    col_text = "面接内容"
    col_report_id = "レポートID"

    if col_company not in group.columns:
        return None

    company_name = str(group[col_company].iloc[0]).strip()
    df = group.copy()

    # 面接だけ
    if col_event in df.columns:
        df = df[df[col_event].astype(str).str.strip() == "試験_面接"].copy()
    if df.empty:
        return None

    # 日付
    if col_start in df.columns:
        df["start_dt_obj"] = pd.to_datetime(df[col_start], errors="coerce")
        df = df.dropna(subset=["start_dt_obj"]).copy()
    else:
        df["start_dt_obj"] = pd.NaT
    if df.empty:
        return None

    # テキスト
    if col_text in df.columns:
        df["_text"] = df[col_text].fillna("").astype(str).map(clean_text)
    else:
        df["_text"] = ""

    atmos = Counter()
    form = Counter()
    dress = Counter()
    tag_counter = Counter()

    for t in df["_text"].tolist():
        if not t:
            continue
        atmos[detect_atmosphere_rule(t)] += 1
        dress[detect_dress_code(t)] += 1
        form[detect_format(t)] += 1
        for tg in detect_content_tags(t):
            tag_counter[tg] += 1

    # 形式列がある場合は上書き（列が信頼できるならこちらが正）
    if col_format in df.columns:
        form = Counter()
        for v in df[col_format].fillna("").astype(str).tolist():
            vv = v.strip()
            if not vv:
                continue
            if "オンライン" in vv or "WEB" in vv.upper():
                form["オンライン"] += 1
            elif "対面" in vv or "来社" in vv:
                form["対面"] += 1
            else:
                form["不明"] += 1

    top_tags = [k for k, _ in tag_counter.most_common(8)]

    # latest_records
    df_latest = df.sort_values("start_dt_obj", ascending=False).head(LATEST_RECORDS_LIMIT).copy()
    latest_records = []
    for _, r in df_latest.iterrows():
        raw_text = str(r.get(col_text, "") or "")
        t = clean_text(raw_text)
        rec = {
            "start_datetime": str(r.get(col_start, "") or ""),
            "result": str(r.get(col_result, "") or ""),
            "format": str(r.get(col_format, "") or ""),
            "memo": (t[:140] + "…") if len(t) > 140 else t,
            "questions": extract_questions(raw_text, max_q=3),
        }

        rid = str(r.get(col_report_id, "") or "").strip()
        if rid:
            rec["public_id"] = make_public_id(rid)

        latest_records.append(rec)

    row = {
        "company_name": company_name,
        "interview_count": int(len(df)),
        "content_top_tags": json.dumps(top_tags, ensure_ascii=False),
        "atmosphere_dist": json.dumps(dict(atmos), ensure_ascii=False),
        "format_dist": json.dumps(dict(form), ensure_ascii=False),
        "dress_code_dist": json.dumps(dict(dress), ensure_ascii=False),
        "latest_records": json.dumps(latest_records, ensure_ascii=False),
    }
    return row


# ============================================================
# 右側：最新10人分（学籍番号ごとの最新1件）を records として返す
#   右AI ONなら：回次ごとの質問TOP5 + メモを LLM 生成
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

    required = [col_company, col_event, col_result, col_start, col_format, col_text]
    if not set(required).issubset(df.columns):
        print("[WARN] build_interview_records_for_company: 必須カラム不足:", df.columns.tolist())
        return []

    target_name = str(company_name).strip()
    if not target_name:
        return []

    company_series = df[col_company].astype(str).str.strip()

    # 完全一致→ダメなら部分一致
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

    # 最新10人
    latest_dt_per_student = df_iv.groupby("_student_key")["start_dt_obj"].max().sort_values(ascending=False)
    latest_student_keys = latest_dt_per_student.head(DISPLAY_RECORD_LIMIT).index.tolist()
    df_top = df_iv[df_iv["_student_key"].isin(latest_student_keys)].copy()
    if df_top.empty:
        return []

    def _round_label(row):
        key = str(row.get("_student_key", "UNKNOWN"))
        total = int(total_rounds_map.get(key, int(row.get("round_index", 1))))
        idx = int(row.get("round_index", 1))
        return calc_round_label(idx, total)

    df_top["round_label"] = df_top.apply(_round_label, axis=1)

    ordered_labels = ["一次面接", "二次面接", "三次面接", "最終面接"]

    # 評価文除外など（AI後にも軽く通す）
    EVAL_PHRASES = [
        "評価", "懸念", "不足", "見られ", "必要", "できた", "できて", "できる",
        "感じた", "思った", "だった", "であった", "が高い", "が低い", "が強い",
        "が弱い", "不足して", "欠け", "ミスマッチ", "払拭", "内定", "合格", "不合格"
    ]
    QUESTION_CUES = [
        "何", "なぜ", "どう", "どの", "いつ", "どれ", "理由", "きっかけ", "具体的",
        "説明", "教えて", "伺", "ありますか", "できますか", "ですか"
    ]

    def _is_good_question(q: str) -> bool:
        if not isinstance(q, str):
            return False
        s = re.sub(r"\s+", " ", q).strip()
        if not s:
            return False
        if any(w in s for w in QUESTION_NG_WORDS):
            return False
        if len(s) < 8 or len(s) > 80:
            return False

        has_qmark = ("？" in s) or ("?" in s)
        has_cue = any(c in s for c in QUESTION_CUES)
        evalish = any(p in s for p in EVAL_PHRASES)
        if evalish and not (has_qmark or has_cue):
            return False

        if s.endswith("について教えてください。") or s.endswith("について教えてください") or s.endswith("について教えて下さい。"):
            core = re.sub(r"(について教えてください。?|について教えて下さい。?)$", "", s).strip()
            if re.search(r"(できた|できて|評価された|不足していた|懸念が残った|払拭した)$", core):
                return False

        return True

    records = []
    for label in ordered_labels:
        sub = df_top[df_top["round_label"] == label].copy()
        if sub.empty:
            continue

        types = []
        all_questions = []
        memos = []
        round_texts_for_ai = []

        for _, r in sub.iterrows():
            fmt_val = str(r.get(col_format, "") or "")
            types.append("オンライン" if ("オンライン" in fmt_val or "WEB" in fmt_val.upper()) else "対面")

            raw_text = str(r.get(col_text, "") or "")
            if raw_text.strip():
                round_texts_for_ai.append(raw_text)

            # フォールバック用：ルール抽出
            qs_raw = extract_questions(raw_text, max_q=12)
            qs = []
            for q in qs_raw:
                if any(w in q for w in QUESTION_NG_WORDS):
                    continue
                q2 = normalize_to_question(q)
                if _is_good_question(q2):
                    qs.append(q2)
            qs = qs[:5]
            all_questions.extend(qs)

            t = clean_text(raw_text)
            if t:
                memos.append(t[:120])

        type_label = Counter(types).most_common(1)[0][0] if types else ""

        top_questions = []
        memo_text = ""

        # 右AI（失敗したらフォールバック）
        if ENABLE_RIGHT_AI:
            qs_ai, memo_ai = build_right_ai_questions_and_memo(
                company_name=str(company_name).strip(),
                round_label=label,
                texts=round_texts_for_ai,
                top_k=5,
            )
            qs_ai = [normalize_to_question(q) for q in qs_ai]
            qs_ai = [q for q in qs_ai if _is_good_question(q)]
            if qs_ai:
                top_questions = qs_ai[:5]
            if isinstance(memo_ai, str) and memo_ai.strip():
                memo_text = memo_ai.strip()

        if not top_questions:
            q_counter = Counter([q.strip() for q in all_questions if q.strip()])
            top_questions = [q for q, _ in q_counter.most_common(5)]

        if not memo_text:
            memo_text = " / ".join(memos[:2]).strip()
            memo_text = memo_text[:180] + ("…" if len(memo_text) > 180 else "")

        records.append(
            {
                "id": label,
                "title": label,
                "year": "",
                "term": "",
                "status": f"{len(sub)}件",
                "type": type_label,
                "questions": top_questions,
                "memo": memo_text,
                "start_datetime": "",
            }
        )

    return records


# ============================================================
# 最新 N 件の生テキスト取得
# ============================================================
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
        df[col_company].astype(str).str.contains(company_name, na=False, regex=False)
        & (df[col_event].astype(str).str.strip() == "試験_面接")
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


# ============================================================
# main（CSV集計して company_summary_t.csv を作る）
# ============================================================
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


if __name__ == "__main__":
    main()
