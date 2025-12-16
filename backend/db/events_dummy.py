# events_dummy.py
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

DUMMY_EVENTS = [
    {
        # ===== システム管理用 =====
        "event_id": 20230001,            # 申請ID
        "user_id": "20233051",           # 学籍番号（users と紐づけ）
        "status": "pending",             # pending / sent / cancelled

        # ===== 利用者情報 =====
        "user_name": "加藤 輝琉",
        "class_no": "S3A2310",

        # ===== イベント情報 =====
        "event_type": "interview",       # interview / exam / briefing
        "company_name": "株式会社さくら",

        # ===== 日時（ISO + JST）=====
        "start_datetime": datetime(
            2025, 12, 16, 10, 0, tzinfo=JST
        ),
        "end_datetime": datetime(
            2025, 12, 16, 11, 35, tzinfo=JST
        ),

        # ===== 通知用（重要）=====
        # 開始の24時間前
        "notify_at": datetime(
            2024, 3, 4, 10, 0, tzinfo=JST
        ),

        # ===== 補足情報（通知には使わない）=====
        "address": "東京都中央区銀座1-1-35 桜ビル5F",
        "address_kind": "道外",
        "attendance_note": "1.2時限目欠席",
    }
]

