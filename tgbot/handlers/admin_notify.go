package handlers

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"

	tele "gopkg.in/telebot.v3"
)

// AbaBot is the secondary ABA BANK bot instance, set by main.go after
// initialization. Used by the main bot's /notify command to send transaction
// alerts through the ABA-branded channel.
var AbaBot *tele.Bot

// RegisterAdminNotifyCommands registers administrator-only notification
// commands on the main Wing Bank bot.
//
//   - /notify <customer_id>  — look up latest completed transfer and send
//     via ABA Bot.
//   - /sendto <customer_id> <text> — send an arbitrary message via ABA Bot.
func RegisterAdminNotifyCommands(b *tele.Bot) {
	b.Handle("/notify", handleAdminNotify)
	b.Handle("/sendto", handleAdminSendTo)
}

// SendToCustomer sends a text message to a customer using the given bot.
func SendToCustomer(b *tele.Bot, chatID int64, text string) error {
	if b == nil {
		return fmt.Errorf("bot is nil")
	}
	_, err := b.Send(&tele.User{ID: chatID}, text)
	return err
}

// handleAdminSendTo implements /sendto <telegram_id> <message...>.
//
// The message may contain spaces and newlines; everything after the ID is
// sent verbatim. Delivery goes through AbaBot when available, otherwise the
// main bot.
func handleAdminSendTo(c tele.Context) error {
	sender := c.Sender()
	if sender == nil {
		return c.Send("Error: cannot identify sender.")
	}
	if !isAdmin(sender.ID) {
		return c.Send("⛔ Permission denied. This command is for administrators only.")
	}

	raw := ""
	if c.Message() != nil {
		raw = c.Message().Text
	}
	// Split into at most 2 parts: command + ID, then the rest as message.
	parts := strings.SplitN(raw, " ", 3)
	if len(parts) < 3 {
		return c.Send("Usage: /sendto <customer_telegram_id> <message>\n\nExample: /sendto 6089183885 Hello there")
	}

	id, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64)
	if err != nil {
		return c.Send("Invalid Telegram ID: " + parts[1])
	}

	text := strings.TrimSpace(parts[2])
	if text == "" {
		return c.Send("Message cannot be empty.")
	}

	bot := AbaBot
	if bot == nil {
		bot = c.Bot()
	}

	if err := SendToCustomer(bot, id, text); err != nil {
		return c.Send("Failed to send: " + err.Error())
	}

	botName := "aba-bank"
	if AbaBot == nil {
		botName = "wing-bank"
	}
	if Store != nil {
		if err := Store.InsertOutboundMessage(0, id, text, botName); err != nil {
			log.Printf("handleAdminSendTo: InsertOutboundMessage failed: %v", err)
		}
	}

	return c.Send(fmt.Sprintf("✅ Message sent to %d via %s", id, botName))
}

// handleAdminNotify implements /notify <telegram_id>.
//
// Flow:
//  1. Verify sender is an administrator (ADMIN_TELEGRAM_IDS).
//  2. Parse the target customer Telegram ID.
//  3. Look up the latest completed transaction where the customer is the
//     recipient (to_account_id -> accounts.customer_id).
//  4. Join accounts + customers to resolve sender/receiver names and
//     account numbers.
//  5. Format the ABA-style receipt and send it through AbaBot.
func handleAdminNotify(c tele.Context) error {
	sender := c.Sender()
	if sender == nil {
		return c.Send("Error: cannot identify sender.")
	}
	if !isAdmin(sender.ID) {
		return c.Send("⛔ Permission denied. This command is for administrators only.")
	}

	text := ""
	if c.Message() != nil {
		text = c.Message().Text
	}
	parts := strings.Fields(text)
	if len(parts) < 2 {
		return c.Send("Usage: /notify <customer_telegram_id>\n\nExample: /notify 6089183885")
	}

	targetID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		return c.Send("Invalid Telegram ID: " + parts[1])
	}

	tx, err := findLatestCompletedTransferForCustomer(targetID)
	if err != nil {
		return c.Send("Database error: " + err.Error())
	}
	if tx == nil {
		return c.Send(fmt.Sprintf("No completed transfer found for customer %d.", targetID))
	}

	msg := formatTransferNotification(tx)

	if AbaBot == nil {
		return c.Send("ABA Bot is not configured; cannot send notification.")
	}

	sent, sendErr := AbaBot.Send(&tele.User{ID: targetID}, msg)
	if sendErr != nil {
		return c.Send("Failed to send via ABA Bot: " + sendErr.Error())
	}

	// Log outbound message
	botName := os.Getenv("BOT_NAME")
	if botName == "" {
		botName = "aba-bank"
	}
	if Store != nil {
		if err := Store.InsertOutboundMessage(int64(sent.ID), targetID, msg, botName); err != nil {
			log.Printf("handleAdminNotify: InsertOutboundMessage failed: %v", err)
		}
	}

	return c.Send(fmt.Sprintf(
		"✅ Notification sent to customer %d\nAmount: %.2f %s\nFrom: %s (%s)\nVia: PAYWAY BY ABA",
		targetID, tx.Amount, tx.Currency, tx.FromName, tx.FromAccount,
	))
}

// transferDetail holds a joined transaction row with human-readable
// sender/receiver information.
type transferDetail struct {
	TxID        int64
	Amount      float64
	Currency    string
	Type        string
	Description string
	ReferenceID string
	CreatedAt   string
	FromAccount string
	FromName    string
	FromPhone   string
	ToAccount   string
	ToName      string
	ToPhone     string
}

// findLatestCompletedTransferForCustomer queries the transactions table
// joined with accounts + customers to resolve the most recent completed
// transfer where the given customer is the recipient.
func findLatestCompletedTransferForCustomer(customerID int64) (*transferDetail, error) {
	if Store == nil {
		return nil, fmt.Errorf("database not initialized")
	}

	query := `
		SELECT
			t.id, t.amount, t.currency, t.type, t.description, t.reference_id, t.created_at,
			fa.account_number, COALESCE(fc.first_name, 'Unknown'), COALESCE(fc.phone, ''),
			ta.account_number, COALESCE(tc.first_name, 'Unknown'), COALESCE(tc.phone, '')
		FROM transactions t
		JOIN accounts ta ON t.to_account_id = ta.id
		LEFT JOIN customers tc ON ta.customer_id = tc.telegram_id
		LEFT JOIN accounts fa ON t.from_account_id = fa.id
		LEFT JOIN customers fc ON fa.customer_id = fc.telegram_id
		WHERE tc.telegram_id = ? AND t.status = 'completed'
		ORDER BY t.id DESC
		LIMIT 1
	`

	var (
		txID        sql.NullInt64
		amount      sql.NullFloat64
		currency    sql.NullString
		txType      sql.NullString
		description sql.NullString
		refID       sql.NullString
		createdAt   sql.NullString
		fromAcc     sql.NullString
		fromName    sql.NullString
		fromPhone   sql.NullString
		toAcc       sql.NullString
		toName      sql.NullString
		toPhone     sql.NullString
	)

	err := Store.QueryRow(query, customerID).Scan(
		&txID, &amount, &currency, &txType, &description, &refID, &createdAt,
		&fromAcc, &fromName, &fromPhone,
		&toAcc, &toName, &toPhone,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	return &transferDetail{
		TxID:        txID.Int64,
		Amount:      amount.Float64,
		Currency:    currency.String,
		Type:        txType.String,
		Description: description.String,
		ReferenceID: refID.String,
		CreatedAt:   createdAt.String,
		FromAccount: fromAcc.String,
		FromName:    fromName.String,
		FromPhone:   fromPhone.String,
		ToAccount:   toAcc.String,
		ToName:      toName.String,
		ToPhone:     toPhone.String,
	}, nil
}

// formatTransferNotification renders an ABA-style transaction receipt.
func formatTransferNotification(tx *transferDetail) string {
	dateStr := tx.CreatedAt
	if t, err := time.Parse(time.RFC3339, tx.CreatedAt); err == nil {
		dateStr = t.Format("2006-01-02 03:04:05 PM")
	}

	desc := tx.Description
	if desc == "" {
		desc = "Channel: ABA bank"
		if tx.ReferenceID != "" {
			desc += " | Hash: " + tx.ReferenceID
		}
	}

	return fmt.Sprintf(
		"✅ Transaction Successful\n\n"+
			"Type: %s\n"+
			"Amount: %.2f %s\n"+
			"From: %s\n"+
			"To: %s — %s\n"+
			"Description: %s\n"+
			"Date: %s\n\n"+
			"Thank you for banking with ABA.",
		titleCase(tx.Type),
		tx.Amount, tx.Currency,
		tx.FromAccount,
		tx.ToName, tx.ToAccount,
		desc,
		dateStr,
	)
}

func titleCase(s string) string {
	if s == "" {
		return "Transfer"
	}
	return strings.ToUpper(s[:1]) + s[1:]
}
