import os
import json
import datetime
import requests
import smtplib
from email.mime.text import MIMEText

# APIのベースURL
BASE_URL = "https://www.minamialps-yoyaku.jp"

def fetch_event_data(session: requests.Session,
                     master_no: int,
                     service_type1_id: int,
                     service_type2_id: int,
                     start_date: str,
                     end_date: str):
    """
    指定した山小屋の予約状況データを取得する。
    APIからはJSON文字列が返ってくる場合があるので繰り返しjson.loadsを行う。
    """
    # Cookie取得のためトップページにアクセス
    session.get(f"{BASE_URL}/MountainHutInfolists?mountaionGroupId=1")
    params = {
        "masterNo": master_no,
        "serviceType1Id": service_type1_id,
        "serviceType2Id": service_type2_id,
        "startDate": start_date,
        "endDate": end_date,
    }
    resp = session.get(f"{BASE_URL}/MountainHutInfolists/GetEventData", params=params)
    resp.raise_for_status()
    raw_json = resp.text.strip()
    # ネストしたJSONに対応する
    try:
        data = json.loads(raw_json)
        while isinstance(data, str):
            data = json.loads(data)
        return data
    except Exception as e:
        raise RuntimeError(f"JSONの解析に失敗しました: {e}")

def check_availability(events, target_date: datetime.date) -> str:
    """
    イベント一覧から指定日の空き状況を判定する。
    空きがあれば「空きあり」、なければ「満室」、データが存在しない場合は「データなし」を返す。
    """
    for item in events:
        raw_date = item.get("serviceDate")
        if not raw_date:
            continue
        # "2025/09/27T00:00:00" のような表記に対応
        date_str = raw_date.replace("/", "-").split("T")[0]
        try:
            service_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            try:
                service_date = datetime.datetime.fromisoformat(date_str).date()
            except Exception:
                continue
        if service_date == target_date:
            return "空きあり" if item.get("reservationCount", 0) > 0 else "満室"
    return "データなし"

def send_notification(status: str, target_date: datetime.date):
    """
    Gmailで空き状況を通知する。環境変数から認証情報を取得。
    """
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["TO_EMAIL"]
    app_password = os.environ["APP_PASSWORD"]
    subject = f"北岳山荘 {target_date:%-m/%-d} 空きあり！"
    body = f"北岳山荘 {target_date:%Y/%m/%d} の予約状況: {status}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)

def main():
    # 環境変数の取得
    master_no = int(os.environ.get("MASTER_NO", "212"))           # 北岳山荘
    service_type1_id = int(os.environ.get("SERVICE_TYPE1_ID", "1"))  # 1=山小屋泊, 2=テント泊
    service_type2_id = int(os.environ.get("SERVICE_TYPE2_ID", "0"))
    target_date_str = os.environ.get("TARGET_DATE", "2025-09-27")
    target_date = datetime.date.fromisoformat(target_date_str)

    # ターゲット日を含む月のデータを取得するよう範囲を計算
    first_day = target_date.replace(day=1)
    # 月末日の計算: 翌月1日から1日引く
    last_day = (target_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    start_date = first_day.strftime("%Y-%m-%d")
    end_date = last_day.strftime("%Y-%m-%d")

    session = requests.Session()
    try:
        events = fetch_event_data(session, master_no, service_type1_id, service_type2_id, start_date, end_date)
        status = check_availability(events, target_date)
    except Exception as e:
        print(f"取得エラー: {e}")
        return

    # 空きがある場合のみ通知
    if status == "空きあり":
        send_notification(status, target_date)
        print(f"通知送信: {status}")
    else:
        # 満室またはデータなしの場合はログを出して終了
        print(f"通知なし: {status}")

if __name__ == "__main__":
    main()
