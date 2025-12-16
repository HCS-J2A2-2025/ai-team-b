# notify_job.py
"""
このファイルの役割（最重要）
----------------------------
・cron / タスクスケジューラから定期実行される
・申請データ（events）を確認し、
  「通知時刻になったもの」だけを対象に通知を送る
・ログイン状態やフロント画面は一切関係ない

＝ 通知機能の心臓部
"""

from datetime import datetime, timedelta, timezone
from users_dummy import get_user_by_id
from events_dummy import DUMMY_EVENTS
from notify_service import send_chat_notification

# 日本時間
JST = timezone(timedelta(hours=9))

def main():
    # 現在時刻を取得
    now = datetime.now(JST)

    # すべての申請データをチェック
    for event in DUMMY_EVENTS:

        # ① すでに送信済みなら何もしない（再送防止）
        if event["status"] != "pending":
            continue

        # ② 通知時刻（1日前）になっていなければスキップ
        if event["notify_at"] > now:
            continue

        # ③ この申請を出したユーザを取得
        user = get_user_by_id(event["user_id"])
        if not user:
            continue

        # ④ 通知先（Webhook URL）がなければ送れない
        webhook_url = user["chat_webhook_url"]
        if not webhook_url:
            continue

        # ⑤ 通知メッセージを作成
        message = f"""【⏰ 面接リマインド】

{user["name"]} さん

明日 {event["start_datetime"].strftime('%m/%d %H:%M')} より
面接予定があります。

■ 企業名
{event["company_name"]}
"""

        # ⑥ Google Chat に通知送信
        send_chat_notification(webhook_url, message)

        # ⑦ 送信済みに更新（再送防止）
        event["status"] = "sent"

        print(f"[OK] notified event_id={event['event_id']}")

# cron から直接実行される入口
if __name__ == "__main__":
    main()
