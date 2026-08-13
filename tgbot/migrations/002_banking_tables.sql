-- Wing Bank Admin: Banking features (accounts, transactions, KYC)
-- Extends existing schema for full banking administration.
-- All DDL uses IF NOT EXISTS patterns for safe re-running.

-- Bank accounts linked to customers
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL,             -- references customers.telegram_id
  account_number TEXT NOT NULL UNIQUE,
  currency TEXT NOT NULL DEFAULT 'USD',     -- KHR | USD
  balance INTEGER NOT NULL DEFAULT 0,       -- stored as integer (cents for USD, whole for KHR)
  status TEXT NOT NULL DEFAULT 'active',    -- active | frozen | closed
  type TEXT NOT NULL DEFAULT 'wallet',      -- savings | current | wallet
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_currency ON accounts(currency);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);

-- Financial transactions
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_account_id INTEGER,                  -- nullable (deposits have no source)
  to_account_id INTEGER,                    -- nullable (withdrawals have no destination)
  amount INTEGER NOT NULL,                  -- stored as integer (cents for USD, whole for KHR)
  currency TEXT NOT NULL DEFAULT 'USD',     -- KHR | USD
  type TEXT NOT NULL DEFAULT 'transfer',    -- transfer | deposit | withdrawal | exchange
  status TEXT NOT NULL DEFAULT 'completed', -- completed | pending | failed | reversed
  description TEXT,
  reference_id TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_currency ON transactions(currency);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);

-- KYC (Know Your Customer) verification records
CREATE TABLE IF NOT EXISTS kyc_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL,             -- references customers.telegram_id
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
  document_type TEXT NOT NULL DEFAULT 'national_id',  -- national_id | passport | driving_license
  document_number TEXT,
  full_name TEXT,
  date_of_birth TEXT,
  address TEXT,
  submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME,
  reviewed_by TEXT,
  rejection_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_kyc_customer ON kyc_records(customer_id);
CREATE INDEX IF NOT EXISTS idx_kyc_status ON kyc_records(status);
