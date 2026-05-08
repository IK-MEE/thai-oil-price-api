import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# ── Config from environment variables ──────────────────────────────────────
load_dotenv()
LINE_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
OIL_API_URL = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"

# ── Fuel types to include in the message ───────────────────────────────────
FUELS_TO_SHOW = [
    "ดีเซล B20",
    "ไฮดีเซล S",
    "แก๊สโซฮอล์ E20 S EVO",
    "แก๊สโซฮอล์ 91 S EVO",
    "แก๊สโซฮอล์ 95 S EVO",
]


def fetch_oil_prices():
    response = requests.get(OIL_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    raw = data[0]

    oil_date = raw.get("OilPriceDate", "")
    remark = raw.get("OilRemark2", "")
    oil_list = json.loads(raw["OilList"])

    return oil_date, remark, oil_list


def format_price_change(diff):
    if diff > 0:
        return f"▲ +{diff:.2f}"
    elif diff < 0:
        return f"▼ {diff:.2f}"
    else:
        return f"  ─ เท่าเดิม"


def build_message(oil_date, remark, oil_list):
    # Convert Buddhist Era date to a readable format
    lines = []
    lines.append("⛽ ราคาน้ำมัน Bangchak วันนี้")
    lines.append(f"📅 {oil_date}")
    lines.append("─" * 28)

    for oil in oil_list:
        name = oil["OilName"]
        if name not in FUELS_TO_SHOW:
            continue
        today = oil["PriceToday"]
        diff = oil["PriceDifYesterday"]
        change = format_price_change(diff)
        lines.append(f"🛢 {name}")
        lines.append(f"   {today:.2f} บาท/ลิตร  {change}")

    lines.append("─" * 28)
    lines.append(f"📌 {remark}")

    return "\n".join(lines)


def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    print("✅ Message sent successfully!")


def main():
    print(f"🔍 Fetching oil prices at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    oil_date, remark, oil_list = fetch_oil_prices()
    message = build_message(oil_date, remark, oil_list)
    print("📨 Message preview:\n")
    print(message)
    print()
    send_line_message(message)


if __name__ == "__main__":
    main()
