package db

import (
	"database/sql"
	"fmt"
	"time"
)

// Message is a row from the messages table.
type Message struct {
	ID                int64
	TelegramMessageID sql.NullInt64
	CustomerID        int64 // Telegram user ID (matches customers.telegram_id)
	Direction         string
	ContentType       string
	Content           sql.NullString
	Source            string
	ReadAt            sql.NullTime
	RepliedBy         sql.NullString
	BotName           string
	CreatedAt         time.Time
}

// InsertMessage appends a message to the shared DB.
//
// direction must be "in" (user -> bot) or "out" (bot/admin -> user).
// source must be "bot" (sent by tgbot) or "admin" (sent by admin panel).
// contentType is typically "text" but may be "photo", "document" or "callback".
// botName identifies which bot instance carried the message (e.g.
// "wing-bank" or "aba-bank") so the admin panel can route replies.
func (d *DB) InsertMessage(telegramMsgID int64, customerID int64, direction, contentType, content, source, botName string) error {
	const q = `
INSERT INTO messages (telegram_message_id, customer_id, direction, content_type, content, source, bot_name)
VALUES (?, ?, ?, ?, ?, ?, ?)`
	_, err := d.Exec(q,
		nullInt64(telegramMsgID),
		customerID,
		direction,
		contentType,
		nullStr(content),
		source,
		botName,
	)
	if err != nil {
		return fmt.Errorf("InsertMessage(customer=%d dir=%s): %w", customerID, direction, err)
	}
	return nil
}

// InsertInboundMessage is a convenience wrapper for logging an incoming
// (user -> bot) text message with source='bot'.
func (d *DB) InsertInboundMessage(telegramMsgID, customerID int64, content, botName string) error {
	return d.InsertMessage(telegramMsgID, customerID, "in", "text", content, "bot", botName)
}

// InsertOutboundMessage logs a bot-generated reply.
func (d *DB) InsertOutboundMessage(telegramMsgID, customerID int64, content, botName string) error {
	return d.InsertMessage(telegramMsgID, customerID, "out", "text", content, "bot", botName)
}

// InsertAdminReply logs an operator reply sent from the admin panel.
func (d *DB) InsertAdminReply(telegramMsgID, customerID int64, content, repliedBy, botName string) error {
	const q = `
INSERT INTO messages (telegram_message_id, customer_id, direction, content_type, content, source, replied_by, bot_name)
VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)`
	_, err := d.Exec(q, nullInt64(telegramMsgID), customerID, nullStr(content), nullStr(repliedBy), botName)
	if err != nil {
		return fmt.Errorf("InsertAdminReply(customer=%d): %w", customerID, err)
	}
	return nil
}

func nullInt64(n int64) sql.NullInt64 {
	if n == 0 {
		return sql.NullInt64{}
	}
	return sql.NullInt64{Int64: n, Valid: true}
}

// HasAdminOrAgentReplySince checks whether there are any outbound messages
// (either sent by the bot as 'out' or by an admin with source='admin') for
// the given customer after the provided time. Returns true if such a message
// exists.
func (d *DB) HasAdminOrAgentReplySince(customerID int64, since time.Time) (bool, error) {
	const q = `
SELECT 1 FROM messages
WHERE customer_id = ?
  AND ((source = 'admin') OR (direction = 'out' AND source = 'bot'))
  AND created_at > ?
LIMIT 1
`
	row := d.QueryRow(q, customerID, since)
	var v int
	if err := row.Scan(&v); err == sql.ErrNoRows {
		return false, nil
	} else if err != nil {
		return false, fmt.Errorf("HasAdminOrAgentReplySince(%d): %w", customerID, err)
	}
	return true, nil
}
