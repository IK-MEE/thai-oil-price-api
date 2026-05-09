import os
import hmac
import hashlib
import base64
import httpx
import json

from http.server import BaseHTTPRequestHandler
from supabase import create_client

# ── Config ──────────────────────────────────────────────────────────────────
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

LINE_REPLY_API = "https://api.line.me/v2/bot/message/reply"
LINE_PROFILE_API = "https://api.line.me/v2/bot/profile"

FUELS = [
    "ดีเซล B20",
    "ไฮดีเซล S",
    "ไฮ พรีเมียม ดีเซล พลัส",
    "ไฮ พรีเมียม 98 พลัส",
    "แก๊สโซฮอล์ E85 S EVO",
    "แก๊สโซฮอล์ E20 S EVO",
    "แก๊สโซฮอล์ 91 S EVO",
    "แก๊สโซฮอล์ 95 S EVO",
    "ทั้งหมด",
]

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


# ── Signature verification ───────────────────────────────────────────────────
def verify_signature(body: bytes, signature: str) -> bool:
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ── LINE API helpers ─────────────────────────────────────────────────────────
def get_display_name(user_id: str) -> str:
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    res = httpx.get(f"{LINE_PROFILE_API}/{user_id}", headers=headers)
    if res.status_code == 200:
        return res.json().get("displayName", "คุณ")
    return "คุณ"


def reply_message(reply_token: str, messages: list):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"replyToken": reply_token, "messages": messages}
    httpx.post(LINE_REPLY_API, headers=headers, json=payload)


# ── Supabase helpers ─────────────────────────────────────────────────────────
def upsert_user(line_user_id: str, display_name: str):
    supabase.table("users").upsert({
        "line_user_id": line_user_id,
        "display_name": display_name,
        "is_active": True,
    }, on_conflict="line_user_id").execute()


def deactivate_user(line_user_id: str):
    supabase.table("users").update(
        {"is_active": False}
    ).eq("line_user_id", line_user_id).execute()


def get_user_settings(line_user_id: str) -> dict:
    result = supabase.table("users").select(
        "notify_enabled, notify_on_change_only"
    ).eq("line_user_id", line_user_id).single().execute()
    return result.data or {}


def toggle_user_field(line_user_id: str, field: str) -> bool:
    """Toggle a boolean field in users table, return new value."""
    result = supabase.table("users").select(field).eq(
        "line_user_id", line_user_id
    ).single().execute()
    current = result.data.get(field, True)
    new_value = not current
    supabase.table("users").update(
        {field: new_value}
    ).eq("line_user_id", line_user_id).execute()
    return new_value


def toggle_fuel_preference(line_user_id: str, fuel_name: str):
    all_fuels = [f for f in FUELS if f != "ทั้งหมด"]

    if fuel_name == "ทั้งหมด":
        for fuel in all_fuels:
            supabase.table("preferences").upsert({
                "line_user_id": line_user_id,
                "fuel_name": fuel,
                "is_active": True,
            }, on_conflict="line_user_id,fuel_name").execute()
        return "all"

    existing = (
        supabase.table("preferences")
        .select("is_active")
        .eq("line_user_id", line_user_id)
        .eq("fuel_name", fuel_name)
        .execute()
    )

    if existing.data:
        current = existing.data[0]["is_active"]
        supabase.table("preferences").update(
            {"is_active": not current}
        ).eq("line_user_id", line_user_id).eq("fuel_name", fuel_name).execute()
        return "off" if current else "on"
    else:
        supabase.table("preferences").insert({
            "line_user_id": line_user_id,
            "fuel_name": fuel_name,
            "is_active": True,
        }).execute()
        return "on"


def get_active_fuels(line_user_id: str) -> list:
    result = (
        supabase.table("preferences")
        .select("fuel_name")
        .eq("line_user_id", line_user_id)
        .eq("is_active", True)
        .execute()
    )
    return [row["fuel_name"] for row in result.data]


# ── Message builders ─────────────────────────────────────────────────────────
def build_fuel_selection_message(intro_text: str = None, notify_on_change_only: bool = False):
    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
    items = []
    for fuel in FUELS:
        display = FUEL_NAMES.get(fuel, fuel)
        items.append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": display if len(display) <= 20 else display[:20],
                "data": f"fuel={fuel}",
                "displayText": f"เลือก {display}",
            },
        })
    items.append({
        "type": "action",
        "action": {
            "type": "postback",
            "label": "🗑 ยกเลิกทั้งหมด",
            "data": "action=deselect_all",
            "displayText": "ยกเลิกทั้งหมด",
        },
    })
    items.append({
        "type": "action",
        "action": {
            "type": "postback",
            "label": "✅ เสร็จแล้ว",
            "data": "action=done",
            "displayText": "เสร็จแล้ว!",
        },
    })
    text = intro_text or (
        f"⛽ เลือกน้ำมันที่ต้องการติดตาม:\n"
        f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n"
        f"(เลือกได้หลายประเภท กด ✅ เสร็จแล้ว เมื่อเลือกครบ)"
    )
    return {
        "type": "text",
        "text": text,
        "quickReply": {"items": items},
    }


def build_settings_message(user_id: str):
    settings = get_user_settings(user_id)
    notify_enabled = settings.get("notify_enabled", True)
    notify_on_change_only = settings.get("notify_on_change_only", False)

    notify_status = "🔔 เปิดอยู่" if notify_enabled else "🔕 ปิดอยู่"
    change_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"

    return {
        "type": "text",
        "text": (
            f"⚙️ ตั้งค่าการแจ้งเตือน\n\n"
            f"🔔 การแจ้งเตือน: {notify_status}\n"
            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_status}\n\n"
            f"กดปุ่มด้านล่างเพื่อเปลี่ยนการตั้งค่า"
        ),
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "🔔 เปิด/ปิด การแจ้งเตือน",
                        "data": "action=toggle_notify",
                        "displayText": "เปิด/ปิด การแจ้งเตือน",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "📊 แจ้งเมื่อราคาเปลี่ยน",
                        "data": "action=toggle_change_only",
                        "displayText": "แจ้งเฉพาะเมื่อราคาเปลี่ยน",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "⛽ เลือกน้ำมัน",
                        "data": "action=select_fuels",
                        "displayText": "เลือกน้ำมันที่ติดตาม",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "✅ เสร็จแล้ว",
                        "data": "action=settings_done",
                        "displayText": "เสร็จแล้ว!",
                    },
                },
            ]
        },
    }


# ── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Oil Price Bot is running! ⛽"}).encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        signature = self.headers.get("X-Line-Signature", "")
        if not verify_signature(body, signature):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        for event in data.get("events", []):
            event_type = event.get("type")
            user_id = event.get("source", {}).get("userId", "")
            reply_token = event.get("replyToken", "")

            # ── User adds the bot ────────────────────────────────────────────
            if event_type == "follow":
                display_name = get_display_name(user_id)
                upsert_user(user_id, display_name)
                reply_message(reply_token, [build_fuel_selection_message(
                    intro_text=(
                        f"⛽ สวัสดี {display_name}! ยินดีต้อนรับ!\n\n"
                        f"เลือกน้ำมันที่ต้องการติดตามราคาทุกวัน:\n"
                        f"(เลือกได้หลายประเภท กด ✅ เสร็จแล้ว เมื่อเลือกครบ)"
                    )
                )])

            # ── User blocks/removes the bot ──────────────────────────────────
            elif event_type == "unfollow":
                deactivate_user(user_id)

            # ── User taps Quick Reply button ─────────────────────────────────
            elif event_type == "postback":
                postback_data = event.get("postback", {}).get("data", "")

                # Safety net: ensure user exists even if follow event was missed
                display_name = get_display_name(user_id)
                upsert_user(user_id, display_name)

                # Fetch settings once for use across handlers
                settings = get_user_settings(user_id)
                notify_on_change_only = settings.get("notify_on_change_only", False)

                # ── Fuel selection ───────────────────────────────────────────
                if postback_data.startswith("fuel="):
                    fuel_name = postback_data.replace("fuel=", "")
                    result = toggle_fuel_preference(user_id, fuel_name)

                    active_fuels = get_active_fuels(user_id)
                    current = ", ".join(active_fuels) if active_fuels else "ยังไม่มี"
                    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"

                    display_fuel = FUEL_NAMES.get(fuel_name, fuel_name)
                    if result == "all":
                        status_msg = "✅ เลือกน้ำมันทั้งหมดแล้ว!"
                    elif result == "on":
                        status_msg = f"✅ เพิ่ม {display_fuel} แล้ว!"
                    else:
                        status_msg = f"❌ ยกเลิก {display_fuel} แล้ว!"

                    reply_message(reply_token, [build_fuel_selection_message(
                        intro_text=(
                            f"{status_msg}\n\n"
                            f"📋 ที่เลือกไว้: {current}\n"
                            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n\n"
                            f"เลือกเพิ่ม/ยกเลิก หรือกด ✅ เสร็จแล้ว"
                        ),
                        notify_on_change_only=notify_on_change_only,
                    )])

                # ── Deselect all fuels ───────────────────────────────────────
                elif postback_data == "action=deselect_all":
                    all_fuels = [f for f in FUELS if f != "ทั้งหมด"]
                    for fuel in all_fuels:
                        supabase.table("preferences").update(
                            {"is_active": False}
                        ).eq("line_user_id", user_id).eq("fuel_name", fuel).execute()
                    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
                    reply_message(reply_token, [build_fuel_selection_message(
                        intro_text=(
                            f"🗑 ยกเลิกน้ำมันทั้งหมดแล้ว!\n\n"
                            f"📋 ที่เลือกไว้: ยังไม่มี\n"
                            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n\n"
                            f"เลือกใหม่ได้เลย หรือกด ✅ เสร็จแล้ว"
                        ),
                        notify_on_change_only=notify_on_change_only,
                    )])

                # ── Done selecting fuels ─────────────────────────────────────
                elif postback_data == "action=done":
                    active_fuels = get_active_fuels(user_id)
                    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
                    if not active_fuels:
                        reply_message(reply_token, [{
                            "type": "text",
                            "text": "⚠️ ยังไม่ได้เลือกน้ำมันเลย!\nกรุณาเลือกอย่างน้อย 1 ประเภท",
                        }])
                    else:
                        fuel_list = "\n".join([f"  • {FUEL_NAMES.get(f, f)}" for f in active_fuels])
                        reply_message(reply_token, [{
                            "type": "text",
                            "text": (
                                f"🎉 บันทึกแล้ว! คุณจะได้รับราคาน้ำมันทุกวัน 4:00 น.\n\n"
                                f"น้ำมันที่เลือก:\n{fuel_list}\n\n"
                                f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n\n"
                                f"💬 พิมพ์ 'ตั้งค่า' เพื่อจัดการการแจ้งเตือน"
                            ),
                        }])

                # ── Settings: open menu ──────────────────────────────────────
                elif postback_data == "action=settings":
                    reply_message(reply_token, [build_settings_message(user_id)])

                # ── Settings: done ───────────────────────────────────────────
                elif postback_data == "action=settings_done":
                    settings = get_user_settings(user_id)
                    notify_enabled = settings.get("notify_enabled", True)
                    notify_on_change_only = settings.get("notify_on_change_only", False)
                    active_fuels = get_active_fuels(user_id)

                    notify_status = "🔔 เปิดอยู่" if notify_enabled else "🔕 ปิดอยู่"
                    change_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
                    fuel_list = "\n".join([f"  • {f}" for f in active_fuels]) if active_fuels else "  ยังไม่มี"

                    reply_message(reply_token, [{
                        "type": "text",
                        "text": (
                            f"✅ บันทึกการตั้งค่าแล้ว!\n\n"
                            f"🔔 การแจ้งเตือน: {notify_status}\n"
                            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_status}\n\n"
                            f"⛽ น้ำมันที่ติดตาม:\n{fuel_list}\n\n"
                            f"💬 พิมพ์ 'ตั้งค่า' เพื่อกลับมาแก้ไขได้เสมอ"
                        ),
                    }])

                # ── Settings: toggle notify on/off ───────────────────────────
                elif postback_data == "action=toggle_notify":
                    toggle_user_field(user_id, "notify_enabled")
                    reply_message(reply_token, [build_settings_message(user_id)])

                # ── Settings: toggle notify on change only ───────────────────
                elif postback_data == "action=toggle_change_only":
                    toggle_user_field(user_id, "notify_on_change_only")
                    reply_message(reply_token, [build_settings_message(user_id)])

                # ── Settings: go to fuel selection ───────────────────────────
                elif postback_data == "action=select_fuels":
                    active_fuels = get_active_fuels(user_id)
                    current = ", ".join(active_fuels) if active_fuels else "ยังไม่มี"
                    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
                    reply_message(reply_token, [build_fuel_selection_message(
                        intro_text=(
                            f"⛽ เลือกน้ำมันที่ต้องการติดตาม:\n"
                            f"📋 ที่เลือกไว้: {current}\n"
                            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n\n"
                            f"(กดเพื่อเพิ่ม/ยกเลิก กด ✅ เสร็จแล้ว เมื่อเลือกครบ)"
                        ),
                        notify_on_change_only=notify_on_change_only,
                    )])

            # ── User sends text message ──────────────────────────────────────
            elif event_type == "message" and event.get("message", {}).get("type") == "text":
                text = event["message"]["text"].strip().lower()

                if any(word in text for word in ["ตั้งค่า", "setting", "การแจ้งเตือน"]):
                    display_name = get_display_name(user_id)
                    upsert_user(user_id, display_name)
                    reply_message(reply_token, [build_settings_message(user_id)])

                elif any(word in text for word in ["เลือก", "เปลี่ยน", "แก้ไข"]):
                    settings = get_user_settings(user_id)
                    notify_on_change_only = settings.get("notify_on_change_only", False)
                    active_fuels = get_active_fuels(user_id)
                    current = ", ".join(active_fuels) if active_fuels else "ยังไม่มี"
                    change_only_status = "✅ เปิดอยู่" if notify_on_change_only else "❌ ปิดอยู่"
                    reply_message(reply_token, [build_fuel_selection_message(
                        intro_text=(
                            f"⛽ เลือกน้ำมันที่ต้องการติดตาม:\n"
                            f"📋 ที่เลือกไว้: {current}\n"
                            f"📊 แจ้งเฉพาะเมื่อราคาเปลี่ยน: {change_only_status}\n\n"
                            f"(กดเพื่อเพิ่ม/ยกเลิก กด ✅ เสร็จแล้ว เมื่อเลือกครบ)"
                        ),
                        notify_on_change_only=notify_on_change_only,
                    )])

                else:
                    reply_message(reply_token, [{
                        "type": "text",
                        "text": (
                            "⛽ สวัสดี!\n\n"
                            "พิมพ์คำสั่งเหล่านี้ได้เลย:\n"
                            "• 'เลือก' — เลือกน้ำมันที่ติดตาม\n"
                            "• 'ตั้งค่า' — จัดการการแจ้งเตือน"
                        ),
                    }])

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())