-- Users table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  line_user_id TEXT UNIQUE NOT NULL,
  display_name TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  notify_enabled BOOLEAN DEFAULT TRUE,
  notify_on_change_only BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Preferences table
CREATE TABLE IF NOT EXISTS preferences (
  id SERIAL PRIMARY KEY,
  line_user_id TEXT NOT NULL REFERENCES users(line_user_id) ON DELETE CASCADE,
  fuel_name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  last_price FLOAT DEFAULT NULL,
  last_notified_at TIMESTAMP DEFAULT NULL,
  UNIQUE(line_user_id, fuel_name)
);