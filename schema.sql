-- ── Users table ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  line_user_id TEXT UNIQUE NOT NULL,
  display_name TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  notify_enabled BOOLEAN DEFAULT TRUE,
  notify_on_change_only BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- ── Preferences table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS preferences (
  id SERIAL PRIMARY KEY,
  line_user_id TEXT NOT NULL REFERENCES users(line_user_id) ON DELETE CASCADE,
  fuel_name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  last_price FLOAT DEFAULT NULL,
  last_notified_at TIMESTAMP DEFAULT NULL,
  UNIQUE(line_user_id, fuel_name)
);

-- ── Oil price logs table ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS oil_price_logs (
  id SERIAL PRIMARY KEY,
  oil_date_now TEXT,
  oil_price_date TEXT NOT NULL,
  oil_price_time TEXT,
  oil_message_date TEXT,
  oil_message_time TEXT,
  oil_remark2 TEXT,
  -- ดีเซล B20
  b20_yesterday FLOAT,
  b20_today FLOAT,
  b20_tomorrow FLOAT,
  -- ไฮดีเซล S
  hi_diesel_yesterday FLOAT,
  hi_diesel_today FLOAT,
  hi_diesel_tomorrow FLOAT,
  -- ไฮ พรีเมียม ดีเซล พลัส
  premium_diesel_yesterday FLOAT,
  premium_diesel_today FLOAT,
  premium_diesel_tomorrow FLOAT,
  -- ไฮ พรีเมียม 98 พลัส
  premium_98_yesterday FLOAT,
  premium_98_today FLOAT,
  premium_98_tomorrow FLOAT,
  -- แก๊สโซฮอล์ E85 S EVO
  e85_yesterday FLOAT,
  e85_today FLOAT,
  e85_tomorrow FLOAT,
  -- แก๊สโซฮอล์ E20 S EVO
  e20_yesterday FLOAT,
  e20_today FLOAT,
  e20_tomorrow FLOAT,
  -- แก๊สโซฮอล์ 91 S EVO
  gasohol_91_yesterday FLOAT,
  gasohol_91_today FLOAT,
  gasohol_91_tomorrow FLOAT,
  -- แก๊สโซฮอล์ 95 S EVO
  gasohol_95_yesterday FLOAT,
  gasohol_95_today FLOAT,
  gasohol_95_tomorrow FLOAT,
  fetched_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(oil_date_now)
);

-- ── Notify logs table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_logs (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  line_user_id TEXT NOT NULL REFERENCES users(line_user_id) ON DELETE CASCADE,
  fuel_name TEXT NOT NULL,
  price FLOAT NOT NULL,
  status TEXT DEFAULT 'sent',
  error_message TEXT DEFAULT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);