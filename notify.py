import requests
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
LINE_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OIL_API_URL = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ── Fuel name mapping (API name → display name) ──────────────────────────────
FUEL_NAMES = {
    "ดีเซล B20":              "B20",
    "ไฮดีเซล S":              "ไฮดีเซล",
    "ไฮ พรีเมียม ดีเซล พลัส": "พรีเมียม ดีเซล",
    "ไฮ พรีเมียม 98 พลัส":    "พรีเมียม 98",
    "แก๊สโซฮอล์ E85 S EVO":   "E85",
    "แก๊สโซฮอล์ E20 S EVO":   "E20",
    "แก๊สโซฮอล์ 91 S EVO":    "91",
    "แก๊สโซฮอล์ 95 S EVO":    "95",
}

# ── Fuel API name → oil_price_logs column prefix ─────────────────────────────
FUEL_COLUMNS = {
    "ดีเซล B20":              "b20",
    "ไฮดีเซล S":              "hi_diesel",
    "ไฮ พรีเมียม ดีเซล พลัส": "premium_diesel",
    "ไฮ พรีเมียม 98 พลัส":    "premium_98",
    "แก๊สโซฮอล์ E85 S EVO":   "e85",
    "แก๊สโซฮอล์ E20 S EVO":   "e20",
    "แก๊สโซฮอล์ 91 S EVO":    "gasohol_91",
    "แก๊สโซฮอล์ 95 S EVO":    "gasohol_95",
}

BKK_TZ = timezone(timedelta(hours=7))


# ── Fetch oil prices ─────────────────────────────────────────────────────────
def fetch_oil_prices():
    response = requests.get(OIL_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    raw = data[0]
    meta = {
        "oil_date_now":     raw.get("OilDateNow", ""),
        "oil_price_date":   raw.get("OilPriceDate", ""),
        "oil_price_time":   raw.get("OilPriceTime", ""),
        "oil_message_date": raw.get("OilMessageDate", ""),
        "oil_message_time": raw.get("OilMessageTime", ""),
        "oil_remark2":      raw.get("OilRemark2", ""),
    }
    oil_list = json.loads(raw["OilList"])
    oil_dict = {oil["OilName"]: oil for oil in oil_list}
    return meta, oil_dict


# ── Format price change ──────────────────────────────────────────────────────
def format_price_change(tomorrow_price: float, last_price: float | None) -> str:
    if last_price is None:
        return None
    diff = round(tomorrow_price - last_price, 2)
    if diff >= 0.4:
        return f"🔴 ▲ +{diff:.2f}"
    elif diff > 0:
        return f"▲ +{diff:.2f}"
    elif diff <= -0.4:
        return f"🟢 ▼ {diff:.2f}"
    elif diff < 0:
        return f"▼ {diff:.2f}"
    else:
        return None


# ── Build personalized message ───────────────────────────────────────────────
def build_message(display_name: str, fuels_to_send: list, meta: dict, oil_dict: dict):
    lines = []

    for fuel_api_name, tomorrow_price, last_price in fuels_to_send:
        display_name_fuel = FUEL_NAMES.get(fuel_api_name, fuel_api_name)
        change = format_price_change(tomorrow_price, last_price)
        line = f"🛢 {display_name_fuel} | ฿{tomorrow_price:.2f}"
        if change:
            line += f" | {change}"
        lines.append(line)

    lines.append(f"\n📅 ข้อมูลล่าสุด {meta['oil_price_date']}")
    lines.append(f"📌 {meta['oil_remark2']} เป็นต้นไป")
    lines.append("\n💬 พิมพ์ 'ตั้งค่า' เพื่อจัดการการแจ้งเตือน")

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


# ── Get all active users with their preferences in one query ─────────────────
def get_users_with_preferences():
    result = (
        supabase.table("users")
        .select("id, line_user_id, display_name, notify_enabled, notify_on_change_only, preferences(fuel_name, is_active, last_price, last_notified_at)")
        .eq("is_active", True)
        .execute()
    )
    return result.data


# ── Update last_price and last_notified_at after sending ─────────────────────
def update_price_history(line_user_id: str, fuel_name: str, new_price: float):
    supabase.table("preferences").update({
        "last_price": new_price,
        "last_notified_at": datetime.now(BKK_TZ).isoformat(),
    }).eq("line_user_id", line_user_id).eq("fuel_name", fuel_name).execute()


# ── Log oil prices to DB ─────────────────────────────────────────────────────
def log_oil_prices(meta: dict, oil_dict: dict):
    row = {
        "oil_date_now":     meta["oil_date_now"],
        "oil_price_date":   meta["oil_price_date"],
        "oil_price_time":   meta["oil_price_time"],
        "oil_message_date": meta["oil_message_date"],
        "oil_message_time": meta["oil_message_time"],
        "oil_remark2":      meta["oil_remark2"],
        "fetched_at":       datetime.now(BKK_TZ).isoformat(),
    }
    for fuel_api_name, db_col_name in FUEL_COLUMNS.items():
        oil = oil_dict.get(fuel_api_name)
        row[f"{db_col_name}_yesterday"] = oil["PriceYesterday"] if oil else None
        row[f"{db_col_name}_today"]     = oil["PriceToday"]     if oil else None
        row[f"{db_col_name}_tomorrow"]  = oil["PriceTomorrow"]  if oil else None

    supabase.table("oil_price_logs").upsert(
        row, on_conflict="oil_date_now"
    ).execute()
    print(f"📝 Oil prices logged — published: {meta['oil_price_date']} | effective: {meta['oil_remark2']}")


# ── Log notify to DB ─────────────────────────────────────────────────────────
def log_notify(user_pk: int, line_user_id: str, fuels_to_send: list, status: str = "sent", error: str = None):
    rows = [
        {
            "user_id": user_pk,
            "line_user_id": line_user_id,
            "fuel_name": fuel_name,
            "price": tomorrow_price,        # ← price shown in message
            "status": status,
            "error_message": error,
            "created_at": datetime.now(BKK_TZ).isoformat(),
        }
        for fuel_name, tomorrow_price, _ in fuels_to_send
    ]
    supabase.table("notify_logs").insert(rows).execute()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Fetching oil prices at {datetime.now(BKK_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    meta, oil_dict = fetch_oil_prices()
    print(f"✅ Oil prices fetched — published: {meta['oil_price_date']} {meta['oil_price_time']} | effective: {meta['oil_remark2']}")

    # ── Log oil prices ───────────────────────────────────────────────────────
    try:
        log_oil_prices(meta, oil_dict)
    except Exception as e:
        print(f"⚠️ Failed to log oil prices: {e}")

    users = get_users_with_preferences()
    print(f"👥 Found {len(users)} active user(s)")

    success = 0
    failed = 0
    skipped = 0

    for user in users:
        user_pk = user["id"]
        user_id = user["line_user_id"]
        display_name = user.get("display_name", "คุณ")
        notify_enabled = user.get("notify_enabled", True)
        notify_on_change_only = user.get("notify_on_change_only", False)
        preferences = [p for p in user.get("preferences", []) if p["is_active"]]

        # ── Skip if notifications disabled ───────────────────────────────────
        if not notify_enabled:
            print(f"🔕 Skipping {display_name} — notifications disabled")
            skipped += 1
            continue

        # ── Skip if no fuel preferences set ─────────────────────────────────
        if not preferences:
            print(f"⚠️  Skipping {display_name} — no fuel preferences set")
            skipped += 1
            continue

        # ── Determine which fuels to include in message ──────────────────────
        # fuels_to_send: list of (fuel_api_name, tomorrow_price, last_price)
        fuels_to_send = []
        fuels_to_update = []

        for pref in preferences:
            fuel_name = pref["fuel_name"]
            last_price = pref.get("last_price")
            oil = oil_dict.get(fuel_name)
            if not oil:
                continue

            tomorrow_price = oil["PriceTomorrow"]
            price_changed = last_price is None or tomorrow_price != last_price

            # Unified check — always send if not change-only, or send if changed
            if not notify_on_change_only or price_changed:
                fuels_to_send.append((fuel_name, tomorrow_price, last_price))
                fuels_to_update.append((fuel_name, tomorrow_price))

        # ── Skip if notify_on_change_only and nothing changed ────────────────
        if not fuels_to_send:
            print(f"📭 Skipping {display_name} — no price changes today")
            skipped += 1
            continue

        # ── Send message ─────────────────────────────────────────────────────
        try:
            message = build_message(display_name, fuels_to_send, meta, oil_dict)
            send_line_message(user_id, message)

            # Update last_price with tomorrow's price for next run comparison
            for fuel_name, tomorrow_price in fuels_to_update:
                update_price_history(user_id, fuel_name, tomorrow_price)

            # Log notify — success
            log_notify(user_pk, user_id, fuels_to_send, status="sent")

            print(f"✅ Sent to {display_name} ({len(fuels_to_send)} fuels)")
            success += 1
        except Exception as e:
            # Log notify — failure
            log_notify(user_pk, user_id, fuels_to_send, status="failed", error=str(e))
            print(f"❌ Failed to send to {display_name}: {e}")
            failed += 1

    print(f"\n📊 Done! Success: {success} | Skipped: {skipped} | Failed: {failed}")


if __name__ == "__main__":
    main()