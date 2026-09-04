-- Migration: create bakong_qr table to store generated BAKONG QR metadata
-- Added by Copilot QA helper on 2026-08-20

CREATE TABLE IF NOT EXISTS bakong_qr (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    account_number TEXT,
    currency TEXT,
    merchant_name TEXT,
    qr_data TEXT,
    qr_image_path TEXT,
    qr_type TEXT,
    created_at TEXT
);
