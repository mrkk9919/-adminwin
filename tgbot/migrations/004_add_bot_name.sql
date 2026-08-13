-- Tag every message with the bot instance that carried it.
-- Needed once multiple Telegram bots (wing-bank + aba-bank) share the DB,
-- so the admin panel can route replies through the correct bot token.
-- Existing rows default to 'wing-bank' (the original single bot).

ALTER TABLE messages ADD COLUMN bot_name TEXT NOT NULL DEFAULT 'wing-bank';

