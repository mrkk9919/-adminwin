-- Wing Bank shared database schema.
-- Used by tgbot (Go, writer) and admin (FastAPI, reader + partial writer).
-- SQLite must be opened in WAL mode for safe concurrent access.

CREATE TABLE IF NOT EXISTS customers (
  telegram_id INTEGER PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  phone TEXT,
  role TEXT NOT NULL DEFAULT 'customer',   -- customer | vip | banned
  is_active INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_message_id INTEGER,
  customer_id INTEGER NOT NULL,            -- Telegram user ID (matches customers.telegram_id)
  direction TEXT NOT NULL,                 -- 'in' (user -> bot) | 'out' (bot/admin -> user)
  content_type TEXT NOT NULL DEFAULT 'text', -- text | photo | document | callback
  content TEXT,
  source TEXT NOT NULL DEFAULT 'bot',      -- bot | admin
  read_at DATETIME,
  replied_by TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(read_at) WHERE read_at IS NULL AND direction = 'in';

CREATE TABLE IF NOT EXISTS orders (
  hash TEXT PRIMARY KEY,
  customer_id INTEGER,                     -- nullable; admin-created orders may not be bound
  amount TEXT,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL DEFAULT 'unknown',  -- pending | success | failed | unknown
  bank TEXT,
  receiver TEXT,
  tx_date TEXT,
  tx_id TEXT,
  notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS bot_heartbeats (
  bot_name TEXT PRIMARY KEY,
  last_heartbeat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'unknown',  -- alive | degraded | dead | unknown
  version TEXT,
  uptime_seconds INTEGER,
  meta TEXT                                -- JSON payload for extra metrics
);

CREATE TABLE IF NOT EXISTS sms_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone TEXT NOT NULL,
  otp_code TEXT,
  message TEXT,
  provider TEXT NOT NULL,                  -- mock | camintel | ...
  provider_msg_id TEXT,
  status TEXT NOT NULL DEFAULT 'sent',     -- sent | delivered | failed
  cost_cents INTEGER,
  error TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sms_logs_phone ON sms_logs(phone, created_at DESC);
