package chatapi

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"

	tele "gopkg.in/telebot.v3"
)

// Message represents a chat message between a customer and support.
type Message struct {
	ID        int64  `json:"id"`
	ChatID    int64  `json:"chat_id"`
	Username  string `json:"username"`
	FirstName string `json:"first_name"`
	Text      string `json:"text"`
	From      string `json:"from"` // "customer" or "staff"
	Timestamp int64  `json:"timestamp"`
}

// Conversation represents an active chat session.
type Conversation struct {
	ChatID    int64     `json:"chat_id"`
	Username  string    `json:"username"`
	FirstName string    `json:"first_name"`
	LastMsg   string    `json:"last_message"`
	UpdatedAt int64     `json:"updated_at"`
	Messages  []Message `json:"-"`
}

// ReplyRequest is the JSON body for the POST /api/reply endpoint.
type ReplyRequest struct {
	ChatID int64  `json:"chat_id"`
	Text   string `json:"text"`
}

// Server provides HTTP API endpoints for live chat relay.
type Server struct {
	bot   *tele.Bot
	mu    sync.RWMutex
	chats map[int64]*Conversation
	addr  string
	msgID int64
}

// NewServer creates a new chat API server.
func NewServer(bot *tele.Bot, addr string) *Server {
	return &Server{
		bot:   bot,
		chats: make(map[int64]*Conversation),
		addr:  addr,
	}
}

// ForwardMessage is called by the bot to forward a customer message to the API store.
func (s *Server) ForwardMessage(chatID int64, username, firstName, text string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	conv, exists := s.chats[chatID]
	if !exists {
		conv = &Conversation{
			ChatID:    chatID,
			Username:  username,
			FirstName: firstName,
		}
		s.chats[chatID] = conv
	}

	s.msgID++
	msg := Message{
		ID:        s.msgID,
		ChatID:    chatID,
		Username:  username,
		FirstName: firstName,
		Text:      text,
		From:      "customer",
		Timestamp: time.Now().Unix(),
	}
	conv.Messages = append(conv.Messages, msg)
	conv.LastMsg = text
	conv.UpdatedAt = msg.Timestamp
	conv.Username = username
	conv.FirstName = firstName
}

// Start starts the HTTP API server in a goroutine.
func (s *Server) Start() {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/conversations", s.handleConversations)
	mux.HandleFunc("/api/messages/", s.handleMessages)
	mux.HandleFunc("/api/reply", s.handleReply)
	mux.HandleFunc("/api/health", s.handleHealth)

	server := &http.Server{
		Addr:    s.addr,
		Handler: corsMiddleware(mux),
	}

	go func() {
		log.Printf("Chat API server started on %s", s.addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("Chat API server error: %v", err)
		}
	}()
}

// corsMiddleware adds CORS headers for cross-origin requests from your website.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// handleConversations returns all active conversations.
// GET /api/conversations
func (s *Server) handleConversations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	convs := make([]Conversation, 0, len(s.chats))
	for _, c := range s.chats {
		convs = append(convs, *c)
	}

	// Sort by most recent first
	sort.Slice(convs, func(i, j int) bool {
		return convs[i].UpdatedAt > convs[j].UpdatedAt
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(convs)
}

// handleMessages returns all messages for a specific conversation.
// GET /api/messages/{chatID}
func (s *Server) handleMessages(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Parse chatID from URL path
	path := strings.TrimPrefix(r.URL.Path, "/api/messages/")
	var chatID int64
	if _, err := fmt.Sscanf(path, "%d", &chatID); err != nil {
		http.Error(w, "Invalid chat ID", http.StatusBadRequest)
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	conv, exists := s.chats[chatID]
	if !exists {
		http.Error(w, "Conversation not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(conv.Messages)
}

// handleReply sends a reply from staff to a customer via Telegram.
// POST /api/reply
// Body: {"chat_id": 123456, "text": "Hello, how can I help?"}
func (s *Server) handleReply(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ReplyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON body", http.StatusBadRequest)
		return
	}

	if req.ChatID == 0 || req.Text == "" {
		http.Error(w, "chat_id and text are required", http.StatusBadRequest)
		return
	}

	// Send message to customer via Telegram bot
	recipient := &tele.Chat{ID: req.ChatID}
	msg, err := s.bot.Send(recipient, req.Text)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to send: %v", err), http.StatusInternalServerError)
		return
	}

	// Store staff message
	s.mu.Lock()
	conv, exists := s.chats[req.ChatID]
	if exists {
		s.msgID++
		staffMsg := Message{
			ID:        s.msgID,
			ChatID:    req.ChatID,
			Text:      req.Text,
			From:      "staff",
			Timestamp: time.Now().Unix(),
		}
		conv.Messages = append(conv.Messages, staffMsg)
		conv.LastMsg = req.Text
		conv.UpdatedAt = staffMsg.Timestamp
	}
	s.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"ok":         true,
		"message_id": msg.ID,
	})
}

// handleHealth returns the server health status.
// GET /api/health
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "ok",
		"time":   time.Now().Format(time.RFC3339),
	})
}
