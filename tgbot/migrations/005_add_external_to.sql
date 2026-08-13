-- 005: support external (out-of-system) beneficiaries on transactions
ALTER TABLE transactions ADD COLUMN external_to TEXT;