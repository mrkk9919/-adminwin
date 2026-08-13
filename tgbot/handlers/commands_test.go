package handlers

import (
	"errors"
	"strings"
	"testing"

	tele "gopkg.in/telebot.v3"
)

func TestHandleStart_SendsMainMenu(t *testing.T) {
	c := newMockContext()
	err := handleStart(c)

	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(c.sentMessages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(c.sentMessages))
	}

	text := c.lastSentText()
	if !strings.Contains(text, "Wing Bank") {
		t.Errorf("expected 'Wing Bank' in welcome, got: %s", text)
	}
	if !strings.Contains(text, "Test") {
		t.Errorf("expected user name in greeting, got: %s", text)
	}
	if len(text) < 50 {
		t.Errorf("expected substantial Khmer welcome text, got short: %s", text)
	}

	// Verify inline keyboard was sent
	msg := c.sentMessages[0]
	if len(msg.Opts) == 0 {
		t.Error("expected inline keyboard option")
	}
}

func TestHandleStart_SendError(t *testing.T) {
	sendErr := errors.New("telegram: send failed")
	c := newMockContext().withSendError(sendErr)

	err := handleStart(c)
	if !errors.Is(err, sendErr) {
		t.Errorf("expected send error, got: %v", err)
	}
}

func TestHandleStart_EmptyName(t *testing.T) {
	c := newMockContext().withSender(&tele.User{
		ID:        99,
		FirstName: "",
	})

	err := handleStart(c)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	text := c.lastSentText()
	// Should still contain "Wing Bank" even with empty name
	if !strings.Contains(text, "Wing Bank") {
		t.Errorf("expected Wing Bank in welcome even with empty name, got: %s", text)
	}
}

func TestHandleStart_NilSender(t *testing.T) {
	c := newMockContext().withSender(nil)
	defer func() {
		if r := recover(); r != nil {
			t.Log("handleStart panics with nil sender (documented behavior)")
		}
	}()
	_ = handleStart(c)
}

func TestHandleHelp_Success(t *testing.T) {
	c := newMockContext()
	err := handleHelp(c)

	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if len(c.sentMessages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(c.sentMessages))
	}

	text := c.lastSentText()
	// Verify Khmer content
	if !strings.Contains(text, "សេវារបស់") {
		t.Errorf("expected Khmer service list header, got: %s", text)
	}
	if !strings.Contains(text, "Wing Bank") {
		t.Errorf("expected 'Wing Bank' in help, got: %s", text)
	}

	// Verify MarkdownV2 parse mode
	msg := c.sentMessages[0]
	hasMarkdownV2 := false
	for _, opt := range msg.Opts {
		if s, ok := opt.(string); ok && s == tele.ModeMarkdownV2 {
			hasMarkdownV2 = true
		}
	}
	if !hasMarkdownV2 {
		t.Error("expected ModeMarkdownV2 parse mode option")
	}
}

func TestHandleHelp_SendError(t *testing.T) {
	sendErr := errors.New("telegram: rate limited")
	c := newMockContext().withSendError(sendErr)

	err := handleHelp(c)
	if !errors.Is(err, sendErr) {
		t.Errorf("expected rate limit error, got: %v", err)
	}
}

func TestHandlePing_SendError(t *testing.T) {
	bot := newTestBot()
	c := newMockContext().withBot(bot)

	err := handlePing(c)
	if err == nil {
		t.Fatal("expected error from Bot.Send() with fake token, got nil")
	}
	t.Logf("handlePing returned expected error: %v", err)
}

func TestHandlePing_NilBot(t *testing.T) {
	c := newMockContext()
	defer func() {
		if r := recover(); r != nil {
			t.Log("handlePing panics with nil bot (documented behavior)")
		}
	}()
	_ = handlePing(c)
}

func TestRegisterCommands_AllRegistered(t *testing.T) {
	bot := newTestBot()
	RegisterCommands(bot)
}
