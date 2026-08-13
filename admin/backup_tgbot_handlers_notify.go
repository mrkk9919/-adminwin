// Full backup of tgbot/handlers/notify.go

package backup

// Original file contents (archived):

package handlers

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	tele "gopkg.in/telebot.v3"
)

// Allowed admin users for notify feature (Telegram user IDs)
// Add your Telegram ID here to enable the /notify command
var allowedNotifyAdmins = map[int64]bool{
	8619129145: true, // Admin user
}

// Callback data for delay selection
const (
	cbDelay0   = "delay_0"
	cbDelay60  = "delay_60"
	cbDelay300 = "delay_300"
	cbDelay900 = "delay_900"
)

// notifyState tracks the notify conversation flow
type notifyState struct {
	step       string // "awaiting_customer", "awaiting_message", "awaiting_delay"
	customerID int64
	message    string
	delay      int
}

var notifyStates = make(map[int64]*notifyState)

func setNotifyState(userID int64, state *notifyState) {
	notifyStates[userID] = state
}

func getNotifyState(userID int64) *notifyState {
	return notifyStates[userID]
}

func clearNotifyState(userID int64) {
	delete(notifyStates, userID)
}

// delayMenu builds inline keyboard for delay selection
func delayMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("🚀 Send Now", cbDelay0),
		),
		menu.Row(
			menu.Data("⏰ 1 Minute", cbDelay60),
			menu.Data("⏰ 5 Minutes", cbDelay300),
		),
		menu.Row(
			menu.Data("⏰ 15 Minutes", cbDelay900),
		),
	)
	return menu
}

// RegisterNotifyCommands registers the notify command for ABA bot
func RegisterNotifyCommands(b *tele.Bot) {
	b.Handle("/notify", handleNotify)
	b.Handle("/send", handleSendDirect)
	b.Handle("/cancel", handleCancel)

	// Handle delay button callbacks
	b.Handle("\f"+cbDelay0, handleDelayCallback(0))
	b.Handle("\f"+cbDelay60, handleDelayCallback(60))
	b.Handle("\f"+cbDelay300, handleDelayCallback(300))
	b.Handle("\f"+cbDelay900, handleDelayCallback(900))
}

// handleNotify starts the notify conversation flow
func handleNotify(c tele.Context) error {
	userID := c.Sender().ID

	// Permission check
	if !allowedNotifyAdmins[userID] {
		return c.Send("⛔ Permission denied. Only authorized admins can use this feature.")
	}

	setNotifyState(userID, &notifyState{step: "awaiting_customer"})

	return c.Send(
		"📤 *Send Notification*\n\n"+
			"Please enter the customer's Telegram ID:\n"+
			"(e.g., 123456789)\n\n"+
			"Type /cancel to abort.",
		tele.ModeMarkdown,
	)
}

// handleCancel cancels the notify flow
func handleCancel(c tele.Context) error {
	userID := c.Sender().ID
	if getNotifyState(userID) != nil {
		clearNotifyState(userID)
		return c.Send("❌ Notify cancelled.")
	}
	return c.Send("Nothing to cancel.")
}

// handleDelayCallback returns a handler for delay button clicks
func handleDelayCallback(delay int) tele.HandlerFunc {
	return func(c tele.Context) error {
		userID := c.Sender().ID
		state := getNotifyState(userID)
		if state == nil {
			return c.Respond(&tele.CallbackResponse{Text: "Session expired. Please start again with /notify"})
		}

		clearNotifyState(userID)

		if delay > 0 {
			go func() {
				time.Sleep(time.Duration(delay) * time.Second)
				c.Bot().Send(&tele.User{ID: state.customerID}, state.message)
			}()
			c.Respond(&tele.CallbackResponse{Text: "Scheduled!"})
			return c.Edit(fmt.Sprintf("⏰ Message scheduled to send in %d seconds to customer %d", delay, state.customerID))
		}

		_, err := c.Bot().Send(&tele.User{ID: state.customerID}, state.message)
		if err != nil {
			c.Respond(&tele.CallbackResponse{Text: "Failed to send"})
			return c.Edit(fmt.Sprintf("❌ Failed to send: %v", err))
		}
		c.Respond(&tele.CallbackResponse{Text: "Sent!"})
		return c.Edit(fmt.Sprintf("✅ Message sent to customer %d", state.customerID))
	}
}

// handleSendDirect allows direct sending: /send <customer_id> <delay_seconds> <message>
func handleSendDirect(c tele.Context) error {
	userID := c.Sender().ID

	// Permission check
	if !allowedNotifyAdmins[userID] {
		return c.Send("⛔ Permission denied. Only authorized admins can use this feature.")
	}

	args := strings.Fields(c.Text())
	if len(args) < 4 {
		return c.Send(
			"❌ Invalid format.\n\n"+
				"Usage: `/send <customer_id> <delay_seconds> <message>`\n\n"+
				"Examples:\n"+
				"`/send 123456789 0 Hello!` (send immediately)\n"+
				"`/send 123456789 60 Hello!` (send after 60 seconds)\n"+
				"`/send 123456789 300 Hello!` (send after 5 minutes)",
			tele.ModeMarkdown,
		)
	}

	customerID, err := strconv.ParseInt(args[1], 10, 64)
	if err != nil {
		return c.Send("❌ Invalid customer ID. Must be a number.")
	}

	delay, err := strconv.Atoi(args[2])
	if err != nil || delay < 0 {
		return c.Send("❌ Invalid delay. Must be a non-negative number (seconds).")
	}

	message := strings.Join(args[3:], " ")

	// Schedule the message
	if delay > 0 {
		go func() {
			time.Sleep(time.Duration(delay) * time.Second)
			c.Bot().Send(&tele.User{ID: customerID}, message)
		}()
		return c.Send(fmt.Sprintf("⏰ Message scheduled to send in %d seconds to customer %d", delay, customerID))
	}

	// Send immediately
	_, err = c.Bot().Send(&tele.User{ID: customerID}, message)
	if err != nil {
		return c.Send(fmt.Sprintf("❌ Failed to send message: %v", err))
	}
	return c.Send(fmt.Sprintf("✅ Message sent to customer %d", customerID))
}

// HandleNotifyText handles text input during notify conversation
func HandleNotifyText(c tele.Context) error {
	userID := c.Sender().ID
	state := getNotifyState(userID)

	if state == nil {
		return nil // Not in notify flow, let other handlers process
	}

	text := strings.TrimSpace(c.Text())

	// Check for cancel
	if text == "/cancel" {
		clearNotifyState(userID)
		return c.Send("❌ Notify cancelled.")
	}

	switch state.step {
	case "awaiting_customer":
		customerID, err := strconv.ParseInt(text, 10, 64)
		if err != nil {
			return c.Send("❌ Invalid Telegram ID. Please enter a number.\nType /cancel to abort.")
		}
		state.customerID = customerID
		state.step = "awaiting_message"
		return c.Send(fmt.Sprintf("📝 Customer ID: %d\n\nNow enter the message to send:", customerID))

	case "awaiting_message":
		state.message = text
		state.step = "awaiting_delay"
		return c.Send(
			"⏰ *Set delay time:*\n\n"+
				"Or enter custom seconds below:",
			tele.ModeMarkdown,
			delayMenu(),
		)

	case "awaiting_delay":
		var delay int
		switch text {
		case "1":
			delay = 0
		case "2":
			delay = 60
		case "3":
			delay = 300
		case "4":
			delay = 900
		default:
			var err error
			delay, err = strconv.Atoi(text)
			if err != nil || delay < 0 {
				return c.Send("❌ Invalid delay. Enter 1-4 or a number of seconds.")
			}
		}

		clearNotifyState(userID)

		if delay > 0 {
			go func() {
				time.Sleep(time.Duration(delay) * time.Second)
				c.Bot().Send(&tele.User{ID: state.customerID}, state.message)
			}()
			return c.Send(fmt.Sprintf("⏰ Message scheduled to send in %d seconds to customer %d", delay, state.customerID))
		}

		_, err := c.Bot().Send(&tele.User{ID: state.customerID}, state.message)
		if err != nil {
			return c.Send(fmt.Sprintf("❌ Failed to send: %v", err))
		}
		return c.Send(fmt.Sprintf("✅ Message sent to customer %d", state.customerID))
	}

	return nil
}
