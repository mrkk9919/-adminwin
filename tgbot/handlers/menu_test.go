package handlers

import (
	"strings"
	"testing"

	tele "gopkg.in/telebot.v3"
)

// mockCallbackContext extends mockContext to support Edit() for callback handlers.
type mockCallbackContext struct {
	mockContext
	editedMessages []sentMessage
	editErr        error
}

func newMockCallbackContext() *mockCallbackContext {
	return &mockCallbackContext{
		mockContext: *newMockContext(),
	}
}

func (m *mockCallbackContext) Edit(what interface{}, opts ...interface{}) error {
	if m.editErr != nil {
		return m.editErr
	}
	m.editedMessages = append(m.editedMessages, sentMessage{What: what, Opts: opts})
	return nil
}

func (m *mockCallbackContext) lastEditedText() string {
	if len(m.editedMessages) == 0 {
		return ""
	}
	last := m.editedMessages[len(m.editedMessages)-1]
	if s, ok := last.What.(string); ok {
		return s
	}
	return ""
}

func TestMainMenu_HasCorrectButtons(t *testing.T) {
	menu := mainMenu()
	if menu == nil {
		t.Fatal("expected non-nil menu")
	}
	if len(menu.InlineKeyboard) != 3 {
		t.Errorf("expected 3 rows, got %d", len(menu.InlineKeyboard))
	}
	for i, row := range menu.InlineKeyboard {
		if len(row) != 2 {
			t.Errorf("row %d: expected 2 buttons, got %d", i, len(row))
		}
	}
}

func TestMainMenu_ButtonLabels(t *testing.T) {
	menu := mainMenu()
	expectedLabels := []string{
		"\U0001f3e6 \u1782\u178e\u1793\u17b8",
		"\U0001f4b0 \u1780\u1798\u1785\u17b8",
		"\U0001f4b1 \u17a2\u178f\u17d2\u179a\u17b6\u1794\u17d2\u178f\u17bc\u179a\u1794\u17d2\u179a\u17b6\u1780\u17cb",
		"\U0001f4cd \u179f\u17b6\u1781\u17b6 \u1793\u17b7\u1784 ATM",
		"\U0001f4de \u1791\u17c6\u1793\u17b6\u1780\u17cb\u1791\u17c4\u1784",
		"\u2139\ufe0f \u17a2\u17c6\u1796\u17b8\u1799\u17be\u1784",
	}

	idx := 0
	for _, row := range menu.InlineKeyboard {
		for _, btn := range row {
			if idx >= len(expectedLabels) {
				t.Fatal("more buttons than expected labels")
			}
			if btn.Text != expectedLabels[idx] {
				t.Errorf("button %d: expected %q, got %q", idx, expectedLabels[idx], btn.Text)
			}
			idx++
		}
	}
}

func TestBackMenu_HasBackButton(t *testing.T) {
	menu := backMenu()
	if len(menu.InlineKeyboard) != 1 {
		t.Fatalf("expected 1 row, got %d", len(menu.InlineKeyboard))
	}
	if len(menu.InlineKeyboard[0]) != 1 {
		t.Fatalf("expected 1 button, got %d", len(menu.InlineKeyboard[0]))
	}
	if !strings.Contains(menu.InlineKeyboard[0][0].Text, "\u178f\u17d2\u179a\u17a1\u1794") {
		t.Errorf("expected back button text, got %q", menu.InlineKeyboard[0][0].Text)
	}
}

func TestHandleAccountInfo(t *testing.T) {
	c := newMockCallbackContext()
	err := handleAccountInfo(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(c.editedMessages) != 1 {
		t.Fatalf("expected 1 edit, got %d", len(c.editedMessages))
	}

	text := c.lastEditedText()
	for _, keyword := range []string{
		"\u1782\u178e\u1793\u17b8\u179f\u1793\u17d2\u179f\u179c",
		"\u1782\u178e\u1793\u17b8\u1794\u1785\u17d2\u1785\u17bb\u1794\u17d2\u1794\u1793\u17d2\u1793",
		"\u1780\u17b6\u179b\u1780\u17c6\u178e\u178f\u17cb",
	} {
		if !strings.Contains(text, keyword) {
			t.Errorf("expected %q in account info, got: %s", keyword, text)
		}
	}

	msg := c.editedMessages[0]
	hasMarkdown := false
	for _, opt := range msg.Opts {
		if s, ok := opt.(string); ok && s == tele.ModeMarkdown {
			hasMarkdown = true
		}
	}
	if !hasMarkdown {
		t.Error("expected ModeMarkdown parse mode option")
	}
}

func TestHandleLoanInfo(t *testing.T) {
	c := newMockCallbackContext()
	err := handleLoanInfo(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	for _, keyword := range []string{
		"\u1780\u1798\u1785\u17b8\u1795\u17d2\u1791\u17b6\u179b\u17cb\u1781\u17d2\u179b\u17bd\u1793",
		"\u1780\u1798\u1785\u17b8\u1791\u17b7\u1789\u1795\u17d1",
		"\u1780\u1798\u1785\u17b8\u17a2\u17b6\u1787\u17b8\u179c\u1780\u1798\u17d2\u1798",
		"\u1799\u17b6\u1793\u1799\u1793\u17d2\u178f",
	} {
		if !strings.Contains(text, keyword) {
			t.Errorf("expected %q in loan info, got: %s", keyword, text)
		}
	}
}

func TestHandleExchangeRates(t *testing.T) {
	c := newMockCallbackContext()
	err := handleExchangeRates(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	if !strings.Contains(text, "USD") {
		t.Errorf("expected USD, got: %s", text)
	}
	if !strings.Contains(text, "KHR") {
		t.Errorf("expected KHR, got: %s", text)
	}
	if !strings.Contains(text, "4,050") {
		t.Errorf("expected buy rate 4,050, got: %s", text)
	}
}

func TestHandleBranches(t *testing.T) {
	c := newMockCallbackContext()
	err := handleBranches(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	for _, branch := range []string{
		"\u1797\u17d2\u1793\u17c6\u1796\u17c1\u1789",
		"\u179f\u17c0\u1798\u179a\u17b6\u1794",
		"\u1794\u17b6\u178f\u17cb\u178a\u17c6\u1794\u1784",
		"ATM",
	} {
		if !strings.Contains(text, branch) {
			t.Errorf("expected %q in branches, got: %s", branch, text)
		}
	}
}

func TestHandleContact(t *testing.T) {
	c := newMockCallbackContext()
	err := handleContact(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	for _, item := range []string{"023 999 888", "1800 200 300", "support@wingbank.com"} {
		if !strings.Contains(text, item) {
			t.Errorf("expected %q in contact info, got: %s", item, text)
		}
	}
}

func TestHandleAbout(t *testing.T) {
	c := newMockCallbackContext()
	err := handleAbout(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	if !strings.Contains(text, "Wing Bank") {
		t.Errorf("expected bank name, got: %s", text)
	}
	if !strings.Contains(text, "500,000") {
		t.Errorf("expected customer count, got: %s", text)
	}
}

func TestHandleBackToMenu(t *testing.T) {
	c := newMockCallbackContext()
	err := handleBackToMenu(c)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	text := c.lastEditedText()
	if !strings.Contains(text, "Wing Bank") {
		t.Errorf("expected Wing Bank in back menu text, got: %s", text)
	}

	msg := c.editedMessages[0]
	hasKeyboard := false
	for _, opt := range msg.Opts {
		if _, ok := opt.(*tele.ReplyMarkup); ok {
			hasKeyboard = true
		}
	}
	if !hasKeyboard {
		t.Error("expected inline keyboard in back-to-menu edit")
	}
}

func TestHandleAccountInfo_EditError(t *testing.T) {
	c := newMockCallbackContext()
	c.editErr = errTestEdit
	if err := handleAccountInfo(c); err == nil {
		t.Fatal("expected edit error")
	}
}

func TestHandleLoanInfo_EditError(t *testing.T) {
	c := newMockCallbackContext()
	c.editErr = errTestEdit
	if err := handleLoanInfo(c); err == nil {
		t.Fatal("expected edit error")
	}
}

func TestHandleBackToMenu_EditError(t *testing.T) {
	c := newMockCallbackContext()
	c.editErr = errTestEdit
	if err := handleBackToMenu(c); err == nil {
		t.Fatal("expected edit error")
	}
}

func TestRegisterMenuHandlers_NoPanic(t *testing.T) {
	bot := newTestBot()
	RegisterMenuHandlers(bot)
}

func TestChannelMenu_HasSatelliteButton(t *testing.T) {
	menu := channelMenu()
	if menu == nil {
		t.Fatal("expected non-nil channel menu")
	}

	found := false
	for _, row := range menu.InlineKeyboard {
		for _, btn := range row {
			if strings.Contains(btn.Text, "Satellite") && btn.Unique == cbChannelSatellite {
				found = true
			}
		}
	}
	if !found {
		t.Error("expected Satellite button in channel menu")
	}
}

func TestHandleChannelSatellite(t *testing.T) {
	c := newMockCallbackContext()
	err := handleChannelSatellite(c)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	text := c.lastEditedText()
	for _, substr := range []string{"Satellite", "Send SOS", "Satellite Message", "0318388000"} {
		if !strings.Contains(text, substr) {
			t.Errorf("expected %q in satellite help text, got: %s", substr, text)
		}
	}
}

var errTestEdit = &editError{}

type editError struct{}

func (e *editError) Error() string { return "edit failed" }
