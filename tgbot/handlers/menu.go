package handlers

import (
	"log"
	"strings"

	tele "gopkg.in/telebot.v3"
)

// Callback unique identifiers for inline keyboard buttons.
const (
	cbAccount          = "menu_account"
	cbLoan             = "menu_loan"
	cbExchange         = "menu_exchange"
	cbBranch           = "menu_branch"
	cbContact          = "menu_contact"
	cbAbout            = "menu_about"
	cbBack             = "menu_back"
	cbVerify           = "menu_verify"
	cbLiveChat         = "menu_livechat"
	cbDirectChat       = "menu_directchat"
	cbBakong           = "menu_bakong"
	cbBakongApply      = "menu_bakong_apply"
	cbBakongTransfer   = "menu_bakong_transfer"
	cbBakongHash       = "menu_bakong_hash"
	cbChannelSMS       = "menu_channel_sms"
	cbChannelTG        = "menu_channel_tg"
	cbChannelSatellite = "menu_channel_satellite"
	cbNotifAccount     = "menu_notif_account"
	cbNotifBank        = "menu_notif_bank"
	cbNotifPhone       = "menu_notif_phone"
	cbNotifName        = "menu_notif_name"
	cbResendOTP        = "menu_resend_otp"
	cbBakongSearch     = "menu_bakong_search"
	cbBakongKHQR       = "menu_bakong_khqr"
	cbBakongScan       = "menu_bakong_scan"
	cbLangKhmer        = "menu_lang_khmer"
	cbLangChinese      = "menu_lang_chinese"
	cbLangEnglish      = "menu_lang_english"
	cbDirectChatBack   = "menu_directchat_back"
)

// RegisterMenuHandlers registers all inline keyboard callback handlers on the bot.
// Each handler is wrapped with a diagnostic logger that prints the callback data
// and the matched handler name, so we can see exactly which button clicks fire
// (and especially: which do NOT fire, indicating a routing / registration bug).
func RegisterMenuHandlers(b *tele.Bot) {
	wrap := func(name string, h tele.HandlerFunc) tele.HandlerFunc {
		return func(c tele.Context) error {
			cb := c.Callback()
			data := ""
			if cb != nil {
				data = cb.Data
			}
			log.Printf("[CB-DIAG] handler=%s fired user=%d data=%q", name, c.Sender().ID, data)
			return h(c)
		}
	}
	b.Handle("\f"+cbAccount, wrap("handleAccountInfo", handleAccountInfo))
	b.Handle("\f"+cbLoan, wrap("handleLoanInfo", handleLoanInfo))
	b.Handle("\f"+cbExchange, wrap("handleExchangeRates", handleExchangeRates))
	b.Handle("\f"+cbBranch, wrap("handleBranches", handleBranches))
	b.Handle("\f"+cbContact, wrap("handleContact", handleContact))
	b.Handle("\f"+cbAbout, wrap("handleAbout", handleAbout))
	b.Handle("\f"+cbBack, wrap("handleBackToMenu", handleBackToMenu))
	b.Handle("\f"+cbVerify, wrap("handleVerifyAccount", handleVerifyAccount))
	b.Handle("\f"+cbLiveChat, wrap("handleLiveChat", handleLiveChat))
	b.Handle("\f"+cbDirectChat, wrap("handleDirectChat", handleDirectChat))
	b.Handle("\f"+cbBakong, wrap("handleBakong", handleBakong))
	b.Handle("\f"+cbBakongApply, wrap("handleBakongApply", handleBakongApply))
	b.Handle("\f"+cbBakongTransfer, wrap("handleBakongTransfer", handleBakongTransfer))
	b.Handle("\f"+cbBakongHash, wrap("handleBakongHash", handleBakongHash))
	b.Handle("\f"+cbChannelSMS, wrap("handleChannelSMS", handleChannelSMS))
	b.Handle("\f"+cbChannelTG, wrap("handleChannelTG", handleChannelTG))
	b.Handle("\f"+cbChannelSatellite, wrap("handleChannelSatellite", handleChannelSatellite))
	b.Handle("\f"+cbNotifAccount, wrap("handleNotifAccountBtn", handleNotifAccountBtn))
	b.Handle("\f"+cbNotifBank, wrap("handleNotifBankBtn", handleNotifBankBtn))
	b.Handle("\f"+cbNotifPhone, wrap("handleNotifPhoneBtn", handleNotifPhoneBtn))
	b.Handle("\f"+cbNotifName, wrap("handleNotifNameBtn", handleNotifNameBtn))
	b.Handle("\f"+cbResendOTP, wrap("handleResendOTP", handleResendOTP))
	b.Handle("\f"+cbBakongSearch, wrap("handleBakongSearch", handleBakongSearch))
	b.Handle("\f"+cbBakongKHQR, wrap("handleBakongKHQR", handleBakongKHQR))
	b.Handle("\f"+cbBakongScan, wrap("handleBakongScan", handleBakongScan))
	b.Handle("\f"+cbLangKhmer, wrap("handleLangKhmer", handleLangKhmer))
	b.Handle("\f"+cbLangChinese, wrap("handleLangChinese", handleLangChinese))
	b.Handle("\f"+cbLangEnglish, wrap("handleLangEnglish", handleLangEnglish))
	b.Handle("\f"+cbDirectChatBack, wrap("handleDirectChatBack", handleDirectChatBack))

	// Catch-all: log ANY callback that didn't match a specific handler above.
	// Useful for detecting typos in cbData, unregistered buttons, or callbacks
	// from stale messages whose handlers have been removed.
	b.Handle(tele.OnCallback, func(c tele.Context) error {
		cb := c.Callback()
		data := ""
		if cb != nil {
			data = cb.Data
		}
		log.Printf("[CB-DIAG] *** UNMATCHED CALLBACK *** user=%d data=%q", c.Sender().ID, data)
		return nil
	})
}

// mainMenu builds the inline keyboard for the main menu.
func mainMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("🏦 គណនី", cbAccount),
			menu.Data("💰 កមចី", cbLoan),
		),
		menu.Row(
			menu.Data("💱 អត្រាប្តូរប្រាក់", cbExchange),
			menu.Data("📍 សាខា និង ATM", cbBranch),
		),
		menu.Row(
			menu.Data("📞 ទំនាក់ទោង", cbContact),
			menu.Data("ℹ️ អំពីយើង", cbAbout),
		),
	)
	return menu
}

// backMenu builds a keyboard with a single "Back to Main Menu" button.
func backMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack)),
	)
	return menu
}

// sendMainMenu sends the welcome message with the main menu keyboard.
func sendMainMenu(c tele.Context) error {
	name := strings.TrimSpace(c.Sender().FirstName)
	if name == "" {
		name = "អ្នកប្រើ"
	}
	text := "សួរស្តី " + name + "!\n\n" +
		"Wing Bank សូមស្វាគមន៍អ្នកមកកាន់យើង\n" +
		"ខាងក្រោមនេះជាម៉ឺនុយសេវារបស់យើងដែលអ្នកអាចជ្រើសរើសបាន។"
	return c.Send(text, mainMenu())
}

// handleAccountInfo shows account type information.
func handleAccountInfo(c tele.Context) error {
	return sendAccountVerification(c)
}

// handleLoanInfo shows loan type information.
func handleLoanInfo(c tele.Context) error {
	text := "\U0001f4b0 *\u1794\u17d2\u179a\u1797\u17c1\u1791\u1780\u1798\u1785\u17b8*\n\n" +
		"\U0001f4cc \u1780\u1798\u1785\u17b8\u1795\u17d2\u1791\u17b6\u179b\u17cb\u1781\u17d2\u179b\u17bd\u1793\n" +
		"\u2022 \u1785\u17c6\u1793\u17bd\u1793\u1796\u17b8 $500 \u178a\u179b\u17cb $50,000\n" +
		"\u2022 \u179a\u1799\u17c8\u1796\u17c1\u179b 12 \u178a\u179b\u17cb 60 \u1781\u17c2\n" +
		"\u2022 \u17a2\u178f\u17d2\u179a\u17b6\u1780\u17b6\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1785\u17b6\u1794\u17cb\u1796\u17b8 1.2%/\u1781\u17c2\n\n" +
		"\U0001f4cc \u1780\u1798\u1785\u17b8\u1791\u17b7\u1789\u1795\u17d1\n" +
		"\u2022 \u1785\u17c6\u1793\u17bd\u1793\u179a\u17a0\u17bc\u178f\u178a\u179b\u17cb $200,000\n" +
		"\u2022 \u179a\u1799\u17c8\u1796\u17c1\u179b\u179a\u17a0\u17bc\u178f\u178a\u179b\u17cb 20 \u1786\u17d2\u1793\u17b6\u17c6\n" +
		"\u2022 \u17a2\u178f\u17d2\u179a\u17b6\u1780\u17b6\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1796\u17b7\u179f\u17c1\u179f\n\n" +
		"\U0001f4cc \u1780\u1798\u1785\u17b8\u17a2\u17b6\u1787\u17b8\u179c\u1780\u1798\u17d2\u1798\n" +
		"\u2022 \u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb SME \u1793\u17b7\u1784\u17a2\u17b6\u1787\u17b8\u179c\u1780\u1798\u17d2\u1798\u1792\u17c6\n" +
		"\u2022 \u179b\u1780\u17d2\u1781\u1781\u178e\u17d2\u178c\u1784\u17b6\u1799\u179f\u17d2\u179a\u17bd\u179b\n" +
		"\u2022 \u1796\u17b7\u1782\u17d2\u179a\u17c4\u17a0\u17cf\u1794\u179b\u17cb\u178a\u17c4\u1799\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\n\n" +
		"\U0001f4cc \u1780\u1798\u1785\u17b8\u1791\u17b7\u1789\u1799\u17b6\u1793\u1799\u1793\u17d2\u178f\n" +
		"\u2022 \u179a\u1790\u1799\u1793\u17d2\u178f\u1790\u17d2\u1798\u17b8 \u1793\u17b7\u1784\u1798\u17bd\u1799\u1791\u17b8\n" +
		"\u2022 \u1794\u1784\u17cb\u179a\u17c6\u179b\u179f\u17cb\u179a\u17a0\u17bc\u178f\u178a\u179b\u17cb 7 \u1786\u17d2\u1793\u17b6\u17c6"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleExchangeRates shows exchange rate information.
func handleExchangeRates(c tele.Context) error {
	text := "\U0001f4b1 *\u17a2\u178f\u17d2\u179a\u17b6\u1794\u17d2\u178f\u17bc\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb*\n" +
		"_\u0028\u17a2\u178f\u17d2\u179a\u17b6\u1782\u17c6\u179a\u17bc \u17a2\u17b6\u1785\u1794\u17d2\u179a\u17c2\u1794\u17d2\u179a\u17bd\u179b\u0029_" + "\n\n" +
		"\U0001f1fa\U0001f1f8 USD \u21c4 \U0001f1f0\U0001f1ed KHR\n" +
		"\u2022 \u1791\u17b7\u1789: 4,050 KHR\n" +
		"\u2022 \u179b\u1780\u17cb: 4,100 KHR\n\n" +
		"\U0001f1f9\U0001f1ed THB \u21c4 \U0001f1f0\U0001f1ed KHR\n" +
		"\u2022 \u1791\u17b7\u1789: 115 KHR\n" +
		"\u2022 \u179b\u1780\u17cb: 120 KHR\n\n" +
		"\U0001f1ea\U0001f1fa EUR \u21c4 \U0001f1fa\U0001f1f8 USD\n" +
		"\u2022 \u1791\u17b7\u1789: 1.05 USD\n" +
		"\u2022 \u179b\u1780\u17cb: 1.10 USD\n\n" +
		"\u26a0\ufe0f \u179f\u17bc\u1798\u1791\u17b6\u1780\u17cb\u1791\u17c4\u1784\u179f\u17b6\u1781\u17b6\u178a\u17be\u1798\u1794\u17b8\u178a\u17b9\u1784\u17a2\u178f\u17d2\u179a\u17b6\u1790\u17d2\u1798\u17b8\u1794\u17c6\u1795\u17bd\u178f\u17cf\u1794\u1784\u17cb\u1796\u17b8\u1791\u17b6\u17c6\u1784\u1793\u17c5\u1794\u17c6\u1795\u17bd\u178f\u17cb\u1794\u1793\u17d2\u1793\u17b6\u179b\u17b6\u179f\u17d2\u178f\u1794\u17c6\u1795\u17bd\u178f\u17cb\u1794\u1793\u17d2\u1793\u17b6\u179b\u17b6\u179f\u17d2\u178f"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleBranches shows branch and ATM location information.
func handleBranches(c tele.Context) error {
	text := "\U0001f4cd *\u179f\u17b6\u1781\u17b6 \u1793\u17b7\u1784 ATM*\n\n" +
		"\U0001f3e2 \u179f\u17b6\u1781\u17b6\u1797\u17d2\u1793\u17c6\u1796\u17c1\u1789\n" +
		"\u2022 \u1795\u17d2\u1791\u17c7\u179b\u17c1\u1781 123 \u1798\u17a0\u17b6\u179c\u17b7\u1790\u17b8 \u1798\u17c9\u17bc\u1793\u17b8\u179c\u1784\u17d2\u179f\n" +
		"\u2022 \u1798\u17c9\u17c4\u1784\u1792\u17d2\u179c\u17be\u1780\u17b6\u179a: 8:00 - 17:00 \u0028\u1785\u17d0\u1793\u17d2\u1791 - \u179f\u17bb\u1780\u17d2\u179a\u0029\n\n" +
		"\U0001f3e2 \u179f\u17b6\u1781\u17b6\u179f\u17c0\u1798\u179a\u17b6\u1794\n" +
		"\u2022 \u1795\u17d2\u1791\u17c7\u179b\u17c1\u1781 45 \u179c\u17b7\u1790\u17b8 \u179f\u17b7\u179c\u178f\u17d2\u1790\u17b6\n" +
		"\u2022 \u1798\u17c9\u17c4\u1784\u1792\u17d2\u179c\u17be\u1780\u17b6\u179a: 8:00 - 17:00 \u0028\u1785\u17d0\u1793\u17d2\u1791 - \u179f\u17bb\u1780\u17d2\u179a\u0029\n\n" +
		"\U0001f3e2 \u179f\u17b6\u1781\u17b6\u1794\u17b6\u178f\u17cb\u178a\u17c6\u1794\u1784\n" +
		"\u2022 \u1795\u17d2\u1791\u17c7\u179b\u17c1\u1781 78 \u179c\u17b7\u1790\u17b8 1\n" +
		"\u2022 \u1798\u17c9\u17c4\u1784\u1792\u17d2\u179c\u17be\u1780\u17b6\u179a: 8:00 - 17:00 \u0028\u1785\u17d0\u1793\u17d2\u1791 - \u179f\u17bb\u1780\u17d2\u179a\u0029\n\n" +
		"\U0001f3e7 \u1798\u17c9\u17b6\u179f\u17ca\u17b8\u1793 ATM\n" +
		"\u2022 \u1798\u17b6\u1793\u1793\u17c5\u1782\u17d2\u179a\u1794\u17cb\u179f\u17b6\u1781\u17b6\n" +
		"\u2022 \u1794\u17be\u1780\u179f\u17c1\u179c\u17b6 24 \u1798\u17c9\u17c4\u1784 7 \u1790\u17d2\u1784\u17c3"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleContact shows contact information.
func handleContact(c tele.Context) error {
	text := "\U0001f4de *\u1796\u17d0\u178f\u17cc\u1798\u17b6\u1793\u1791\u17c6\u1793\u17b6\u1780\u17cb\u1791\u17c4\u1784*\n\n" +
		"\U0001f4f1 \u1791\u17bc\u179a\u179f\u17d0\u1796\u17d2\u1791: 023 999 888\n" +
		"\U0001f4f1 Hotline: 1800 200 300 \u0028\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\u0029\n" +
		"\U0001f4e7 \u17a2\u17ca\u17b8\u1798\u17c2\u179b: support@wingbank.com\n" +
		"\U0001f310 \u1782\u17c1\u17a0\u1791\u17c6\u1796\u17d0\u179a: www.wingbank.com\n\n" +
		"\U0001f550 \u1798\u17c9\u17c4\u1784\u1792\u17d2\u179c\u17be\u1780\u17b6\u179a:\n" +
		"\u2022 \u1785\u17d0\u1793\u17d2\u1791 - \u179f\u17bb\u1780\u17d2\u179a: 8:00 - 17:00\n" +
		"\u2022 \u179f\u17c5\u179a\u17cd: 8:00 - 12:00\n" +
		"\u2022 \u17a2\u17b6\u1791\u17b7\u178f\u17d2\u1799: \u1794\u17b7\u1791\n\n" +
		"\U0001f4ac \u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb\u179f\u17c6\u178e\u17bc\u179a\u1794\u1793\u17d2\u1791\u17b6\u1793\u17cf \u179f\u17bc\u1798\u1791\u17bc\u179a\u179f\u17d0\u1796\u17d2\u1791\u1798\u1780 Hotline\u17d4"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleAbout shows information about the bank.
func handleAbout(c tele.Context) error {
	text := "\u2139\ufe0f *\u17a2\u17c6\u1796\u17b8 Wing Bank*\n\n" +
		"Wing Bank \u1787\u17b6\u1786\u1793\u17b6\u1782\u17b6\u179a\u1788\u17d2\u1793\u17b6\u17c6\u1798\u17bb\u1781\u1782\u17c1\u1793\u17c5\u1780\u1798\u17d2\u1796\u17bb\u1787\u17b6\n" +
		"\u178a\u17c2\u179b\u1795\u17d2\u178f\u179b\u17cb\u179f\u17c1\u179c\u17b6\u17a0\u17b7\u179a\u1789\u17d2\u1789\u179c\u178f\u17d2\u1790\u17ba\n" +
		"\u1794\u17d2\u179a\u1780\u1794\u178a\u17c4\u1799\u1791\u17c6\u1793\u17bb\u1780\u1785\u17b7\u178f\u17d2\u178f \u1793\u17b7\u1784\u179f\u17bb\u179c\u178f\u17d2\u1790\u17b7\u1797\u17b6\u1796\u17cb\u17d4\n\n" +
		"\U0001f3c6 \u179f\u1798\u17b7\u1791\u17d2\u1792\u1795\u179b:\n" +
		"\u2022 \u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\u1787\u17b6\u1784 500,000 \u1793\u17b6\u1780\u17cb\n" +
		"\u2022 \u179f\u17b6\u1781\u17b6\u1787\u17b6\u1784 30 \u1791\u17bc\u1791\u17b6\u17c6\u1784\u1794\u17d2\u179a\u1791\u17c1\u179f\u1793\u17c5\n" +
		"\u2022 \u179f\u17c1\u179c\u17b6\u1786\u1793\u17b6\u1782\u17b6\u179a\u178c\u17b8\u1787\u17b7\u1790\u179b 24/7\n\n" +
		"\U0001f512 \u179f\u17bb\u179c\u178f\u17d2\u1790\u17b7\u1797\u17b6\u1796\u17cb \u1793\u17b7\u1784\u1791\u17c6\u1793\u17bb\u1780\u1785\u17b7\u178f\u17d2\u178f:\n" +
		"\u2022 \u1791\u1791\u17bd\u179b\u179f\u17d2\u1782\u17b6\u179b\u17cb\u178a\u17c4\u1799\u1786\u1793\u17b6\u1782\u17b6\u179a\u1787\u17b6\u178f\u17b7\u1793\u17c5\u1794\u17d2\u179a\u1791\u17c1\u179f\u1793\u17c5\u1780\u1798\u17d2\u1796\u17bb\u1787\u17b6\n" +
		"\u2022 \u1794\u17d2\u179a\u1796\u17d0\u1793\u17d2\u1792\u179f\u17bb\u179c\u178f\u17d2\u1790\u17b7\u1797\u17b6\u1796\u17cb\u1780\u1798\u17d2\u179a\u17b7\u178f\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleBackToMenu edits the current message back to the main menu.
// It also clears any active conversation state so the user starts fresh.
func handleBackToMenu(c tele.Context) error {
	clearState(c.Sender().ID)
	text := "Wing Bank\n\n" +
		"ក្រុមជំនួយការសេវាអតិថជន រីករាយដែរបានផ្ញើរសារមកកាន់ពួកយើង\n" +
		"ខាងក្រោមបង្កាញពីបញ្ហាទូទៅអាចជ្រើសរើសតាមជ្រើសរើសសេវាកម្មដែលអ្នកត្រូវការ."
	return c.Edit(text, mainMenu())
}

// liveChatMenu builds a keyboard with "Online Customer Service" and "Back" buttons.
func liveChatMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\U0001f4ac \u179f\u17c1\u179c\u17b6\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7\u17a2\u17c9\u17c6\u1796\u17b8\u179a\u17c4\u1784", cbLiveChat),
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// handleLiveChat is called when the customer clicks "Online Customer Service".
func handleLiveChat(c tele.Context) error {
	clearState(c.Sender().ID)
	text := "\U0001f4ac *\u179f\u17c1\u179c\u17b6\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7\u17a2\u17c9\u17c6\u1796\u17b8\u179a\u17c4\u1784*\n\n" +
		"\u179f\u17bc\u1798\u1782\u17b6\u179a\u1795\u17d2\u179f\u17b6\u179a\u1794\u1789\u17d2\u17a0\u17b6\u179a\u17b8\u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789\u17a2\u17c6\u1796\u17b8\u1794\u1789\u17d2\u17a0\u17b6\u1793\u17c5\u1796\u17b8\u1780\u17d2\u179a\u17bb\u1798\u1787\u17c6\u1793\u17bd\u1799\u1780\u17b6\u179a\u179f\u17c1\u179c\u17b6\u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\n" +
		"\u179a\u17b8\u1780\u179a\u17b6\u1799\u1795\u17d2\u178f\u179b\u17cb\u17a2\u1793\u1780\u1793\u17bc\u179c\u179a\u17b6\u179c\u1794\u17d2\u179a\u179f\u17b6\u179a\u178a\u17c2\u179b\u17a2\u1793\u1780\u178f\u17d2\u179a\u17bc\u179c\u1780\u17b6\u179a\u17d4\n\n" +
		"\U0001f4de Hotline: 1800 200 300 \u0028\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\u0029"
	return c.Edit(text, tele.ModeMarkdown, mainMenu())
}

// handleDirectChat is called when the customer clicks "Direct Chat with Team".
// It shows a language selection menu: Khmer, Chinese, English.
func handleDirectChat(c tele.Context) error {
	clearState(c.Sender().ID)
	text := "\U0001f4ac *\u179f\u1793\u17d2\u1791\u1793\u17b6\u1787\u17b6\u1798\u17bd\u1799\u1780\u17d2\u179a\u17bb\u1798\u1780\u17b6\u179a\u1784\u17b6\u179a\u178a\u17c4\u1799\u1795\u17d2\u1791\u17b6\u179b\u17cb*\n\n" +
		"\u179f\u17bc\u1798\u1787\u17d2\u179a\u17be\u179f\u1794\u17d2\u179a\u17be\u179a\u1797\u17b6\u179f\u17b6\u179a\u17c1\u1793\u1780\u17b6\u179a\u179f\u17c1\u179c\u17b6\u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\n" +
		"Please select your language / \u8bf7\u9009\u62e9\u60a8\u7684\u8bed\u8a00"

	langMenu := &tele.ReplyMarkup{}
	langMenu.Inline(
		langMenu.Row(
			langMenu.Data("\U0001f1f0\u0048 \u1781\u17d2\u1798\u17c2\u179a", cbLangKhmer),
			langMenu.Data("\U0001f1e8\u004e \u4e2d\u6587", cbLangChinese),
			langMenu.Data("\U0001f1ec\u0042 English", cbLangEnglish),
		),
		langMenu.Row(
			langMenu.Data("\u2b05\ufe0f \u1791\u17c5\u1798\u17c1\u1793\u17bc\u1799\u179c\u17b7\u1789", cbDirectChatBack),
		),
	)
	return c.Edit(text, tele.ModeMarkdown, langMenu)
}

// chatMenu builds the keyboard shown during live chat mode.
// Language switch buttons + end chat button.
func chatMenu(lang string) *tele.ReplyMarkup {
	m := &tele.ReplyMarkup{}
	m.Inline(
		m.Row(
			m.Data("\U0001f1f0\u0048 \u1781\u17d2\u1798\u17c2\u179a", cbLangKhmer),
			m.Data("\U0001f1e8\u004e \u4e2d\u6587", cbLangChinese),
			m.Data("\U0001f1ec\u0042 English", cbLangEnglish),
		),
		m.Row(
			m.Data("\u274c "+chatEndLabel(lang), cbDirectChatBack),
		),
	)
	return m
}

func chatEndLabel(lang string) string {
	switch lang {
	case "zh":
		return "结束对话"
	case "en":
		return "End Chat"
	default:
		return "\u1794\u1789\u17d2\u1785\u1794\u17cb\u179f\u1793\u17d2\u1791\u1793\u17b6"
	}
}

// handleLangKhmer shows the Direct Chat info in Khmer and enters live chat mode.
func handleLangKhmer(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "live_chat", name: "km"})
	text := "\U0001f4ac *\u179f\u1793\u17d2\u1791\u1793\u17b6\u1787\u17b6\u1798\u17bd\u1799\u1780\u17d2\u179a\u17bb\u1798\u1780\u17b6\u179a\u1784\u17b6\u179a\u178a\u17c4\u1799\u1795\u17d2\u1791\u17b6\u179b\u17cb*\n\n" +
		"\u179f\u17bc\u1798\u1795\u17d2\u1791\u17b6\u179a\u1780\u17b6\u179a\u1787\u17c6\u1793\u17bd\u1799\u1780\u17b6\u179a\u179f\u17c1\u179c\u17b6\u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\n" +
		"\u179a\u17b8\u1780\u179a\u17b6\u1799\u1795\u17d2\u178f\u179b\u17cb\u17a2\u1793\u1780\u1793\u17bc\u179c\u179a\u17b6\u179c\u1794\u17d2\u179a\u179f\u17b6\u179a\u178a\u17c2\u179b\u17a2\u1793\u1780\u178f\u17d2\u179a\u17bc\u179c\u1780\u17b6\u179a\u17d4\n\n" +
		"\U0001f4de \u1791\u17bc\u179a\u179f\u17d0\u1798\u17d2\u179a\u17b6\u1794\u17cb: 1800 200 300 \u0028\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\u0029\n" +
		"\u23f0 \u1798\u17c9\u17c4\u1784\u1780\u17b6\u179a\u1784\u17b6\u179a: 8:00 - 17:00\n\n" +
		"\u270d\ufe0f \u179f\u17bc\u1798\u179c\u17b6\u1799\u179f\u17b6\u179a\u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789"
	return c.Edit(text, tele.ModeMarkdown, chatMenu("km"))
}

// handleLangChinese shows the Direct Chat info in Chinese and enters live chat mode.
func handleLangChinese(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "live_chat", name: "zh"})
	text := "\U0001f4ac *\u76f4\u63a5\u8054\u7cfb\u6211\u4eec\u7684\u56e2\u961f*\n\n" +
		"\u6211\u4eec\u7684\u5ba2\u670d\u56e2\u961f\u5c06\u5c3d\u5feb\u4e3a\u60a8\u670d\u52a1\n" +
		"\u60a8\u53ef\u4ee5\u76f4\u63a5\u5728\u8fd9\u91cc\u53d1\u9001\u6d88\u606f\u7ed9\u6211\u4eec\u7684\u56e2\u961f\u3002\n\n" +
		"\U0001f4de \u70ed\u7ebf: 1800 200 300 \u0028\u514d\u8d39\u0029\n" +
		"\u23f0 \u5de5\u4f5c\u65f6\u95f4: 8:00 - 17:00\n\n" +
		"\u270d\ufe0f \u8bf7\u5728\u4e0b\u65b9\u53d1\u9001\u60a8\u7684\u6d88\u606f"
	return c.Edit(text, tele.ModeMarkdown, chatMenu("zh"))
}

// handleLangEnglish shows the Direct Chat info in English and enters live chat mode.
func handleLangEnglish(c tele.Context) error {
	userID := c.Sender().ID
	setState(userID, &conversationState{step: "live_chat", name: "en"})
	text := "\U0001f4ac *Direct Chat with Our Team*\n\n" +
		"Our customer service team is ready to assist you.\n" +
		"You can send your message directly to our team here.\n\n" +
		"\U0001f4de Hotline: 1800 200 300 \u0028Free\u0029\n" +
		"\u23f0 Working hours: 8:00 - 17:00\n\n" +
		"\u270d\ufe0f Please send your message below"
	return c.Edit(text, tele.ModeMarkdown, chatMenu("en"))
}

// handleDirectChatBack returns to the main menu from Direct Chat.
func handleDirectChatBack(c tele.Context) error {
	clearState(c.Sender().ID)
	return handleBackToMenu(c)
}

// handleBakongTransfer shows the transfer transaction check page.
// It offers a "Search Hash" button so the user can query order status by
// Hash code without having to go back to the main BAKONG menu.
func handleBakongTransfer(c tele.Context) error {
	clearState(c.Sender().ID)
	text := "\U0001f4f3 *\u1786\u17c2\u1780\u1796\u17b8\u1780\u17b6\u179a\u1790\u17d2\u179c\u17be\u1780\u17b6\u179a\u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780*\n\n" +
		"\u179f\u17bc\u1798\u179c\u17b7\u1789\u1781\u17b6\u1784\u1780\u17d2\u179a\u17c4\u1798\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780\u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789\u1794\u1789\u17d2\u17a0\u17b6\u1793\u17c5\u1796\u17b8\u178a\u17c6\u178e\u17be\u1780\u17b6\u179a\u179c\u17be\u1785\u17c1\u1789\u1793\u17b7\u1784\u1785\u17bc\u179b\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780\u17d4\n\n" +
		"\u179f\u17bc\u1798\u1795\u17d2\u1791\u179b\u17cb\u179a\u1794\u179f\u17cb\u1780\u17b6\u179a\u1794\u1789\u17d2\u1785\u17bc\u179b\u1787\u17b6\u1798\u17bd\u1799\u1780\u17d2\u179a\u17bb\u1798\u1787\u17c6\u1793\u17bd\u1799\u1780\u17b6\u179a\u179f\u17c1\u179c\u17b6\u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\u17d4\n\n" +
		"\U0001f4de Hotline: 1800 200 300 \u0028\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\u0029\n" +
		"\u23f0 \u1798\u17c9\u17c4\u1784\u1780\u17b6\u179a\u1784\u17b6\u179a: 8:00 - 17:00"
	return c.Edit(text, tele.ModeMarkdown, bakongSearchMenu())
}

// bakongSearchMenu builds a keyboard with a Hash search button and a back
// button. Used on pages where the user may want to look up an order by Hash.
func bakongSearchMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\U0001f50d \u179f\u17d2\u179a\u17b6\u179c\u179a\u1780\u17b6\u179a\u1794\u1789\u17d2\u1787\u17b6\u1791\u17b6\u1798 Hash", cbBakongSearch),
		),
		menu.Row(
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// handleBakongHash shows the Hash number check page.
func handleBakongHash(c tele.Context) error {
	clearState(c.Sender().ID)
	text := "\U0001f4f3 *\u1780\u17b6\u179a\u1786\u17c2\u1780\u179b\u17c1\u1781Hash \u1796\u17b8\u178a\u17c6\u178e\u17be\u1780\u17b6\u179a\u179c\u17be\u1785\u17c1\u1789\u1793\u17b7\u1784\u1785\u17bc\u179b*\n\n" +
		"\u179f\u17bc\u1798\u179c\u17b7\u1789\u1781\u17b6\u1784\u1780\u17d2\u179a\u17c4\u1798\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780\u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789\u1794\u1789\u17d2\u17a0\u17b6\u1793\u17c5\u1796\u17b8\u178a\u17c6\u178e\u17be\u1780\u17b6\u179a\u179c\u17be\u1785\u17c1\u1789\u1793\u17b7\u1784\u1785\u17bc\u179b\u1795\u17d2\u179f\u17c1\u1784\u17d4\n\n" +
		"\u179f\u17bc\u1798\u1795\u17d2\u1791\u179b\u17cb\u179a\u1794\u179f\u17cb\u1780\u17b6\u179a\u1794\u1789\u17d2\u1785\u17bc\u179b\u1787\u17b6\u1798\u17bd\u1799\u1780\u17d2\u179a\u17bb\u1798\u1787\u17c6\u1793\u17bd\u1799\u1780\u17b6\u179a\u179f\u17c1\u179c\u17b6\u17a2\u178f\u17b7\u1792\u17b7\u1787\u1793\u17d4\n\n" +
		"\U0001f4de Hotline: 1800 200 300 \u0028\u17a5\u178f\u1782\u17b7\u178f\u1790\u17d2\u179b\u17b8\u0029\n" +
		"\u23f0 \u1798\u17c9\u17c4\u1784\u1780\u17b6\u179a\u1784\u17b6\u179a: 8:00 - 17:00"
	return c.Edit(text, tele.ModeMarkdown, backMenu())
}

// handleBakongSearch is the entry point of the Hash-based order lookup flow.
// It switches the conversation to the "awaiting_hash" step so that the next
// text message from the user is captured as a Hash code and handed to
// handleHashInput (conversation.go) for status display.
func handleBakongSearch(c tele.Context) error {
	userID := c.Sender().ID
	log.Printf("[handleBakongSearch] user=%d fired", userID)
	setState(userID, &conversationState{step: "awaiting_hash"})

	text := "\U0001f50d *\u179f\u17d2\u179a\u17b6\u179c\u179a\u1780\u17b6\u179a\u1794\u1789\u17d2\u1787\u17b6\u1791\u17b6\u1798 Hash*\n\n" +
		"\u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781 Hash \u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780\u1793\u17c5\u1781\u17b6\u1784\u1780\u17d2\u179a\u17c4\u1798\u17d4\n\n" +
		"\u17a7\u1791\u17b6\u17a0\u179a\u178e\u17cd: `a5822d81`\n\n" +
		"\u179f\u17bc\u1798\u1794\u1789\u17d2\u1785\u17bc\u179b\u179b\u17c1\u1781 Hash \u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789\u1794\u1789\u17d2\u17a0\u17b6\u1793\u17c5\u1781\u17b6\u1784\u1780\u17d2\u179a\u17c4\u1798\u17d6"
	if err := c.Edit(text, tele.ModeMarkdown, backMenu()); err != nil {
		log.Printf("[handleBakongSearch] Edit failed for user %d: %v - falling back to Send", userID, err)
		return c.Send(text, tele.ModeMarkdown, backMenu())
	}
	return nil
}

// bakongMenu builds a keyboard with 3 action buttons and a back button.
func bakongMenu() *tele.ReplyMarkup {
	menu := &tele.ReplyMarkup{}
	menu.Inline(
		menu.Row(
			menu.Data("\U0001f518 \u179f\u17d2\u1793\u17be\u179a\u179f\u17bb\u1798\u179f\u17b6\u179a\u1791\u1791\u17bd\u179b\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1796\u17b8BAKONG", cbBakongApply),
		),
		menu.Row(
			menu.Data("\U0001f518 \u1786\u17c2\u1780\u1796\u17b8\u1780\u17b6\u179a\u1790\u17d2\u179c\u17be\u1780\u17b6\u179a\u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u179a\u1794\u179f\u17cb\u17a2\u17d2\u1793\u1780", cbBakongTransfer),
		),
		menu.Row(
			menu.Data("\U0001f518 \u1780\u17b6\u179a\u1786\u17c2\u1780\u179b\u17c1\u1781Hash \u1796\u17b8\u178a\u17c6\u178e\u17be\u1780\u17b6\u179a\u179c\u17be\u1785\u17c1\u1789\u1793\u17b7\u1784\u1785\u17bc\u179b\u1795\u17d2\u179f\u17c1\u1784", cbBakongHash),
		),
		menu.Row(
			menu.Data("\U0001f4f1 Generate KHQR Code", cbBakongKHQR),
		),
		menu.Row(
			menu.Data("\U0001f4f7 Scan & Transfer (ស្កែន QR ផ្ញើប្រាក់)", cbBakongScan),
		),
		menu.Row(
			menu.Data("\U0001f519 \u178f\u17d2\u179a\u17a1\u1794\u1791\u17c5\u1798\u17d9\u1793\u17bb\u1799\u178a\u17be\u1798", cbBack),
		),
	)
	return menu
}

// handleBakong shows BAkong KHQR description, benefits, notification template and service buttons.
func handleBakong(c tele.Context) error {
	text := "\U0001f4f3 *BAKONG KHQR (KHQR)*\n\n" +
		"KHQR \u1787\u17b6\u179f\u17d2\u178f\u17b6\u1793\u1791\u17b6\u179a\u1794\u1784\u17d2\u1780\u17be\u178f QR \u179a\u17bd\u1798\u178f\u17c2\u1794\u1784\u17d2\u1780\u17be\u178f\u17a1\u17c1\u1781\u1793\u17b7\u1784\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7 (NBC) \u179a\u1794\u179f\u17cb\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7\u17a2\u1793\u17d2\u178f\u179a\u179c\u17b7\u1792\u17b7\u1793\u17b6\u1780\u179a\u179a\u1794\u179f\u17cb\u17a2\u1793\u17d2\u178f\u179a\u179f\u17b6\u1781\u17b6\u179a\u179b\u179f\u17cb\u1798\u17bd\u1799\u179f\u17d2\u1780\u17c2\u1793\u17a1\u17c1\u1781\u1793\u17b7\u1784 QR \u1785\u17c6\u1793\u17bd\u1793\u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb\u1780\u17b6\u179a\u1794\u1784\u17d2\u1780\u17be\u178f\u179a\u179c\u17b6\u17c6\u1784\u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb\u179a\u1794\u179f\u17cb\u17a2\u1793\u17d2\u178f\u179a\u179c\u17b6\u17c6\u1784\u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb\u179a\u1794\u179f\u17cb\u17a2\u1793\u17d2\u178f\u179a\u1787\u17b6\u178f\u17b7\u1793\u17c5\u1780\u1798\u17d2\u1796\u17bb\u1787\u17b6\u1793\u17b7\u1784\u178a\u17be\u1798\u17d4\n\n" +
		"\u17a2\u17b6\u1785\u1787\u17d2\u179a\u17be\u179f\u179a\u17be\u179f\u178f\u17b6\u1798\u1787\u17d2\u179a\u17be\u179f\u179a\u17be\u179f\u179f\u17c1\u179c\u17b6\u1780\u1798\u17d2\u1798\u178a\u17c2\u179b\u17a2\u17d2\u1793\u1780\u178f\u17d2\u179a\u17bc\u179c\u1780\u17b6\u179a.\n\n" +
		"\u2705 \u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1785\u17c1\u1789\u1785\u17bc\u179b\u179a\u179b\u179f\u17cb \u1793\u17b7\u1784\u179f\u17b6\u179a\u1795\u17d2\u1789\u17ba\u179a\u1794\u179f\u17cb\u1780\u17b6\u179a\u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\n" +
		"\u2705 \u1794\u1784\u17d2\u1780\u17be\u178f\u179f\u17b6\u179a\u1795\u17d2\u1789\u17ba\u179a\u1794\u179f\u17cb\u1780\u17b6\u179a\u1794\u1784\u17d2\u1780\u17be\u178f\n" +
		"\u2705 \u179f\u17b6\u179a\u1794\u1789\u17d2\u1787\u17b6\u1780\u17cb\u179f\u1798\u17d2\u179a\u17b6\u1794\u17cb\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1785\u17bc\u179b\u1785\u17bc\u179b\n" +
		"\u2705 \u179f\u17b6\u179a\u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1785\u17c1\u1789\u1785\u17bc\u179b\n" +
		"\u2705 \u1785\u17bc\u179b\u179a\u1794\u179f\u17cb\u1780\u17b6\u179a\u1795\u17d2\u1791\u17be\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1787\u17c4\u1782\u1787\u17d0\u1799 \u17ac \u1798\u17b7\u1793\u1787\u17c4\u1782\u1787\u17d0\u1799\n\n" +
		"\U0001f4dd *\u179f\u17b6\u179a\u1795\u17d2\u1789\u17ba\u179a\u1794\u179f\u17cb\u1785\u17bc\u179b (\u1782\u1798\u17d2\u179a\u17bc)*\n\n" +
		"[WING BANK]\n" +
		"\u179b\u17c4\u1780\u1794\u17b6\u1793\u1791\u1791\u17bd\u179b\u1791\u17b9\u1780\u1794\u17d2\u179a\u17b6\u1780\u17cb\u1785\u17c6\u1793\u17bd\u1793 300.00 \u178a\u17bb\u179b\u17d2\u179b\u17b6\n" +
		"\u1796\u17b8\u1788\u17d2\u1798\u17c4\u17a0 xxx \u1792\u17b6\u1793\u17c4\u17a0 \u1792\u17b6\u1793\u17b6\u1782\u17b6\u179a ABA BANK\n" +
		"\u178f\u17b6\u1798\u1780\u17b6\u179a\u179f\u17d2\u1780\u17c2\u1793 KHQR\n" +
		"\u1790\u17d2\u1784\u17c3\u1791\u17b8\u17e2\u17e7 \u1780\u1780\u17d2\u1780\u178a\u17b6 \u17e2\u17e0\u17e2\u17e6 \u1798\u17d9\u17a0\u17c4\u1784 \u17e0\u17e9.\u17e2\u17e2 \u179b\u17c6\u178a\u17b6\u1785\n" +
		"\u179b\u17c1\u1781 Hash: a5822d81\n" +
		"\u179f\u1798\u178f\u17bb\u179b\u17d2\u1799\u1794\u1785\u17d2\u1785\u17bb\u1794\u17d2\u1794\u1793\u17d2\u1793: 1,500.00 \u178a\u17bb\u179b\u17d2\u179b\u17b6\n" +
		"\u179b\u17c1\u1781\u1794\u17d2\u179a\u178f\u17b7\u1794\u178f\u17d2\u178f\u17b7\u1780\u17b6\u179a: TXN-20260727-001"
	return c.Edit(text, bakongMenu())
}

// handleBakongApply starts the notification service application flow.
func handleBakongApply(c tele.Context) error {
	userID := c.Sender().ID
	state := getState(userID)
	if state == nil {
		state = &conversationState{}
	}
	// Reset step so text handler doesn't intercept
	state.step = ""
	setState(userID, state)

	text := "\u2709\ufe0f *\u179f\u17d2\u1793\u17be\u179a\u179f\u17c1\u179c\u17b6\u1795\u17d2\u1789\u17ba\u179a\u1794\u179f\u17cb\u1785\u17bc\u179b BAkong*\n\n" +
		"\u179f\u17bc\u1798\u1785\u17bb\u1785\u1794\u1789\u17d2\u1785\u17bc\u179b\u1793\u17c5\u1781\u17b6\u1784\u1780\u17d2\u179a\u17c4\u1798\u1793\u17c5\u1791\u17b8\u1793\u17c8\u179c\u17b7\u1789:"
	return c.Edit(text, tele.ModeMarkdown, notifFormMenu(state))
}
