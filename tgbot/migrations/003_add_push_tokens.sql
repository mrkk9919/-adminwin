-- Migration 003: Add push notification token fields
-- Adds FCM (Android) and APNs (iOS) token columns to customers table
-- Note: SQLite < 3.35 doesn't support ADD COLUMN IF NOT EXISTS
-- The Go migration code handles "duplicate column" errors gracefully

-- Add FCM token column
ALTER TABLE customers ADD COLUMN fcm_token VARCHAR(255);

-- Add APNs token column
ALTER TABLE customers ADD COLUMN apns_token VARCHAR(255);

-- Add push enabled flag
ALTER TABLE customers ADD COLUMN push_enabled INTEGER DEFAULT 1;

-- Add push token update timestamp
ALTER TABLE customers ADD COLUMN push_token_updated_at DATETIME;

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_customers_fcm_token ON customers(fcm_token);
CREATE INDEX IF NOT EXISTS idx_customers_apns_token ON customers(apns_token);
