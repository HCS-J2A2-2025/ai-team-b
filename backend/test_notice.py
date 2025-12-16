import requests

WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAQAUcqo9_o/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=dGWhQTmPbEnfYv6U8vbEMG9yLcgjrQ3AhZ0psBInh-c"

message = """【テスト通知】

これはダミー通知です。
"""

requests.post(
    WEBHOOK_URL,
    json={"text": message},
    timeout=10
)

print("通知を送信しました")
