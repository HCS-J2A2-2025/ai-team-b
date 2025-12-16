# users_dummy.py
"""
このファイルの役割
------------------
・通知対象となるユーザのダミーデータを管理する
・event（申請データ）に含まれる user_id から
  「どのユーザに通知を送るか」を特定するために使う

※ 本番では users テーブル（DB）に置き換える想定
"""

# 通知対象ユーザのダミーデータ
DUMMY_USERS = [
    {
        "user_id": "20233051",              # events.user_id と紐づくID
        "name": "加藤 輝琉",                # 通知文に表示する名前

        # Google Chat の個人専用スペースに紐づく Incoming Webhook URL
        # ※ URL自体が権限なのでフロントには絶対に出さない
        "chat_webhook_url": "https://chat.googleapis.com/v1/spaces/AAQAUcqo9_o/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=dGWhQTmPbEnfYv6U8vbEMG9yLcgjrQ3AhZ0psBInh-c",
    }
]

def get_user_by_id(user_id: str):
    """
    user_id をもとに通知対象ユーザを取得する関数

    notify_job.py から呼ばれ、
    「この申請は誰のものか？」を解決するために使われる
    """
    for user in DUMMY_USERS:
        if user["user_id"] == user_id:
            return user
    return None
