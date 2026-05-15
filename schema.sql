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
  b20 FLOAT,
  hi_diesel FLOAT,
  premium_diesel FLOAT,
  premium_98 FLOAT,
  e85 FLOAT,
  e20 FLOAT,
  gasohol_91 FLOAT,
  gasohol_95 FLOAT,
  fetched_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(oil_price_date)
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