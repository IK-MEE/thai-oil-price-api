# ⛽ Oil Price LINE Bot

Sends **personalized** daily Bangchak oil prices to LINE followers automatically.
Each user picks which fuels they want to track and controls their own notification settings — completely free, no server cost.

---

## 📁 Project Structure

```
oil-price-bot/
├── notify.py                        # Daily notification script
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Vercel project config
├── schema.sql                       # Database schema reference
├── .env.example                     # Example environment variables
├── .gitignore
├── api/
│   └── webhook.py                   # Vercel serverless webhook
├── scripts/
│   └── migrations/
│       └── 001_sync_last_price.py   # Sync last_price with API
└── .github/
    └── workflows/
        └── daily-notify.yml         # GitHub Actions scheduler
```

---

## 🏗️ Architecture

```
User adds bot → Vercel webhook → saves to Supabase
User picks fuels → Vercel webhook → saves preferences

Every ~21:00 → GitHub Actions → fetches oil prices from Bangchak API
                              → reads each user's preferences from Supabase
                              → sends personalized LINE message per user
```

---

## 🆓 Free Stack

| Component | Tool | Cost |
|---|---|---|
| Webhook server | Vercel serverless | Free |
| Database | Supabase (PostgreSQL) | Free |
| Scheduler | GitHub Actions | Free |
| Messaging | LINE Messaging API | Free |
| Oil price data | Bangchak API | Free |

---

## 🚀 Setup Guide

### 1. Supabase — create tables
Create a new Supabase project then run `schema.sql` in the SQL Editor:
- Go to your project → **SQL Editor** → **New query**
- Paste the contents of `schema.sql` and click **Run**

Get your credentials from **Settings** → **Integrations** → **Data API**:
- `Project URL` — looks like `https://xxxx.supabase.co`
- `Service Role` key — under **Settings** → **API**

### 2. LINE Developers — create a Messaging API channel
1. Go to https://developers.line.biz/console/
2. Create a **Provider** → **New channel** → **Messaging API**
3. Create a **LINE Official Account** when prompted
4. Go to **Messaging API** tab → issue a **Channel access token**
5. Go to **Basic settings** tab → copy your **Channel secret**
6. Scan the QR code on the **Messaging API** tab to add your bot as a friend

### 3. Vercel — deploy webhook server
1. Push this repo to GitHub
2. Go to https://vercel.com → **Add New Project** → import your repo
3. Vercel auto-detects the `api/` folder and deploys ✅
4. Go to your project → **Settings** → **Environment Variables** and add:

| Key | Value |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | Your LINE channel access token |
| `LINE_CHANNEL_SECRET` | Your LINE channel secret |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key |

5. Go to **Deployments** → **Redeploy** to pick up the new env vars
6. Copy your Vercel domain (e.g. `https://your-app.vercel.app`)

### 4. LINE — set webhook URL
1. Go to LINE Developers → your channel → **Messaging API** tab
2. Set **Webhook URL** to: `https://your-app.vercel.app/webhook`
3. Enable **"Use webhook"** toggle
4. Click **"Verify"** — should return success ✅

### 5. GitHub — add secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | Your LINE channel access token |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key |

### 6. Test
- Add your LINE bot as a friend (scan QR code in LINE Developers Console)
- You should receive a fuel selection menu immediately!
- Pick your fuels → tap ✅ เสร็จแล้ว
- Go to GitHub Actions → **Daily Oil Price Notification** → **Run workflow** to test

---

## ⏰ Schedule
Runs every day at approximately **21:00 Bangkok time (ICT, UTC+7)**.
Bangchak publishes the next day's prices around 20:30 — notifying at 21:00 gives users ~8 hours before the price takes effect at 05:00 the next morning.
GitHub Actions cron is not guaranteed to run at exact time — expect ±1 hour variance.

To change the schedule, edit `.github/workflows/daily-notify.yml`:
```yaml
- cron: "0 14 * * *"   # 14:00 UTC = 21:00 Bangkok (UTC+7)
```

---

## 💬 User Commands
Users can send these messages to the bot at any time:
- **"เลือก"** / **"เปลี่ยน"** / **"แก้ไข"** — open fuel selection menu
- **"ตั้งค่า"** / **"setting"** / **"การแจ้งเตือน"** — open settings menu

---

## ⚙️ User Settings
Each user can configure via the settings menu:
- 🔔 **เปิด/ปิด การแจ้งเตือน** — pause all notifications without unfollowing
- 📊 **แจ้งเฉพาะเมื่อราคาเปลี่ยน** — only notify when tracked fuel prices actually change

---

## 🛢 Supported Fuels

| Display Name | Full Name |
|---|---|
| B20 | ดีเซล B20 |
| ไฮดีเซล | ไฮดีเซล S |
| พรีเมียม ดีเซล | ไฮ พรีเมียม ดีเซล พลัส |
| พรีเมียม 98 | ไฮ พรีเมียม 98 พลัส |
| E85 | แก๊สโซฮอล์ E85 S EVO |
| E20 | แก๊สโซฮอล์ E20 S EVO |
| 91 | แก๊สโซฮอล์ 91 S EVO |
| 95 | แก๊สโซฮอล์ 95 S EVO |

---

## 💬 Sample LINE Message

```
🛢 B20 | ฿32.95 | 🟢 ▼ -0.85
🛢 E20 | ฿35.45
🛢 95  | ฿42.45 | 🔴 ▲ +0.50

📅 07/05/2569
📌 ราคามีผล ณ วันที่ 8 พ.ค. 69 เวลา 05.00 น.

💬 พิมพ์ 'ตั้งค่า' เพื่อจัดการการแจ้งเตือน
```

---

## 🔑 Local Development

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

Run the notification script locally:
```bash
pip install -r requirements.txt
python notify.py
```

Run a migration script:
```bash
python scripts/migrations/001_sync_last_price.py
```

---

## 🤖 Built With AI Assistance

This project was collaboratively designed and built with **Claude** (by Anthropic) as an AI pair programmer —
handling architecture decisions, code generation, debugging, and refactoring across the entire session.

> *"I'll leave my note in case I fall asleep unnoticed"* — the developer, at 2AM 😄