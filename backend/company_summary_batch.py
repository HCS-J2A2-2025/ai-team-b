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
INPUT_CSV = os.path.join(BASE_DIR, "data", "data-1768790126893.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "company_summary_t.csv")

LATEST_RECORDS_LIMIT = 5
DISPLAY_RECORD_LIMIT = 10  # 右側に出す最大件数（= 最新10人分）

EVENT_KIND_INTERVIEW = "EXAM_INTERVIEW"
EVENT_KIND_APTITUDE = "EXAM_APTITUDE"
FINAL_RESULT_KINDS = {"RESCIND_OFFER", "OFFERED"}

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
_REPORT_DF_CACHE = None
_REPORT_DF_MTIME = None
_REPORT_NAMES_CACHE = None
_REPORT_NAMES_MTIME = None


def _get_report_mtime():
    return os.path.getmtime(INPUT_CSV)


def load_report_df():
    global _REPORT_DF_CACHE, _REPORT_DF_MTIME, _REPORT_NAMES_CACHE, _REPORT_NAMES_MTIME
    mtime = _get_report_mtime()
    if _REPORT_DF_CACHE is not None and _REPORT_DF_MTIME == mtime:
        return _REPORT_DF_CACHE

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

    if rename_map:
        df = df.rename(columns=rename_map)

    if "user_no" in df.columns and "学籍番号" not in df.columns:
        df["学籍番号"] = df["user_no"]

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

    _REPORT_DF_CACHE = df
    _REPORT_DF_MTIME = mtime
    _REPORT_NAMES_CACHE = None
    _REPORT_NAMES_MTIME = None
    return df


def get_company_names_cached() -> list[str]:
    global _REPORT_NAMES_CACHE, _REPORT_NAMES_MTIME
    try:
        mtime = _get_report_mtime()
    except OSError:
        return []

    if _REPORT_NAMES_CACHE is not None and _REPORT_NAMES_MTIME == mtime:
        return _REPORT_NAMES_CACHE

    df = load_report_df()
    col_event = "イベント種別"
    if col_event in df.columns:
        df = _filter_interview_only(df, col_event)
    col_candidates = ["企業名", "company_name"]
    target_col = next((c for c in col_candidates if c in df.columns), None)
    if not target_col:
        _REPORT_NAMES_CACHE = []
        _REPORT_NAMES_MTIME = mtime
        return []

    names = (
        df[target_col]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    _REPORT_NAMES_CACHE = names
    _REPORT_NAMES_MTIME = mtime
    return names



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
    s = df[col_event].astype(str).str.strip().str.upper()

    if s.isin({EVENT_KIND_INTERVIEW, EVENT_KIND_APTITUDE}).any():
        return df[s == EVENT_KIND_INTERVIEW].copy()

    df_iv = df[s.str.contains("面接", na=False, regex=False)].copy()
    if not df_iv.empty:
        return df_iv

    df_iv = df[s.str.contains("INTERVIEW", na=False, case=False, regex=False)].copy()
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

def _has_online_strong_word(text: str) -> bool:
    if not isinstance(text, str):
        return False
    s = text.upper()

    # 強いオンライン根拠（URL/会議ツール/明示語）
    online_words = [
        "オンライン",
        "WEB",
        "ZOOM",
        "TEAMS",
        "GOOGLE MEET",
        "GOOGLEMEET",
        "MEET",
        "SKYPE",
        "URL",
        "HTTPS://",
        "HTTP://",
        "リンク",
        "招待",
        "ミーティング",
        "会議URL",
        "面接URL",
        "WEB面接",
        "リモート",
    ]
    return any(w in s for w in online_words)


def _has_offline_strong_word(text: str) -> bool:
    if not isinstance(text, str):
        return False
    s = text.upper()

    # 強い対面根拠（場所/来社/集合/会場）
    offline_words = [
        "対面",
        "来社",
        "本社",
        "支社",
        "支店",
        "会場",
        "会議室",
        "受付",
        "入館",
        "集合",
        "現地",
        "持参",
        "筆記用具持参",
        "交通費",
        "住所",
    ]
    return any(w in s for w in offline_words)


# address_kind の「確定カテゴリ」
ONLINE_KIND_SET = {
    "自宅",
    "オンライン",
    "WEB",
    "リモート",
}
OFFLINE_KIND_SET = {
    "企業",
    "本社",
    "支社",
    "支店",
    "会場",
    "現地",
    "対面",
}


def _resolve_format_label(row: pd.Series, col_address_kind: str, col_address: str, col_format: str) -> str:
    address_kind = str(row.get(col_address_kind, "") or "").strip()
    address = str(row.get(col_address, "") or "").strip()
    fmt = str(row.get(col_format, "") or "").strip()

    merged = f"{address_kind} {address} {fmt}"

    # -------------------------
    # A: 確定（最優先）
    # -------------------------
    if address_kind in ONLINE_KIND_SET:
        return "オンライン"
    if address_kind in OFFLINE_KIND_SET:
        return "対面"

    # 形式/住所/種別に強い根拠があれば確定
    if _has_online_strong_word(merged):
        return "オンライン"
    if _has_offline_strong_word(merged):
        return "対面"

    # -------------------------
    # B: 準確定（学校）
    # ※現状の方針を維持：強いオンライン語がなければ対面
    # -------------------------
    if address_kind == "学校":
        return "オンライン" if _has_online_strong_word(merged) else "対面"

    # -------------------------
    # C: 最後の強制決着（ここでは“未確定”を返さず対面）
    # ※会社代表の最終決着は「最新レコード」でやる（後述）
    # -------------------------
    return "対面"


def _round_label_from_index(idx: int) -> str:
    labels = {
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
    return labels.get(int(idx), f"{int(idx)}次面接")





def _aggregate_format_labels(labels: list[str], latest_label: str | None = None) -> str:
    online = sum(1 for x in labels if x == "オンライン")
    offline = sum(1 for x in labels if x == "対面")

    if online > 0 and offline == 0:
        return "オンライン"
    if offline > 0 and online == 0:
        return "対面"
    if online == 0 and offline == 0:
        # ここまで来たら最新（なければ対面）
        return latest_label or "対面"

    # ★拮抗は「最新」で決める（C-1）
    if abs(online - offline) <= 1:
        return latest_label or "対面"

    return "オンライン" if online > offline else "対面"



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

import os
import requests

def ask_ai(user_prompt: str, system_prompt: str | None = None) -> str:
    # 優先順：OLLAMA_BASE_URL > OLLAMA_HOST >（Docker内）ollama0 >（ローカル）localhost
    base = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "").strip()

    if not base:
        # Dockerで動いているなら service 名、そうでないなら localhost を使う
        base = "http://ollama0:11434" if os.getenv("DOCKER") == "1" else "http://localhost:11434"

    if not base.startswith(("http://", "https://")):
        base = "http://" + base

    url = base.rstrip("/") + "/api/generate"

    model = (os.getenv("OLLAMA_MODEL") or "qwen2.5:14b-instruct").strip() or "qwen2.5:14b-instruct"

    payload = {
        "model": model,
        "prompt": (user_prompt or "").strip(),
        "stream": False,
        "options": {"temperature": 0.4},
    }
    if system_prompt and system_prompt.strip():
        payload["system"] = system_prompt.strip()

    try:
        r = requests.post(url, json=payload, timeout=600)
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
    df = load_report_df().copy()
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
    col_address = "address"
    col_address_kind = "address_kind"

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
    atmos = Counter()
    dress = Counter()
    tag_counter = Counter()

    for t in df["_text"].tolist():
        if not t:
            continue
        atmos[detect_atmosphere_rule(t)] += 1
        dress[detect_dress_code(t)] += 1
        for tg in detect_content_tags(t):
            tag_counter[tg] += 1

    form = Counter()
    for _, row in df.iterrows():
        label = _resolve_format_label(row, col_address_kind, col_address, col_format)
        if label:
            form[label] += 1

    top_tags = [k for k, _ in tag_counter.most_common(8)]

    # 最終面接フラグ（最重要）
    if col_result in df.columns:
        df["__result_kind"] = df[col_result].astype(str).str.strip().str.upper()
        df["__is_final"] = df["__result_kind"].isin(FINAL_RESULT_KINDS)
    else:
        df["__is_final"] = False
    
    # latest_records
    df_latest = df.sort_values("start_dt_obj", ascending=False).head(LATEST_RECORDS_LIMIT).copy()

    latest_records = []
    for _, r in df_latest.iterrows():
        raw_text = str(r.get(col_text, "") or "")
        t = clean_text(raw_text)
        rec = {
            "start_datetime": str(r.get(col_start, "") or ""),
            "result": str(r.get(col_result, "") or ""),
            "is_final": bool(r.get("__is_final", False)),
            "format": _resolve_format_label(r, col_address_kind, col_address, col_format),
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
# 右側：最新10人分（user_no ごとの最新1件）を records として返す
#   右AI ONなら：回次ごとの質問TOP5 + メモを LLM 生成
# ============================================================
def build_interview_records_for_company(company_name: str, student_no: str | None = None):
    df = load_report_df()

    col_company = "企業名"
    col_event = "イベント種別"
    col_start = "開始日時"
    col_format = "形式"
    col_result = "結果種別"
    col_text = "面接内容"
    col_address = "address"
    col_address_kind = "address_kind"
    col_user = "user_no" if "user_no" in df.columns else "学籍番号"

    required = [col_company, col_event, col_start, col_format, col_text]
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
    if student_no is not None and col_user in df_company.columns:
        df_company = df_company[df_company[col_user].astype(str).str.strip() == str(student_no).strip()].copy()
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

    # user_no キー（無い/空は UNKNOWN）
    if col_user in df_iv.columns:
        df_iv["_user_key"] = df_iv[col_user].astype(str).fillna("").str.strip()
        df_iv.loc[df_iv["_user_key"] == "", "_user_key"] = "UNKNOWN"
    else:
        df_iv["_user_key"] = "UNKNOWN"

    # =========================================================
    # ★コホートを作る：最新10人（＝右側の「10人」）
    # =========================================================
    if student_no is None:
        latest_dt_per_student = (
            df_iv.groupby("_user_key")["start_dt_obj"]
            .max()
            .sort_values(ascending=False)
        )
        cohort_keys = latest_dt_per_student.head(DISPLAY_RECORD_LIMIT).index.tolist()
        df_iv = df_iv[df_iv["_user_key"].isin(cohort_keys)].copy()

    if df_iv.empty:
        return []

    # =========================================================
    # 回次：user_no × start_date_time の昇順でロジック確定
    # =========================================================
    df_iv = df_iv.sort_values(["_user_key", "start_dt_obj"])
    df_iv["_order_index"] = df_iv.groupby("_user_key").cumcount() + 1
    df_iv["round_index"] = df_iv["_order_index"].astype(int)

    # 結果種別を正規化（内定/辞退などの集計に使う）
    if col_result in df_iv.columns:
        df_iv["__result_kind"] = df_iv[col_result].astype(str).str.strip().str.upper()
    else:
        df_iv["__result_kind"] = ""


    # 回次ラベル：常に回次通り（一次/二次/三次…）
    def _label_for_round(idx: int) -> str:
        return _round_label_from_index(int(idx))

    df_iv["round_label"] = df_iv["round_index"].apply(_label_for_round)

    # =========================================================
    # 回次ごとの「人数カウント（件数）」を user_no 単位で作る
    # =========================================================
    round_indices = (
        df_iv["round_index"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )

    records = []
    for round_idx in round_indices:
        label = _label_for_round(round_idx)
        sub = df_iv[df_iv["round_index"] == round_idx].copy()

        # 件数＝その回に到達して実際に受けた人数
        count_people = int(sub["_user_key"].nunique())

        # その回で「内定/辞退（OFFERED / RESCIND_OFFER）」になった人数（user単位）
        offer_like_people = 0
        if "__result_kind" in sub.columns:
            offer_like_people = int(
                sub.loc[sub["__result_kind"].isin(FINAL_RESULT_KINDS), "_user_key"].nunique()
            )

        status_text = f"{count_people}件"
        if offer_like_people > 0:
            status_text += f"（内定等{offer_like_people}件）"


        # ★ 0件の回次は表示しない
        if count_people == 0:
            continue

        # オンライン/対面（厳密ルール）
        types = [
            _resolve_format_label(row, col_address_kind, col_address, col_format)
            for _, row in sub.iterrows()
        ]

        # ★最新1件のラベル（C-1）
        latest_row = sub.sort_values("start_dt_obj", ascending=False).iloc[0] if "start_dt_obj" in sub.columns and len(sub) > 0 else None
        latest_label = _resolve_format_label(latest_row, col_address_kind, col_address, col_format) if latest_row is not None else None

        type_label = _aggregate_format_labels(types, latest_label=latest_label) or ""


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
                "status": status_text,
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
    ].copy()

    df = _filter_interview_only(df, col_event)

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
