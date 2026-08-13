package handlers

import (
	"fmt"
	"os"
	"strings"
	"time"
	"log"

	tele "gopkg.in/telebot.v3"
)

// RegisterCommands registers all command handlers on the bot.
func RegisterCommands(b *tele.Bot) {
	b.Handle("/start", handleStart)
	b.Handle("/help", handleHelp)
	b.Handle("/ping", handlePing)
}

// handleStart sends a Khmer welcome message with the main menu.
// It also supports deep-link tokens: when the user opens the bot via
// t.me/<bot>?start=<token> the token is claimed and any pending
// notification payload is delivered to the user. After processing the
// token the normal main menu is shown.
func handleStart(c tele.Context) error {
	user := c.Sender()
	if user == nil {
		return fmt.Errorf("handleStart: missing sender")
	}
	clearState(user.ID)

	// Parse possible token from the message text. Telegram may deliver
	// "/start <token>" as the message text, so split on whitespace.
	text := ""
	if c.Message() != nil {
		text = c.Message().Text
	}
	parts := strings.Fields(text)
	if len(parts) >= 2 {
		token := parts[1]
		// Claim the pending registration if it exists.
		if Store != nil {
			msgPayload, err := Store.ClaimPendingRegistration(token, user.ID, user.Username, user.FirstName, user.LastName)
			if err == nil {
				// Notify the user of successful binding (Khmer friendly text).
				if _, sendErr := c.Bot().Send(user, "✅ ការភ្ជាប់គណនីបានសម្រេចរួច។ ឥឡូវ​អ្នក​នឹងទទួលព័ត៌មាន​អំពី​ការទូទាត់។"); sendErr != nil {
					log.Printf("handleStart: send confirm failed: %v", sendErr)
				}

				// If the pending entry included a message to deliver, send it now
				if msgPayload != "" {
					sent, sendErr := c.Bot().Send(user, msgPayload)
					if sendErr != nil {
						log.Printf("handleStart: failed to send pending payload to %d: %v", user.ID, sendErr)
					} else {
						// Log outbound message into shared DB.
						botName := os.Getenv("BOT_NAME")
						if botName == "" {
							botName = "wing-bank"
						}
						if Store != nil {
							if err := Store.InsertOutboundMessage(int64(sent.ID), user.ID, msgPayload, botName); err != nil {
								log.Printf("handleStart: InsertOutboundMessage failed: %v", err)
							}
						}
					}
				}
				return sendMainMenu(c)
			}
			// If claim failed, fall through and show the normal menu but inform user.
			log.Printf("handleStart: claim token %s failed for user %d: %v", token, user.ID, err)
			// Inform user the token was invalid/expired (bilingual to be safe).
			if _, sendErr := c.Bot().Send(user, "⚠️ Token invalid or expired. ឬ token មិនត្រឹមត្រូវ ឬ បានផុយម៉ោង។"); sendErr != nil {
				log.Printf("handleStart: send token-invalid failed: %v", sendErr)
			}
		}
	}

	// No token path: just show main menu as before.
	return sendMainMenu(c)
}

// handleHelp lists all available services in Khmer.
func handleHelp(c tele.Context) error {
	return c.Send(
		"📋 *សេវារបស់ Wing Bank*\n\n"+
			"/start \\- ចាប់ផ្តើម និងមើលម៉ឺនុយ\n"+
			"/help \\- បង្ហាញសារជំនួយនេះ\n\n"+
			"🏦 សេវាដែលមាន:\n"+
			"• ព័ត៌មានគណនី\n"+
			"• ព័ត៌មានកម្ចី\n"+
			"• អត្រាប្តូរប្រាក់\n"+
			"• ទីតាំងសាខា និង ATM\n"+
			"• ព័ត៌មានទំនាក់ទំនង\n"+
			"• ព័ត៌មានអំពីធនាគារ\n"+
			"• ការសន្ទនាជាមួយក្រុមការងារដោយផ្ទាល់\n"+
			"• BAkong ឆែកពីការផ្ទេរប្រាក់ចេញចូល\n\n"+
			"ចុច /start ដើម្បីចាប់ផ្តើម!",
		tele.ModeMarkdownV2,
	)
}

// handlePing responds with latency for health checking.
func handlePing(c tele.Context) error {
	start := time.Now()
	msg, err := c.Bot().Send(c.Recipient(), "🏓 Pong!")
	if err != nil {
		return err
	}
	latency := time.Since(start)
	_, err = c.Bot().Edit(msg, fmt.Sprintf("🏓 Pong!\nLatency: %v", latency.Round(time.Millisecond)))
	return err
}
