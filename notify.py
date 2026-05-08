import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
LINE_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OIL_API_URL = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ── Fetch oil prices ─────────────────────────────────────────────────────────
def fetch_oil_prices():
    response = requests.get(OIL_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    raw = data[0]

    oil_date = raw.get("OilPriceDate", "")
    remark = raw.get("OilRemark2", "")
    oil_list = json.loads(raw["OilList"])

    # Convert list to dict for easy lookup
    oil_dict = {oil["OilName"]: oil for oil in oil_list}
    return oil_date, remark, oil_dict


# ── Format price change ──────────────────────────────────────────────────────
def format_price_change(diff):
    if diff > 1:
        return f"🔴 ▲ +{diff:.2f}"
    elif diff > 0:
        return f"▲ +{diff:.2f}"
    elif diff < -1:
        return f"🟢 ▼ {diff:.2f}"
    elif diff < 0:
        return f"▼ {diff:.2f}"
    else:
        return f"─ เท่าเดิม"


# ── Build personalized message ───────────────────────────────────────────────
def build_message(display_name: str, fuel_prefs: list, oil_date: str, remark: str, oil_dict: dict):
    lines = []
    lines.append(f"สวัสดี {display_name}! 👋")
    lines.append(f"⛽ ราคาน้ำมัน Bangchak วันนี้")
    lines.append(f"📅 {oil_date}")
    lines.append("─" * 28)

    for fuel_name in fuel_prefs:
        oil = oil_dict.get(fuel_name)
        if not oil:
            continue
        today = oil["PriceToday"]
        diff = oil["PriceDifYesterday"]
        change = format_price_change(diff)
        lines.append(f"🛢 {fuel_name}")
        lines.append(f"   {today:.2f} บาท/ลิตร  {change}")

    lines.append("─" * 28)
    lines.append(f"📌 {remark}")
    lines.append("\n💬 พิมพ์ 'เลือก' เพื่อเปลี่ยนน้ำมันที่ติดตาม")

    return "\n".join(lines)


# ── Send LINE message ────────────────────────────────────────────────────────
def send_line_message(user_id: str, text: str):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()


# ── Get all active users and their preferences ───────────────────────────────
def get_active_users():
    users = (
        supabase.table("users")
        .select("line_user_id, display_name")
        .eq("is_active", True)
        .execute()
    )
    return users.data


def get_user_fuel_preferences(line_user_id: str) -> list:
    prefs = (
        supabase.table("preferences")
        .select("fuel_name")
        .eq("line_user_id", line_user_id)
        .eq("is_active", True)
        .execute()
    )
    return [row["fuel_name"] for row in prefs.data]


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Fetching oil prices at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    oil_date, remark, oil_dict = fetch_oil_prices()
    print(f"✅ Oil prices fetched for {oil_date}")

    users = get_active_users()
    print(f"👥 Found {len(users)} active user(s)")

    success = 0
    failed = 0

    for user in users:
        user_id = user["line_user_id"]
        display_name = user.get("display_name", "คุณ")

        fuel_prefs = get_user_fuel_preferences(user_id)
        if not fuel_prefs:
            print(f"⚠️  Skipping {display_name} — no fuel preferences set")
            continue

        try:
            message = build_message(display_name, fuel_prefs, oil_date, remark, oil_dict)
            send_line_message(user_id, message)
            print(f"✅ Sent to {display_name} ({len(fuel_prefs)} fuels)")
            success += 1
        except Exception as e:
            print(f"❌ Failed to send to {display_name}: {e}")
            failed += 1

    print(f"\n📊 Done! Success: {success} | Failed: {failed}")


if __name__ == "__main__":
    main()