-- 007: notification groups for ABA bot
CREATE TABLE IF NOT EXISTS notification_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_name TEXT NOT NULL DEFAULT 'aba-bank',
    chat_id INTEGER NOT NULL UNIQUE,
    chat_title TEXT NOT NULL DEFAULT '',
    invite_link TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
