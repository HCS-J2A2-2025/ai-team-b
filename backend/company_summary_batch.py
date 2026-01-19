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
ENABLE_ROUND_AI = True

# ====== 設定 ======
BASE_DIR = os.path.dirname(__file__)
INPUT_CSV = os.path.join(BASE_DIR, "data", "data-1768790126893.csv")
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

    if "結果種別" not in col_set:
        if "result_status" in col_set:
            rename_map["result_status"] = "結果種別"
        elif "result_kind" in col_set:
            rename_map["result_kind"] = "結果種別"

    if "開始日時" not in col_set:
        if "start_datetime" in col_set:
            rename_map["start_datetime"] = "開始日時"
        elif "start_date_time" in col_set:
            rename_map["start_date_time"] = "開始日時"

    if "終了日時" not in col_set:
        if "end_datetime" in col_set:
            rename_map["end_datetime"] = "終了日時"
        elif "end_date_time" in col_set:
            rename_map["end_date_time"] = "終了日時"

    # 「形式」相当の候補も吸収（あなたのCSVだと report_held_style っぽい）
    if "形式" not in col_set:
        if "format" in col_set:
            rename_map["format"] = "形式"
        elif "exam_format" in col_set:
            rename_map["exam_format"] = "形式"
        elif "report_held_style" in col_set:
            rename_map["report_held_style"] = "形式"

    # 面接内容（あなたのCSVだと report_content）
    if "面接内容" not in col_set:
        if "report_text" in col_set:
            rename_map["report_text"] = "面接内容"
        elif "report_content" in col_set:
            rename_map["report_content"] = "面接内容"

    if "学籍番号" not in col_set:
        if "student_no" in col_set:
            rename_map["student_no"] = "学籍番号"
        elif "user_no" in col_set:
            rename_map["user_no"] = "学籍番号"

    if rename_map:
        df = df.rename(columns=rename_map)

    # =========================================================
    # 3) ★正規化（report_id が複数行に分割されている前提に対応）
    #    - 同一「レポートID」を 1行に集約
    #    - 面接内容は連結して本文化
    # =========================================================
    if "レポートID" in df.columns:
        df["_rid"] = df["レポートID"].astype(str).fillna("").str.strip()
        # rid が空の行は「集約不能」なので、行ごとに一意IDを振って崩れないようにする
        empty = df["_rid"] == ""
        if empty.any():
            df.loc[empty, "_rid"] = "NO_ID_" + df.index.astype(str)

        # 代表値（空でないものを優先して取る）
        def first_non_empty(s: pd.Series) -> str:
            for v in s.tolist():
                if v is None:
                    continue
                vv = str(v).strip()
                if vv and vv.lower() not in {"nan", "none"}:
                    return vv
            return ""

        # 面接内容は複数行を連結（重複や空は除外）
        def join_texts(s: pd.Series) -> str:
            parts = []
            seen = set()
            for v in s.tolist():
                if v is None:
                    continue
                t = str(v).strip()
                if not t or t.lower() in {"nan", "none"}:
                    continue
                t = re.sub(r"\s+", " ", t).strip()
                if t and t not in seen:
                    parts.append(t)
                    seen.add(t)
            # 行分割されている前提なので、改行でつなぐ（UIで読みやすい）
            return "\n".join(parts)

        # 日付は min/max（解釈できないものは NaT）
        has_start = "開始日時" in df.columns
        has_end = "終了日時" in df.columns
        if has_start:
            df["_start_dt"] = pd.to_datetime(df["開始日時"], errors="coerce")
        else:
            df["_start_dt"] = pd.NaT
        if has_end:
            df["_end_dt"] = pd.to_datetime(df["終了日時"], errors="coerce")
        else:
            df["_end_dt"] = pd.NaT

        agg_map = {}

        # 既存列は基本「代表値」を取る
        for c in df.columns:
            if c in {"_rid", "_start_dt", "_end_dt"}:
                continue
            if c == "面接内容":
                agg_map[c] = join_texts
            else:
                agg_map[c] = first_non_empty

        grouped = df.groupby("_rid", sort=False).agg(agg_map).reset_index(drop=True)

        # 開始/終了は groupby で別集計して付与
        dt = df.groupby("_rid", sort=False).agg(
            _start_min=(" _start_dt".replace(" ", ""), "min") if False else ("_start_dt", "min"),
            _end_max=(" _end_dt".replace(" ", ""), "max") if False else ("_end_dt", "max"),
        )

        # ↑pandas の列名を安全に扱うために素直に書き直し
        dt = df.groupby("_rid", sort=False).agg(
            _start_min=("_start_dt", "min"),
            _end_max=("_end_dt", "max"),
        )

        dt = dt.reset_index()

        # grouped は _rid がないので、いったん _rid を付けて merge
        grouped["_rid"] = dt["_rid"].values
        grouped = grouped.merge(dt[["_rid", "_start_min", "_end_max"]], on="_rid", how="left")
        grouped = grouped.drop(columns=["_rid"])

        # 開始/終了を戻す（ISO文字列にすると downstream が安定）
        if "開始日時" in grouped.columns:
            grouped["開始日時"] = grouped["_start_min"].dt.strftime("%Y-%m-%d %H:%M:%S")
        if "終了日時" in grouped.columns:
            grouped["終了日時"] = grouped["_end_max"].dt.strftime("%Y-%m-%d %H:%M:%S")

        grouped = grouped.drop(columns=[c for c in ["_start_min", "_end_max"] if c in grouped.columns])

        df = grouped

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


def _filter_interview_only(df: pd.DataFrame, col_event: str) -> pd.DataFrame:
    if col_event not in df.columns:
        return df
    s = df[col_event].astype(str).str.strip()

    df_iv = df[s == "試験_面接"].copy()
    if not df_iv.empty:
        return df_iv

    df_iv = df[s.str.contains("面接", na=False, regex=False)].copy()
    if not df_iv.empty:
        return df_iv

    df_iv = df[s.str.contains("interview", na=False, case=False, regex=False)].copy()
    if not df_iv.empty:
        return df_iv

    return df


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


def normalize_format_value(value: str) -> str:
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    s = value.strip()
    if not s:
        return ""

    upper = s.upper()
    if "オンライン" in s or "WEB" in upper or "ONLINE" in upper:
        return "オンライン"
    if "対面" in s or "来社" in s or "OFFLINE" in upper:
        return "対面"
    if s in {"その他", "OTHER", "不明", "UNKNOWN"}:
        return ""
    return ""


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
# 回次抽出（テキスト内の "1次/一次/最終" 等）
# ============================================================
def _kanji_to_int(s: str) -> int | None:
    table = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }
    return table.get(s)


def detect_round_index_from_text(text: str) -> int | None:
    if not isinstance(text, str):
        return None
    t = text

    m = re.search(r"(?:第\s*)?(\d+)\s*(?:次|回目|回|次面接)", t)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    m = re.search(r"(?:第\s*)?([一二三四五六七八九十])\s*(?:次|回目|回|次面接)", t)
    if m:
        return _kanji_to_int(m.group(1))

    for k in ["一次", "二次", "三次", "四次", "五次", "六次", "七次", "八次", "九次", "十次"]:
        if k in t:
            return _kanji_to_int(k[:1])

    return None


def detect_is_final_from_text(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return "最終" in text


def is_info_session_text(text: str) -> bool:
    if not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    return any(
        kw in t
        for kw in [
            "説明会",
            "会社説明会",
            "オリエンテーション",
            "セミナー",
            "ガイダンス",
            "座談会",
        ]
    )


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
    # 安全に int 化
    try:
        round_index = int(round_index)
    except Exception:
        round_index = 1

    try:
        total_rounds = int(total_rounds)
    except Exception:
        total_rounds = round_index if round_index > 0 else 1

    # 下限補正
    if round_index <= 0:
        round_index = 1
    if total_rounds <= 0:
        total_rounds = 1

    # 上限補正（round_index が total を超えないように）
    if round_index > total_rounds:
        round_index = total_rounds

    # ★追加：1回しかログがない学生は一次面接扱い（最終面接にしない）
    if total_rounds == 1:
        return "一次面接"

    # 4回以上は 1,2,3,最終 の固定割当
    if total_rounds >= 4:
        if round_index == 1:
            return "一次面接"
        if round_index == 2:
            return "二次面接"
        if round_index == 3:
            return "三次面接"
        return "最終面接"

    # 2回 or 3回のときは「最後＝最終」
    if round_index == total_rounds:
        return "最終面接"

    # それ以外は順番どおり
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


def _extract_json_value(text: str):
    if not isinstance(text, str):
        return None
    s = text.strip()

    try:
        return json.loads(s)
    except Exception:
        pass

    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", s, flags=re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        try:
            return json.loads(inner)
        except Exception:
            pass

    l = s.find("[")
    r = s.rfind("]")
    if l != -1 and r != -1 and r > l:
        inner = s[l:r+1]
        try:
            return json.loads(inner)
        except Exception:
            pass

    l = s.find("{")
    r = s.rfind("}")
    if l != -1 and r != -1 and r > l:
        inner = s[l:r+1]
        try:
            return json.loads(inner)
        except Exception:
            pass

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
# 回次推定（LLM）
# ============================================================
def infer_rounds_with_ai(records: list[dict]) -> dict[int, dict]:
    if not records:
        return {}

    system = """
あなたは就職活動の受験記録を正規化するアシスタントです。
以下のルールに従って、面接区分を必ず「一次面接」または「最終面接」のどちらかに分類してください。

【判別ルール（最優先）】
1. 「最終」「Final」「最終選考」「役員面接」「社長面接」「内定直前」「意思確認」
   → 必ず「最終面接」とする

2. 「一次」「1次」「1st」「書類通過後」「最初の面接」「人事面接」
   → 必ず「一次面接」とする

【補助ルール】
3. 面接回数が明示されていない場合：
   - 面接が1回のみと記載されている → 「最終面接」
   - 面接が複数回ある前提の記載 → 最初のものは「一次面接」

※二次・三次など複数回の面接が存在する可能性がある

4. オンライン／対面の別は面接区分の判断には一切影響しない

5. 判断に迷う場合でも「不明」「その他」は使用せず、
   文脈から最も妥当な方（一次 or 最終）を必ず選択する

【出力制約】
- 出力はJSON配列のみ
- 各要素は { "idx": number, "label": "一次面接" | "最終面接" }
- 理由や説明文は一切出力しない
"""

    lines = []
    for r in records:
        idx = r.get("idx")
        dt = str(r.get("start_datetime", "") or "")
        text = clean_text(str(r.get("text", "") or ""))[:600]
        lines.append(f"[{idx}] {dt}\n{text}")

    user = "以下の面接ログから回次を推定してください。\n\n" + "\n\n".join(lines)
    out = ask_ai(user, system_prompt=system)
    if isinstance(out, str) and out.startswith("[ERROR]"):
        return {}

    payload = _extract_json_value(out)
    items = None
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    if not items:
        return {}

    result = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = it.get("idx")
        try:
            idx = int(idx)
        except Exception:
            continue
        label = str(it.get("label", "") or "").strip()
        if label not in {"一次面接", "最終面接"}:
            continue
        if label == "一次面接":
            result[idx] = {"round_index": 1, "is_final": False}
        else:
            result[idx] = {"round_index": None, "is_final": True}

    return result


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
- 文体は必ず丁寧語（です・ます調）
- 出力フォーマットを絶対に守る

【今回の最重要方針（必ず守る）】
- 「情報が不明」「分からない」「不足している」「判断できない」「不明な部分が多い」等の“分からない宣言”を一切書かない
- 会社固有の断定は、データに根拠がある範囲だけに限定する
- データが少ない場合は、会社固有の話を無理に広げず、
  「参考としての一般的な対策」を短く添える（断定せず、目安・推奨・心構えとして書く）
  例：×「不明です」→ ○「参考：〜を準備しておくと安心です」
- “不明”“不足”“推測できない”という単語自体を出力に含めない

【出力フォーマット】
以下の４つのブロックをこの順番・この見出しで出力してください。

■ 雰囲気
- 1〜3文でまとめる
- データに根拠がある場合：分布の多い傾向を自然文にする（例：落ち着いた/丁寧/圧迫気味 など）
- 根拠が薄い場合：会社固有の断定は避けつつ、参考として「面接で意識すると良い姿勢」を1文だけ添える

■ よく聞かれる質問
- 箇条書き（「・」または「-」）で3〜6個
- タグがある場合：タグを日本語の“質問テーマ名”に整形して列挙（英語は禁止）
- タグが少ない場合：会社固有にせず、一般的に頻出のテーマを列挙（志望動機/強み弱み/学校で学んだこと/逆質問/チーム経験 など）

■ 服装
- 1〜2文
- 服装分布に根拠がある場合：多い傾向を述べる
- 根拠が薄い場合：参考として無難な基準（例：ビジネスフォーマル寄り、清潔感、派手すぎない）を1〜2文で提示

■ 面接形式
- 1〜2文
- 形式分布に根拠がある場合：オンライン/対面の多い方を中心に述べる
- 根拠が薄い場合：会社固有にせず「オンライン想定の準備と対面想定の準備を両方しておく」等、参考の準備方針を述べる

【禁止事項】
- 「情報が不明/不足/わからない/判断できない」などの文言
- 会社固有の断定を、根拠なしで書くこと
- 英語、英単語、英語の括弧書き

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
def summarize_company_with_error(group: pd.DataFrame) -> tuple[dict | None, str | None]:
    if group is None or group.empty:
        return None, "対象データが空です"

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_result = "結果種別"
    col_format = "形式"
    col_text = "面接内容"
    col_report_id = "レポートID"

    required = [col_company, col_start, col_text]
    missing = [c for c in required if c not in group.columns]
    if missing:
        return None, f"必須カラム不足: {missing}"

    company_name = str(group[col_company].iloc[0]).strip()
    if not company_name:
        return None, "企業名が空です"

    df = group.copy()

    # 面接だけ（可能なら絞る、該当なしなら全件）
    df = _filter_interview_only(df, col_event)
    if df.empty:
        return None, "面接ログがありません"

    # 日付
    if col_start in df.columns:
        df["start_dt_obj"] = pd.to_datetime(df[col_start], errors="coerce")
        df = df.dropna(subset=["start_dt_obj"]).copy()
    else:
        df["start_dt_obj"] = pd.NaT
    if df.empty:
        return None, "開始日時が不正で日付が解釈できません"

    # テキスト
    if col_text in df.columns:
        df["_text"] = df[col_text].fillna("").astype(str).map(clean_text)
    else:
        df["_text"] = ""
    df = df[~df["_text"].map(is_info_session_text)].copy()
    if df.empty:
        return None, "面接ログがありません"

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
        formats = df[col_format].fillna("").astype(str).tolist()
        texts = df["_text"].tolist()
        for v, t in zip(formats, texts):
            label = normalize_format_value(v)
            if not label:
                label = detect_format(t)
            if not label:
                label = "不明"
            form[label] += 1

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
    return row, None


def summarize_company(group: pd.DataFrame) -> dict | None:
    row, _ = summarize_company_with_error(group)
    return row


# ============================================================
# 右側：最新10人分（学籍番号ごとの最新1件）を records として返す
#   右AI ONなら：回次ごとの質問TOP5 + メモを LLM 生成
# ============================================================
def build_interview_records_for_company(company_name: str, student_no: str | None = None):
    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_result = "結果種別"      # 通過判定に使う
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

    # 企業一致（完全一致→部分一致）
    company_series = df[col_company].astype(str).str.strip()
    df_company = df[company_series == target_name].copy()
    if df_company.empty:
        df_company = df[company_series.str.contains(target_name, na=False, regex=False)].copy()
        if df_company.empty:
            return []

    # 個人モード（学生指定）※この場合はその学生だけの回次表示になる
    if student_no is not None and col_student in df_company.columns:
        df_company = df_company[df_company[col_student].astype(str).str.strip() == str(student_no).strip()].copy()
        if df_company.empty:
            return []

    # 面接のみ（可能なら絞る、該当なしなら全件）
    df_iv = _filter_interview_only(df_company, col_event)
    if df_iv.empty:
        return []

    # 日付
    df_iv["start_dt_obj"] = pd.to_datetime(df_iv[col_start], errors="coerce")
    df_iv = df_iv.dropna(subset=["start_dt_obj"]).copy()
    if df_iv.empty:
        return []

    # 説明会などは除外（本文判定）
    df_iv = df_iv[~df_iv[col_text].fillna("").astype(str).map(is_info_session_text)].copy()
    if df_iv.empty:
        return []

    # 学籍番号キー（無い/空は UNKNOWN）
    if col_student in df_iv.columns:
        df_iv["_student_key"] = df_iv[col_student].astype(str).fillna("").str.strip()
        df_iv.loc[df_iv["_student_key"] == "", "_student_key"] = "UNKNOWN"
    else:
        df_iv["_student_key"] = "UNKNOWN"

    # =========================================================
    # ★コホートを作る：最新10人（＝右側の「10人」）
    # =========================================================
    if student_no is None:
        latest_dt_per_student = (
            df_iv.groupby("_student_key")["start_dt_obj"]
            .max()
            .sort_values(ascending=False)
        )
        cohort_keys = latest_dt_per_student.head(DISPLAY_RECORD_LIMIT).index.tolist()
        df_iv = df_iv[df_iv["_student_key"].isin(cohort_keys)].copy()

    if df_iv.empty:
        return []

    # =========================================================
    # 回次：内容優先で判定（無ければ日時順）
    # =========================================================
    def _round_label_from_index(idx: int) -> str:
        m = {
            1: "一次面接",
            2: "二次面接",
            3: "三次面接",
            4: "四次面接",
            5: "五次面接",
            6: "六次面接",
            7: "七次面接",
            8: "八次面接",
            9: "九次面接",
            10: "十次面接",
        }
        return m.get(int(idx), f"{idx}次面接")

    df_iv = df_iv.sort_values(["_student_key", "start_dt_obj"])
    df_iv["_order_index"] = df_iv.groupby("_student_key").cumcount() + 1
    df_iv["_total_order_rounds"] = df_iv.groupby("_student_key")["_order_index"].transform("max")

    texts = df_iv[col_text].fillna("").astype(str)
    df_iv["_round_hint"] = texts.map(detect_round_index_from_text)
    df_iv["_is_final_hint"] = texts.map(detect_is_final_from_text)

    if ENABLE_ROUND_AI:
        df_iv["_round_hint_ai"] = pd.NA
        df_iv["_is_final_hint_ai"] = False

        for sid, g in df_iv.groupby("_student_key", sort=False):
            if g.empty:
                continue
            recs = []
            for i, (_, row) in enumerate(g.iterrows()):
                recs.append(
                    {
                        "idx": i,
                        "start_datetime": str(row.get(col_start, "") or ""),
                        "text": str(row.get(col_text, "") or ""),
                    }
                )
            ai_map = infer_rounds_with_ai(recs)
            if not ai_map:
                continue
            for i, (idx, _) in enumerate(g.iterrows()):
                info = ai_map.get(i)
                if not info:
                    continue
                if info.get("round_index") is not None:
                    df_iv.loc[idx, "_round_hint_ai"] = info["round_index"]
                if info.get("is_final") is True:
                    df_iv.loc[idx, "_is_final_hint_ai"] = True

        ai_hint = df_iv["_round_hint_ai"].notna()
        df_iv.loc[ai_hint, "_round_hint"] = df_iv.loc[ai_hint, "_round_hint_ai"].astype(int)
        df_iv["_is_final_hint"] = df_iv["_is_final_hint"] | df_iv["_is_final_hint_ai"]

    df_iv["_max_round_hint"] = (
        df_iv.groupby("_student_key")["_round_hint"]
        .transform("max")
        .fillna(0)
        .astype(int)
    )

    df_iv["round_index"] = df_iv["_order_index"].astype(int)
    hinted = df_iv["_round_hint"].notna()
    df_iv.loc[hinted, "round_index"] = df_iv.loc[hinted, "_round_hint"].astype(int)

    def _apply_final_round(row):
        if row.get("_is_final_hint"):
            return max(int(row.get("_total_order_rounds", 1)), int(row.get("_max_round_hint", 0)), int(row.get("round_index", 1)))
        return int(row.get("round_index", 1))

    df_iv["round_index"] = df_iv.apply(_apply_final_round, axis=1).astype(int)

    total_rounds_map = df_iv.groupby("_student_key")["round_index"].max().to_dict()

    def _round_label(row):
        if row.get("_is_final_hint"):
            return "最終面接"
        hint = row.get("_round_hint")
        if pd.notna(hint):
            try:
                return _round_label_from_index(int(hint))
            except Exception:
                pass
        idx = int(row.get("round_index", 1))
        return _round_label_from_index(max(idx, 1))

    df_iv["round_label"] = df_iv.apply(_round_label, axis=1)

    # ★最後の回（真の最終）を明示（これが「最終10件」を止める）
    df_iv["total_rounds"] = (
        df_iv["_student_key"].map(total_rounds_map)
        .fillna(df_iv["round_index"])
        .astype(int)
    )
    df_iv["_is_final"] = (df_iv["round_index"] == df_iv["total_rounds"])

    # =========================================================
    # ★通過判定（ここが画像のカウントの肝）
    # =========================================================
    PASS_WORDS = ["継続", "合格", "通過", "内々定", "次へ", "内定"]
    FAIL_WORDS = ["落選", "不合格", "見送り", "辞退", "不採用", "終了", "否"]
    PASS_WORDS_EN = [
        "CONTINUE",
        "OFFERED",
        "PASS",
        "PASSED",
        "SUCCESS",
        "SUCCEED",
        "NEXT",
        "ADVANCE",
        "PROCEED",
        "ACCEPT",
        "ACCEPTED",
    ]
    FAIL_WORDS_EN = [
        "UNSUCCESS",
        "FAIL",
        "FAILED",
        "DECLINE",
        "REJECT",
        "REJECTED",
        "NOT PASS",
        "NOT_PASS",
        "NOTPASSED",
        "NG",
    ]

    def is_pass(result_str: str) -> bool | None:
        s = str(result_str or "").strip()
        if not s:
            return None
        s_upper = s.upper()
        if any(w in s for w in FAIL_WORDS) or any(w in s_upper for w in FAIL_WORDS_EN):
            return False
        if any(w in s for w in PASS_WORDS) or any(w in s_upper for w in PASS_WORDS_EN):
            return True
        return None

    # =========================================================
    # ★「一次→二次→…」の通過ゲート
    # eligible=True の人だけ “その回次に到達した” として数える
    # =========================================================
    df_iv["_eligible"] = False
    for sid, g in df_iv.groupby("_student_key", sort=False):
        eligible = True
        for idx in g.index:
            if eligible:
                df_iv.loc[idx, "_eligible"] = True
            verdict = is_pass(df_iv.loc[idx, col_result])
            if verdict is False:
                eligible = False
            elif verdict is True:
                eligible = True

    # =========================================================
    # ★回次ごとの「人数カウント（件数）」を内容ベースで作る
    # =========================================================
    label_order = (
        df_iv.groupby("round_label")["round_index"]
        .min()
        .sort_values()
        .index.tolist()
    )
    if "最終面接" in label_order:
        label_order = [l for l in label_order if l != "最終面接"] + ["最終面接"]

    records = []
    for label in label_order:
        sub = df_iv[
            (df_iv["round_label"] == label)
            & (df_iv["_eligible"] == True)
        ].copy()

        # 件数＝その回に到達して実際に受けた人数
        count_people = int(sub["_student_key"].nunique())

        # ★ 0件の回次は表示しない
        if count_people == 0:
            continue

        # 形式（列優先で判定）
        types = []
        formats = sub[col_format].fillna("").astype(str).tolist()
        texts = sub[col_text].fillna("").astype(str).tolist()
        for v, t in zip(formats, texts):
            fmt_label = normalize_format_value(v)
            if not fmt_label:
                fmt_label = detect_format(t)
            if not fmt_label:
                fmt_label = "不明"
            types.append(fmt_label)
        type_label = Counter(types).most_common(1)[0][0] if types else ""

        # この回の面接テキスト
        round_texts_for_ai = sub[col_text].fillna("").astype(str).tolist()

        # フォールバック（ルール質問）
        all_questions = []
        memos = []
        for raw_text in round_texts_for_ai[:200]:
            qs_raw = extract_questions(raw_text, max_q=12)
            for q in qs_raw:
                if any(w in q for w in QUESTION_NG_WORDS):
                    continue
                all_questions.append(normalize_to_question(q))
            t = clean_text(raw_text)
            if t:
                memos.append(t[:120])

        top_questions = []
        memo_text = ""

        # 右AI
        if ENABLE_RIGHT_AI:
            qs_ai, memo_ai = build_right_ai_questions_and_memo(
                company_name=str(company_name).strip(),
                round_label=label,
                texts=round_texts_for_ai,
                top_k=5,
            )
            qs_ai = [normalize_to_question(q) for q in qs_ai]
            qs_ai = [q for q in qs_ai if q and not any(w in q for w in QUESTION_NG_WORDS)]
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
                "status": f"{count_people}件",
                "type": type_label,
                "questions": top_questions,
                "memo": memo_text,
                "start_datetime": "",
            }
        )

    return records

    # =========================================================
    # ★回次ごとの「人数カウント（件数）」を作る
    # =========================================================
    records = []
    for label in ordered_labels:
        sub = df_iv[(df_iv["round_label"] == label) & (df_iv["_eligible"] == True)].copy()

        # ★最終面接だけ「最後の回」限定（ここが決定打）
        if label == "最終面接":
            sub = sub[sub["_is_final"] == True].copy()

        if sub.empty:
            continue

        # 件数＝学生数（人の数）
        count_people = sub["_student_key"].nunique()

        # 形式（列優先で判定）
        types = []
        for v in sub[col_format].fillna("").astype(str).tolist():
            vv = v.strip()
            if "オンライン" in vv or "WEB" in vv.upper():
                types.append("オンライン")
            elif "対面" in vv or "来社" in vv:
                types.append("対面")
            else:
                types.append("不明")
        type_label = Counter(types).most_common(1)[0][0] if types else ""

        # この回次の面接テキスト（AI用）
        round_texts_for_ai = sub[col_text].fillna("").astype(str).tolist()

        # フォールバック（ルール質問）
        all_questions = []
        memos = []
        for raw_text in round_texts_for_ai[:200]:
            qs_raw = extract_questions(raw_text, max_q=12)
            for q in qs_raw:
                if any(w in q for w in QUESTION_NG_WORDS):
                    continue
                all_questions.append(normalize_to_question(q))
            t = clean_text(raw_text)
            if t:
                memos.append(t[:120])

        top_questions = []
        memo_text = ""

        # 右AI
        if ENABLE_RIGHT_AI:
            qs_ai, memo_ai = build_right_ai_questions_and_memo(
                company_name=str(company_name).strip(),
                round_label=label,
                texts=round_texts_for_ai,
                top_k=5,
            )
            qs_ai = [normalize_to_question(q) for q in qs_ai]
            qs_ai = [q for q in qs_ai if q and not any(w in q for w in QUESTION_NG_WORDS)]
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
                "status": f"{count_people}件",
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
