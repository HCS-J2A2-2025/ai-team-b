# notify_service.py
"""
このファイルの役割
------------------
・Google Chat Incoming Webhook にメッセージを送信する
・通知の送信方法を1か所にまとめるためのファイル

※ 将来 LINE / メール通知に変えても、
  notify_job.py を書き換えずに済むように分離している
"""

import requests

def send_chat_notification(webhook_url: str, message: str):
    """
    Google Chat に通知を送る関数

    引数:
    - webhook_url : ユーザ専用スペースの Incoming Webhook URL
    - message     : Chat に表示するメッセージ本文
    """
    payload = {"text": message}

    # POST するだけで通知が送られる（認証不要）
    res = requests.post(webhook_url, json=payload, timeout=10)

    # HTTPエラーがあれば例外を出す
    res.raise_for_status()
