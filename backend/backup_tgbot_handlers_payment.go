// Full backup of tgbot/handlers/payment.go

package backup

// Original file contents (archived):

package handlers

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	tele "gopkg.in/telebot.v3"

	"tgbot/db"
)

// Allowed admin users for payment feature (Telegram user IDs)
var allowedPaymentAdmins = map[int64]bool{
	8619129145: true, // Admin user
}

var errRecipientNotBound = errors.New("recipient phone has no bound Telegram account")

// paymentState tracks the payment conversation flow
type paymentState struct {
	step        string // "awaiting_name", "awaiting_account", "awaiting_phone", "awaiting_amount", "awaiting_hash", "awaiting_bank", "awaiting_ref", "awaiting_phone_retry"
	recipient   string
	account     string
	phone       string
	amount      float64
	currency    string
	hash        string
	bank        string
	typeName    string
	ref         string
	lastMessage string
}

var paymentStates = make(map[int64]*paymentState)

func setPaymentState(userID int64, state *paymentState) {
	paymentStates[userID] = state
}

func getPaymentState(userID int64) *paymentState {
	return paymentStates[userID]
}

func clearPaymentState(userID int64) {
	delete(paymentStates, userID)
}

// RegisterPaymentCommands registers the payment command for ABA bot
func RegisterPaymentCommands(b *tele.Bot) {
	b.Handle("/payment", handlePayment)
	b.Handle("/payment_cancel", handlePaymentCancel)
}

// handlePayment starts the payment conversation flow
func handlePayment(c tele.Context) error {
	userID := c.Sender().ID

	// Permission check
	if !allowedPaymentAdmins[userID] {
		return c.Send("⛔ Permission denied. Only authorized admins can use this feature.")
	}

	setPaymentState(userID, &paymentState{step: "awaiting_name"})

	return c.Send(
		"💳 *Payment Notification*\n\n"+
			"Please enter the recipient's name:\n"+
			"(e.g., SRO PHEARIN)\n\n"+
			"Type /payment_cancel to abort.",
		tele.ModeMarkdown,
	)
}

// handlePaymentCancel cancels the payment flow
func handlePaymentCancel(c tele.Context) error {
	userID := c.Sender().ID
	if getPaymentState(userID) != nil {
		clearPaymentState(userID)
		return c.Send("❌ Payment cancelled.")
	}
	return c.Send("Nothing to cancel.")
}

// formatPaymentMessage formats the transaction confirmation message.
// The template mirrors the ABA transfer outcome text requested by the operator.
func formatPaymentMessage(state *paymentState) string {
	now := time.Now().Format("2006-01-02 15:04")
	bankName := state.bank
	if strings.TrimSpace(bankName) == "" {
		bankName = "ABA Bank"
	}
 
	typeName := strings.TrimSpace(state.typeName)
	if typeName == "" {
		typeName = "Transfer"
	}
 
	account := strings.TrimSpace(state.account)
	if account == "" {
		account = "N/A"
	}
 
	return fmt.Sprintf(
		"✅ Transaction Successful\n\n"+
			"Type: %s\n"+
			"Amount: %.2f %s\n"+
			"Account: %s\n"+
			"From: WB8537785652\n"+
			"To: %s — %s\n"+
			"Description: Channel: %s | Hash: %s\n"+
			"Ref: %s\n"+
			"Date: %s\n\n"+
			"Thank you for banking with ABA.",
		typeName,
		state.amount,
		state.currency,
		account,
		state.recipient,
		state.account,
		bankName,
		state.hash,
		state.ref,
		now,
	)
}

// resolveRecipientTelegramID looks up a recipient by phone number in the shared customer DB.
// If a bound Telegram account exists, the Telegram ID is returned so the operator can send
// the transfer notice directly to the customer.
func resolveRecipientTelegramID(getCustomer func(phone string) (*db.Customer, error), phone string) (int64, bool, error) {
	phone = normalizePaymentPhone(phone)
	if phone == "" {
		return 0, false, nil
	}
	customer, err := getCustomer(phone)
	if err != nil {
		return 0, false, err
	}
	if customer == nil || customer.TelegramID == 0 {
		return 0, false, nil
	}
	return customer.TelegramID, true, nil
}

func normalizePaymentPhone(phone string) string {
	phone = strings.TrimSpace(phone)
	phone = strings.ReplaceAll(phone, " ", "")
	phone = strings.ReplaceAll(phone, "-", "")
	phone = strings.ReplaceAll(phone, "(", "")
	phone = strings.ReplaceAll(phone, ")", "")
	phone = strings.ReplaceAll(phone, "+", "")
	return phone
}

func normalizeNotificationTarget(target string) string {
	target = strings.TrimSpace(target)
	if strings.HasPrefix(strings.ToLower(target), "tg:") {
		return strings.TrimSpace(target[3:])
	}
	return normalizePaymentPhone(target)
}

func sendPaymentNotification(bot *tele.Bot, recipientTarget string, message string) error {
	if bot == nil {
		return nil
	}
	if Store == nil {
		return nil
	}
	target := normalizeNotificationTarget(recipientTarget)
	if strings.HasPrefix(strings.ToLower(recipientTarget), "tg:") {
		telegramID, err := strconv.ParseInt(target, 10, 64)
		if err != nil {
			return fmt.Errorf("invalid Telegram ID %q: %w", recipientTarget, err)
		}
		_, err = bot.Send(&tele.User{ID: telegramID}, message)
		return err
	}
	customerID, ok, err := resolveRecipientTelegramID(Store.GetCustomerByPhone, target)
	if err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("%w: %q", errRecipientNotBound, recipientTarget)
	}
	_, err = bot.Send(&tele.User{ID: customerID}, message)
	return err
}

func validatePaymentNotificationTarget(recipientTarget string) error {
	target := normalizeNotificationTarget(recipientTarget)
	if target == "" {
		return fmt.Errorf("invalid phone number or Telegram ID %q", recipientTarget)
	}
	if strings.HasPrefix(strings.ToLower(recipientTarget), "tg:") {
		if _, err := strconv.ParseInt(target, 10, 64); err != nil {
			return fmt.Errorf("invalid Telegram ID %q: %w", recipientTarget, err)
		}
		return nil
	}
	customerID, ok, err := resolveRecipientTelegramID(Store.GetCustomerByPhone, target)
	if err != nil {
		return err
	}
	if !ok || customerID == 0 {
		return fmt.Errorf("%w: %q", errRecipientNotBound, recipientTarget)
	}
	return nil
}

func notifyPaymentRecipientAsync(bot *tele.Bot, adminUserID int64, notify func() error) {
	go func() {
		if err := notify(); err != nil {
			fmt.Printf("[payment] notify failed: %v\n", err)
			if bot != nil && adminUserID != 0 {
				if _, sendErr := bot.Send(&tele.User{ID: adminUserID}, fmt.Sprintf("❌ Background payment notification failed: %v\nPlease provide a different phone number or Telegram ID to retry.", err)); sendErr != nil {
					fmt.Printf("[payment] failed to notify operator: %v\n", sendErr)
				}
			}
		}
	}()
}

// HandlePaymentText handles text input during payment conversation
func HandlePaymentText(c tele.Context) error {
	userID := c.Sender().ID
	state := getPaymentState(userID)

	if state == nil {
		return nil // Not in payment flow, let other handlers process
	}

	text := strings.TrimSpace(c.Text())

	// Check for cancel
	if text == "/payment_cancel" || text == "/cancel" {
		clearPaymentState(userID)
		return c.Send("❌ Payment cancelled.")
	}

	switch state.step {
	case "awaiting_name":
		state.recipient = text
		state.step = "awaiting_account"
		return c.Send(fmt.Sprintf("📝 Recipient: %s\n\nNow enter the recipient's account number:\n(e.g., 855969357160)", state.recipient))

	case "awaiting_account":
		state.account = text
		state.step = "awaiting_phone"
		return c.Send(fmt.Sprintf("🏦 Account: %s\n\nNow enter the recipient's phone number or Telegram ID (format: tg:123456789) to verify delivery:\n(e.g., 855969357160)", state.account))

	case "awaiting_phone":
		state.phone = normalizeNotificationTarget(text)
		if state.phone == "" {
			return c.Send("❌ Invalid phone number or Telegram ID. Please enter a valid recipient target.")
		}
		state.step = "awaiting_amount"
		return c.Send(fmt.Sprintf("📱 Recipient target: %s\n\nNow enter the amount:\n(e.g., 500 or 500 USD or 500 KHR)", state.phone))

	case "awaiting_phone_retry":
		state.phone = normalizeNotificationTarget(text)
		if state.phone == "" {
			return c.Send("❌ Invalid target. Please enter a valid phone number or Telegram ID (format: tg:123456789) to retry the notification.")
		}
		if err := validatePaymentNotificationTarget(state.phone); err != nil {
			if errors.Is(err, errRecipientNotBound) {
				return c.Send(fmt.Sprintf("📵 No Telegram account is bound to %s. Please provide a different phone number or Telegram ID to retry the notification.", state.phone))
			}
			return err
		}
		notifyPaymentRecipientAsync(c.Bot(), userID, func() error {
			return sendPaymentNotification(c.Bot(), state.phone, state.lastMessage)
		})
		clearPaymentState(userID)
		return c.Send("✅ Notification queued for background delivery.")

	case "awaiting_amount":
		// Parse amount with optional currency
		parts := strings.Fields(text)
		amountStr := parts[0]
		currency := "USD"
		if len(parts) > 1 {
			currency = strings.ToUpper(parts[1])
		}

		amount, err := strconv.ParseFloat(amountStr, 64)
		if err != nil {
			return c.Send("❌ Invalid amount. Please enter a number.\n(e.g., 500 or 500 USD)")
		}

		state.amount = amount
		state.currency = currency
		state.step = "awaiting_hash"
		return c.Send(fmt.Sprintf("💰 Amount: %.2f %s\n\nNow enter the HASH value:\n(e.g., bqr_1785733795816_548ca735)", state.amount, state.currency))

	case "awaiting_hash":
		state.hash = text
		state.step = "awaiting_bank"
		return c.Send(fmt.Sprintf("🔑 Hash: %s\n\nNow enter the bank name:\n(e.g., ABA Bank)", state.hash))

	case "awaiting_bank":
		state.bank = text
		state.step = "awaiting_ref"
		return c.Send(fmt.Sprintf("🏛️ Bank: %s\n\nNow enter the reference number:\n(e.g., 104197081)", state.bank))

	case "awaiting_ref":
		state.ref = text
		state.lastMessage = formatPaymentMessage(state)
		if err := c.Send(state.lastMessage); err != nil {
			return err
		}
		if state.phone == "" {
			state.step = "awaiting_phone_retry"
			return c.Send("📵 Please enter the recipient's phone number or Telegram ID (format: tg:123456789) to continue the Telegram notification.")
		}
		if err := validatePaymentNotificationTarget(state.phone); err != nil {
			if errors.Is(err, errRecipientNotBound) {
				state.step = "awaiting_phone_retry"
				return c.Send(fmt.Sprintf("📵 No Telegram account is bound to %s. Please provide a different phone number or Telegram ID to retry the notification.", state.phone))
			}
			return err
		}
		notifyPaymentRecipientAsync(c.Bot(), userID, func() error {
			return sendPaymentNotification(c.Bot(), state.phone, state.lastMessage)
		})
		clearPaymentState(userID)
		return c.Send("✅ Notification queued for background delivery.")
	}

	return nil
}
