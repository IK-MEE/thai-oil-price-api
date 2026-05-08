# ⛽ Oil Price LINE Notifier

Sends daily Bangchak oil prices to your LINE account automatically via GitHub Actions — completely free, no server needed.

---

## 📁 Project Structure

```
oil-price-bot/
├── notify.py                        # Main script
├── requirements.txt                 # Python dependencies
└── .github/
    └── workflows/
        └── daily-notify.yml         # GitHub Actions scheduler
```

---

## 🚀 Setup Guide

### 1. Create a GitHub Repository
- Create a new repo (public or private, both work)
- Upload all files maintaining the folder structure above

### 2. Add GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these two secrets:

| Secret Name | Value |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | Your LINE channel access token |
| `LINE_USER_ID` | Your LINE user ID (starts with `U...`) |

### 3. Enable GitHub Actions
- Go to the **Actions** tab in your repo
- If prompted, click **"I understand my workflows, go ahead and enable them"**

### 4. Test it manually
- Go to **Actions** → **"Daily Oil Price Notification"**
- Click **"Run workflow"** → **"Run workflow"**
- Check your LINE app for the message! 📲

---

## ⏰ Schedule
The bot runs every day at **06:00 AM Bangkok time (ICT, UTC+7)**.

To change the time, edit the cron expression in `.github/workflows/daily-notify.yml`:
```yaml
- cron: "0 23 * * *"   # 23:00 UTC = 06:00 AM Bangkok (UTC+7)
```

---

## 🛢 Fuels Included
- ดีเซล B20
- ไฮดีเซล S
- แก๊สโซฮอล์ E20 S EVO
- แก๊สโซฮอล์ 91 S EVO
- แก๊สโซฮอล์ 95 S EVO

To add/remove fuels, edit the `FUELS_TO_SHOW` list in `notify.py`.

---

## 💬 Sample LINE Message
```
⛽ ราคาน้ำมัน Bangchak วันนี้
📅 07/05/2569
────────────────────────────
🛢 ดีเซล B20
   32.95 บาท/ลิตร  ▼ -0.85
🛢 ไฮดีเซล S
   39.95 บาท/ลิตร  ▼ -0.85
...
────────────────────────────
📌 ราคามีผล ณ วันที่ 8 พ.ค. 69 เวลา 05.00 น.
```
