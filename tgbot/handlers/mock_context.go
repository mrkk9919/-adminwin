package handlers

import (
	"errors"
	"time"

	tele "gopkg.in/telebot.v3"
)

// mockContext is a mock implementation of tele.Context for testing handlers
// without making real Telegram API calls.
type mockContext struct {
	// Captured outputs
	sentMessages []sentMessage

	// Configurable inputs
	sender  *tele.User
	message *tele.Message
	chat    *tele.Chat

	// Error simulation
	sendErr error

	// Bot instance (needed by handlePing which calls c.Bot().Send())
	bot *tele.Bot

	// Key-value store (mirrors nativeContext behavior)
	store map[string]interface{}
}

// sentMessage records a single call to Send().
type sentMessage struct {
	What interface{}
	Opts []interface{}
}

// newMockContext creates a mockContext with sensible defaults.
func newMockContext() *mockContext {
	return &mockContext{
		sender: &tele.User{
			ID:        12345,
			FirstName: "Test",
			LastName:  "User",
			Username:  "testuser",
		},
		message: &tele.Message{
			ID:   1,
			Text: "/start",
			Sender: &tele.User{
				ID:        12345,
				FirstName: "Test",
				LastName:  "User",
				Username:  "testuser",
			},
			Chat: &tele.Chat{
				ID: 12345,
			},
		},
		chat: &tele.Chat{
			ID: 12345,
		},
		store: make(map[string]interface{}),
	}
}

// withSender overrides the sender for the mock context.
func (m *mockContext) withSender(u *tele.User) *mockContext {
	m.sender = u
	if m.message != nil {
		m.message.Sender = u
	}
	return m
}

// withMessage overrides the message for the mock context.
func (m *mockContext) withMessage(msg *tele.Message) *mockContext {
	m.message = msg
	return m
}

// withSendError configures Send() to return an error.
func (m *mockContext) withSendError(err error) *mockContext {
	m.sendErr = err
	return m
}

// withBot sets a real *tele.Bot instance (for handlePing tests).
func (m *mockContext) withBot(b *tele.Bot) *mockContext {
	m.bot = b
	return m
}

// --- tele.Context interface implementation ---

func (m *mockContext) Bot() *tele.Bot {
	return m.bot
}

func (m *mockContext) Update() tele.Update {
	return tele.Update{Message: m.message}
}

func (m *mockContext) Message() *tele.Message {
	return m.message
}

func (m *mockContext) Callback() *tele.Callback {
	return nil
}

func (m *mockContext) Query() *tele.Query {
	return nil
}

func (m *mockContext) InlineResult() *tele.InlineResult {
	return nil
}

func (m *mockContext) ShippingQuery() *tele.ShippingQuery {
	return nil
}

func (m *mockContext) PreCheckoutQuery() *tele.PreCheckoutQuery {
	return nil
}

func (m *mockContext) Poll() *tele.Poll {
	return nil
}

func (m *mockContext) PollAnswer() *tele.PollAnswer {
	return nil
}

func (m *mockContext) ChatMember() *tele.ChatMemberUpdate {
	return nil
}

func (m *mockContext) ChatJoinRequest() *tele.ChatJoinRequest {
	return nil
}

func (m *mockContext) Migration() (int64, int64) {
	return 0, 0
}

func (m *mockContext) Topic() *tele.Topic {
	return nil
}

func (m *mockContext) Boost() *tele.BoostUpdated {
	return nil
}

func (m *mockContext) BoostRemoved() *tele.BoostRemoved {
	return nil
}

func (m *mockContext) Sender() *tele.User {
	return m.sender
}

func (m *mockContext) Chat() *tele.Chat {
	return m.chat
}

func (m *mockContext) Recipient() tele.Recipient {
	if m.chat != nil {
		return m.chat
	}
	return m.sender
}

func (m *mockContext) Text() string {
	if m.message != nil {
		return m.message.Text
	}
	return ""
}

func (m *mockContext) Entities() tele.Entities {
	return nil
}

func (m *mockContext) Data() string {
	return ""
}

func (m *mockContext) Args() []string {
	return nil
}

func (m *mockContext) Send(what interface{}, opts ...interface{}) error {
	if m.sendErr != nil {
		return m.sendErr
	}
	m.sentMessages = append(m.sentMessages, sentMessage{What: what, Opts: opts})
	return nil
}

func (m *mockContext) SendAlbum(a tele.Album, opts ...interface{}) error {
	return nil
}

func (m *mockContext) Reply(what interface{}, opts ...interface{}) error {
	return nil
}

func (m *mockContext) Forward(msg tele.Editable, opts ...interface{}) error {
	return nil
}

func (m *mockContext) ForwardTo(to tele.Recipient, opts ...interface{}) error {
	return nil
}

func (m *mockContext) Edit(what interface{}, opts ...interface{}) error {
	return nil
}

func (m *mockContext) EditCaption(caption string, opts ...interface{}) error {
	return nil
}

func (m *mockContext) EditOrSend(what interface{}, opts ...interface{}) error {
	return m.Send(what, opts...)
}

func (m *mockContext) EditOrReply(what interface{}, opts ...interface{}) error {
	return m.Send(what, opts...)
}

func (m *mockContext) Delete() error {
	return nil
}

func (m *mockContext) DeleteAfter(d time.Duration) *time.Timer {
	return time.AfterFunc(d, func() {})
}

func (m *mockContext) Notify(action tele.ChatAction) error {
	return nil
}

func (m *mockContext) Ship(what ...interface{}) error {
	return nil
}

func (m *mockContext) Accept(errorMessage ...string) error {
	return nil
}

func (m *mockContext) Answer(resp *tele.QueryResponse) error {
	return nil
}

func (m *mockContext) Respond(resp ...*tele.CallbackResponse) error {
	return nil
}

func (m *mockContext) RespondText(text string) error {
	return nil
}

func (m *mockContext) RespondAlert(text string) error {
	return nil
}

func (m *mockContext) Get(key string) interface{} {
	return m.store[key]
}

func (m *mockContext) Set(key string, val interface{}) {
	m.store[key] = val
}

// lastSentText returns the text of the last message sent via Send().
func (m *mockContext) lastSentText() string {
	if len(m.sentMessages) == 0 {
		return ""
	}
	last := m.sentMessages[len(m.sentMessages)-1]
	if s, ok := last.What.(string); ok {
		return s
	}
	return ""
}

// newTestBot creates a *tele.Bot in offline mode for tests that need
// c.Bot() to be non-nil (e.g., handlePing). Offline mode skips the
// Telegram API call, so no real token is required.
func newTestBot() *tele.Bot {
	b, err := tele.NewBot(tele.Settings{
		Token:   "000000:fake-token-for-testing",
		Poller:  &tele.LongPoller{Timeout: 1 * time.Second},
		Offline: true,
	})
	if err != nil {
		panic("newTestBot: " + err.Error())
	}
	return b
}

// assertContains checks that s contains substr.
func assertContains(s, substr string) error {
	if len(s) == 0 && len(substr) > 0 {
		return errors.New("expected string to contain " + substr + " but got empty string")
	}
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return nil
		}
	}
	return errors.New("expected string to contain " + substr + " but got: " + s)
}
