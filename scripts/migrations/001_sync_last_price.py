"""
Migration 001 — Sync last_price with current Bangchak API prices

Problem: last_price in preferences table may be out of sync with
         actual current prices due to schedule/logic changes.

Solution: Fetch today's prices from Bangchak API and update
          last_price for all active preferences where the value
          differs. last_notified_at is left untouched.

Run once locally:
    python migrations/001_sync_last_price.py
"""

import requests
import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OIL_API_URL = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def fetch_oil_prices() -> dict:
    response = requests.get(OIL_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    raw = data[0]
    oil_list = json.loads(raw["OilList"])
    return {oil["OilName"]: oil["PriceToday"] for oil in oil_list}


def migrate():
    print("🔍 Fetching current oil prices from Bangchak API...")
    oil_dict = fetch_oil_prices()
    print(f"✅ Fetched {len(oil_dict)} fuel prices")

    print("\n🔍 Reading active preferences from Supabase...")
    result = (
        supabase.table("preferences")
        .select("id, line_user_id, fuel_name, last_price")
        .eq("is_active", True)
        .execute()
    )
    prefs = result.data
    print(f"✅ Found {len(prefs)} active preference row(s)")

    updated = 0
    skipped = 0
    not_found = 0

    print()
    for pref in prefs:
        user_id = pref["line_user_id"]
        fuel_name = pref["fuel_name"]
        last_price = pref["last_price"]
        today_price = oil_dict.get(fuel_name)

        if today_price is None:
            print(f"⚠️  Fuel not found in API: {fuel_name}")
            not_found += 1
            continue

        if last_price == today_price:
            print(f"✅ Already in sync: {fuel_name} = ฿{today_price}")
            skipped += 1
            continue

        supabase.table("preferences").update({
            "last_price": today_price,
        }).eq("line_user_id", user_id).eq("fuel_name", fuel_name).execute()

        print(f"🔄 [{pref['id']}] {fuel_name} | ฿{last_price} → ฿{today_price}")
        updated += 1

    print(f"\n📊 Done! Updated: {updated} | Already in sync: {skipped} | Not found: {not_found}")


if __name__ == "__main__":
    migrate()