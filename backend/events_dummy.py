# events_dummy.py
"""
このファイルの役割
------------------
・申請されたイベント（面接・試験など）のダミーデータを管理する
・通知の判定は start_datetime を基準に自動計算する
・notify_at は「開始日時 - 1日」で必ず算出する

※ 本番では events テーブル（DB）に置き換える想定
"""

from datetime import datetime, timedelta, timezone

# 日本時間（JST）
JST = timezone(timedelta(hours=9))

def create_event(
    event_id: int,
    user_id: str,
    company_name: str,
    start_datetime: datetime,
):
    """
    申請データを作る共通関数

    ・notify_at を自動計算
    ・status を初期値 pending にする
    """
    return {
        "event_id": event_id,
        "user_id": user_id,
        "company_name": company_name,
        "start_datetime": start_datetime,

        # ★ 開始日時の1日前を自動計算
        "notify_at": start_datetime - timedelta(days=1),

        "status": "pending",
    }

# ===== ダミーイベント =====

DUMMY_EVENTS = [
    create_event(
        event_id=20230001,
        user_id="20233051",
        company_name="株式会社さくら",
        start_datetime=datetime(
            2025, 12, 17, 11, 11, tzinfo=JST
        ),
    )
]
