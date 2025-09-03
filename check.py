import os
import json
import datetime, json, requests, smtplib
from email.mime.text import MIMEText

BASE_URL = "https://www.minamialps-yoyaku.jp"
# 北岳山荘の識別子は、master_no=212, service_type2_id=0（固定）
MASTER_NO = int(os.environ.get("MASTER_NO", "212"))
SERVICE_TYPE1_ID = int(os.environ.get("SERVICE_TYPE1_ID", "1"))
SERVICE_TYPE2_ID = int(os.environ.get("SERVICE_TYPE2_ID", "0"))
TARGET_DATE = datetime.date.fromisoformat(os.environ.get("TARGET_DATE", "2025-09-27"))

def fetch_event_data(session, start_date, end_date):
    # 初回アクセスでクッキー取得（必要ない可能性もありますが安全のため）
    session.get(f"{BASE_URL}/MountainHutInfolists?mountaionGroupId=1")
    params = {
        "masterNo": MASTER_NO,
        "serviceType1Id": SERVICE_TYPE1_ID,
        "serviceType2Id": SERVICE_TYPE2_ID,
        "startDate": start_date,
        "endDate": end_date,
    }
    resp = session.get(f"{BASE_URL}/MountainHutInfolists/GetEventData", params=params)
    resp.raise_for_status()
    raw_json = resp.text.strip()
    try:
        data = json.loads(raw_json)
        # APIによっては JSON がさらに文字列として返されることがあるので解釈を繰り返す
        while isinstance(data, str):
            data = json.loads(data)
        return data  # ここでようやくリストや辞書になっているはずです
    except Exception as e:
        raise RuntimeError(f"JSONの解析に失敗しました: {e}")

import datetime

def check_availability(data, target_date):
    for row in data:
        raw_date = row.get("serviceDate")
        if not raw_date:
            continue
        # 「2025/09/28T00:00:00」のようなパターンに対応するため、Tで分割し、/→-に統一
        date_str = raw_date.split("T")[0].replace("/", "-")
        try:
            service_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            # 念のため datetime.fromisoformat を使うと時間付きでも処理できる
            service_date = datetime.datetime.fromisoformat(date_str).date()
        if service_date == target_date:
            return "空きあり" if row.get("reservationCount", 0) > 0 else "満室"
    return "データなし"

def send_notification(status):
    FROM_EMAIL = os.environ["FROM_EMAIL"]
    TO_EMAIL = os.environ["TO_EMAIL"]
    APP_PASSWORD = os.environ["APP_PASSWORD"]
    subject = f"北岳山荘 {TARGET_DATE:%-m/%-d} 空きあり！"
    body = f"北岳山荘 {TARGET_DATE:%Y/%m/%d} の予約状況: {status}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(FROM_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

def main():
    session = requests.Session()
    start = TARGET_DATE.strftime("%Y-%m-%d")
    end   = TARGET_DATE.strftime("%Y-%m-%d")
    try:
        data = fetch_event_data(session, start, end)
        status = check_availability(data, TARGET_DATE)
    except Exception as e:
        # 取得失敗時は満室扱い（通知しない）
        print(f"取得エラー: {e}")
        return
    if status == "空きあり":
        send_notification(status)
        print(f"通知送信: {status}")
    else:
        print(f"通知なし: {status}")

if __name__ == "__main__":
    main()
