package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"time"
)

// PushService handles push notifications by calling the Python admin backend.
type PushService struct {
	BaseURL    string // e.g. http://127.0.0.1:8080
	APIKey     string // optional API key for auth
	HTTPClient *http.Client
	Enabled    bool
}

// GlobalPush is the global push service instance, initialized by InitPushService.
var GlobalPush *PushService

// InitPushService initializes the global push service.
// If baseURL is empty, push notifications are disabled.
func InitPushService(baseURL, apiKey string) {
	if baseURL == "" {
		log.Println("[push] Push service disabled (PUSH_BASE_URL not set)")
		GlobalPush = &PushService{Enabled: false}
		return
	}
	GlobalPush = &PushService{
		BaseURL: baseURL,
		APIKey:  apiKey,
		Enabled: true,
		HTTPClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
	log.Printf("[push] Push service initialized with base URL: %s", baseURL)
}

// NewPushService creates a new push service client.
func NewPushService(baseURL, apiKey string) *PushService {
	return &PushService{
		BaseURL: baseURL,
		APIKey:  apiKey,
		Enabled: baseURL != "",
		HTTPClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// --- Request/Response types ---

// RegisterTokenRequest is the payload for registering a push token.
type RegisterTokenRequest struct {
	TelegramID int64  `json:"telegram_id"`
	FCMToken   string `json:"fcm_token,omitempty"`
	APNSToken  string `json:"apns_token,omitempty"`
	DeviceType string `json:"device_type"` // android / ios
}

// PushResponse is the generic response from the push API.
type PushResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
	Error   string `json:"error,omitempty"`
}

// SendTestRequest is the payload for sending a test notification.
type SendTestRequest struct {
	TelegramID int64  `json:"telegram_id"`
	Title      string `json:"title"`
	Body       string `json:"body"`
}

// TransferNotificationRequest is the payload for transfer notifications.
type TransferNotificationRequest struct {
	Token         string `json:"token"`
	Amount        string `json:"amount"`
	Currency      string `json:"currency"`
	Counterparty  string `json:"counterparty_name"`
	TransactionID string `json:"transaction_id"`
	Direction     string `json:"direction"` // sent / received
}

// --- API Methods ---

// RegisterToken registers or updates a user's push token.
func (s *PushService) RegisterToken(req RegisterTokenRequest) (*PushResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := s.buildURL("/push/api/register")
	resp, err := s.doPost(url, body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result PushResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

// SendTest sends a test push notification to a user.
func (s *PushService) SendTest(req SendTestRequest) (*PushResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := s.buildURL("/push/api/send-test")
	resp, err := s.doPost(url, body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result PushResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

// SendTransferReceived sends a "transfer received" notification to the recipient.
// userID is the recipient's Telegram ID.
func (s *PushService) SendTransferReceived(userID int64, amount, currency, senderName, txID string) error {
	if !s.Enabled {
		return nil
	}

	req := map[string]interface{}{
		"telegram_id":       userID,
		"amount":            amount,
		"currency":          currency,
		"counterparty_name": senderName,
		"transaction_id":    txID,
		"timestamp":         time.Now().UTC().Format(time.RFC3339),
	}

	body, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}

	url := s.buildURL("/push/api/transfer-received")
	resp, err := s.doPostWithRetries(url, body)
	if err != nil {
		log.Printf("[push] SendTransferReceived error: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("[push] SendTransferReceived failed: HTTP %d", resp.StatusCode)
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	log.Printf("[push] transfer received notification sent to user %d", userID)
	return nil
}

// SendTransferSent sends a "transfer sent" notification to the sender.
// userID is the sender's Telegram ID.
func (s *PushService) SendTransferSent(userID int64, amount, currency, receiverName, txID string) error {
	if !s.Enabled {
		return nil
	}

	req := map[string]interface{}{
		"telegram_id":       userID,
		"amount":            amount,
		"currency":          currency,
		"counterparty_name": receiverName,
		"transaction_id":    txID,
		"timestamp":         time.Now().UTC().Format(time.RFC3339),
	}

	body, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}

	url := s.buildURL("/push/api/transfer-sent")
	resp, err := s.doPostWithRetries(url, body)
	if err != nil {
		log.Printf("[push] SendTransferSent error: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		log.Printf("[push] SendTransferSent failed: HTTP %d", resp.StatusCode)
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	log.Printf("[push] transfer sent notification sent to user %d", userID)
	return nil
}

// --- Helpers ---

func (s *PushService) buildURL(path string) string {
	base := s.BaseURL
	if base == "" {
		base = "http://127.0.0.1:8080"
	}
	u, err := url.Parse(base + path)
	if err != nil {
		return base + path
	}
	return u.String()
}

func (s *PushService) doPost(url string, body []byte) (*http.Response, error) {
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if s.APIKey != "" {
		req.Header.Set("X-API-Key", s.APIKey)
	}

	return s.HTTPClient.Do(req)
}

// doPostWithRetries calls doPost with a small retry loop for transient errors.
func (s *PushService) doPostWithRetries(url string, body []byte) (*http.Response, error) {
	var resp *http.Response
	var err error
	// Try up to 2 attempts (initial + 1 retry)
	for i := 0; i < 2; i++ {
		resp, err = s.doPost(url, body)
		if err == nil {
			// If we got a response and it's not a server error, return it.
			if resp != nil && resp.StatusCode < 500 {
				return resp, nil
			}
		}
		log.Printf("[push] doPost attempt %d failed: %v", i+1, err)
		// brief backoff before retrying
		time.Sleep(300 * time.Millisecond)
	}
	return resp, err
}
