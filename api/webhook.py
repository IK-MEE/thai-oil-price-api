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


# ── Quick Reply builder ──────────────────────────────────────────────────────
def build_fuel_selection_message():
    items = []
    for fuel in FUELS:
        items.append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": fuel if len(fuel) <= 20 else fuel[:20],
                "data": f"fuel={fuel}",
                "displayText": f"เลือก {fuel}",
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
    return {
        "type": "text",
        "text": "⛽ สวัสดี! เลือกน้ำมันที่ต้องการติดตามราคาทุกวัน:\n(เลือกได้หลายประเภท กด ✅ เสร็จแล้ว เมื่อเลือกครบ)",
        "quickReply": {"items": items},
    }


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


# ── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Oil Price Bot is running! ⛽"}).encode())

    def do_POST(self):
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Verify LINE signature
        signature = self.headers.get("X-Line-Signature", "")
        if not verify_signature(body, signature):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        # Parse events
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

            # User adds the bot
            if event_type == "follow":
                display_name = get_display_name(user_id)
                upsert_user(user_id, display_name)
                reply_message(reply_token, [build_fuel_selection_message()])

            # User blocks/removes the bot
            elif event_type == "unfollow":
                deactivate_user(user_id)

            # User taps Quick Reply button
            elif event_type == "postback":
                postback_data = event.get("postback", {}).get("data", "")

                if postback_data.startswith("fuel="):
                    fuel_name = postback_data.replace("fuel=", "")
                    result = toggle_fuel_preference(user_id, fuel_name)

                    if result == "all":
                        msg = "✅ เลือกน้ำมันทั้งหมดแล้ว!\nกด ✅ เสร็จแล้ว เพื่อยืนยัน"
                    elif result == "on":
                        msg = f"✅ เพิ่ม {fuel_name} แล้ว!\nเลือกเพิ่มได้ หรือกด ✅ เสร็จแล้ว"
                    else:
                        msg = f"❌ ยกเลิก {fuel_name} แล้ว!\nเลือกเพิ่มได้ หรือกด ✅ เสร็จแล้ว"

                    reply_message(reply_token, [{"type": "text", "text": msg}])

                elif postback_data == "action=done":
                    active_fuels = get_active_fuels(user_id)
                    if not active_fuels:
                        reply_message(reply_token, [{
                            "type": "text",
                            "text": "⚠️ ยังไม่ได้เลือกน้ำมันเลย!\nกรุณาเลือกอย่างน้อย 1 ประเภท",
                        }])
                    else:
                        fuel_list = "\n".join([f"  • {f}" for f in active_fuels])
                        reply_message(reply_token, [{
                            "type": "text",
                            "text": f"🎉 บันทึกแล้ว! คุณจะได้รับราคาน้ำมันทุกวัน 4:00 น.\n\nน้ำมันที่เลือก:\n{fuel_list}",
                        }])

            # User sends text message
            elif event_type == "message" and event.get("message", {}).get("type") == "text":
                text = event["message"]["text"].strip().lower()
                if any(word in text for word in ["เลือก", "เปลี่ยน", "แก้ไข", "setting", "ตั้งค่า"]):
                    reply_message(reply_token, [build_fuel_selection_message()])
                else:
                    reply_message(reply_token, [{
                        "type": "text",
                        "text": "⛽ พิมพ์ 'เลือก' เพื่อเปลี่ยนประเภทน้ำมันที่ติดตามได้เลย!",
                    }])

        # Always return 200 to LINE
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())