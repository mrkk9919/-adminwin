package services

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestHTTPClient_Get_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"message": "hello"})
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))

	var result map[string]string
	err := client.Get(context.Background(), "/test", &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["message"] != "hello" {
		t.Errorf("expected 'hello', got %q", result["message"])
	}
}

func TestHTTPClient_Get_PathAppend(t *testing.T) {
	var requestedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	_ = client.Get(context.Background(), "/api/v1/users", &result)

	if requestedPath != "/api/v1/users" {
		t.Errorf("expected path '/api/v1/users', got %q", requestedPath)
	}
}

func TestHTTPClient_Get_AuthHeader(t *testing.T) {
	var authHeader string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader = r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithAPIKey("my-secret-key"), WithRetries(0))
	var result map[string]string
	_ = client.Get(context.Background(), "/", &result)

	if authHeader != "Bearer my-secret-key" {
		t.Errorf("expected 'Bearer my-secret-key', got %q", authHeader)
	}
}

func TestHTTPClient_Get_AcceptHeader(t *testing.T) {
	var acceptHeader string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		acceptHeader = r.Header.Get("Accept")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	_ = client.Get(context.Background(), "/", &result)

	if acceptHeader != "application/json" {
		t.Errorf("expected 'application/json', got %q", acceptHeader)
	}
}

func TestHTTPClient_Get_NoAPIKey(t *testing.T) {
	var authHeader string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader = r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	_ = client.Get(context.Background(), "/", &result)

	if authHeader != "" {
		t.Errorf("expected empty auth header without API key, got %q", authHeader)
	}
}

func TestHTTPClient_Get_ServerError500(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("internal error"))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error for 500 response")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("expected error to mention status 500, got: %v", err)
	}
}

func TestHTTPClient_Get_ServerError503(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error for 503 response")
	}
	if !strings.Contains(err.Error(), "503") {
		t.Errorf("expected error to mention status 503, got: %v", err)
	}
}

func TestHTTPClient_Get_ClientError400(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error":"bad request"}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error for 400 response")
	}
	if !strings.Contains(err.Error(), "400") {
		t.Errorf("expected error to mention status 400, got: %v", err)
	}
	if !strings.Contains(err.Error(), "bad request") {
		t.Errorf("expected error body in message, got: %v", err)
	}
}

func TestHTTPClient_Get_ClientError404(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte("not found"))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	err := client.Get(context.Background(), "/missing", &result)

	if err == nil {
		t.Fatal("expected error for 404 response")
	}
	if !strings.Contains(err.Error(), "404") {
		t.Errorf("expected error to mention 404, got: %v", err)
	}
}

func TestHTTPClient_Get_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("not json at all {{{"))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
	if !strings.Contains(err.Error(), "decoding response") {
		t.Errorf("expected decode error, got: %v", err)
	}
}

func TestHTTPClient_Get_RetryOn500(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count := atomic.AddInt32(&attempts, 1)
		if count <= 2 {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		// Third attempt succeeds
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(2))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err != nil {
		t.Fatalf("expected success after retries, got: %v", err)
	}
	if result["status"] != "ok" {
		t.Errorf("expected 'ok' after retry, got %q", result["status"])
	}
	if atomic.LoadInt32(&attempts) != 3 {
		t.Errorf("expected 3 attempts, got %d", atomic.LoadInt32(&attempts))
	}
}

func TestHTTPClient_Get_AllRetriesExhausted(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(2))
	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error after exhausting retries")
	}
	if !strings.Contains(err.Error(), "3 attempts") {
		t.Errorf("expected '3 attempts' in error, got: %v", err)
	}
	if atomic.LoadInt32(&attempts) != 3 {
		t.Errorf("expected 3 total attempts, got %d", atomic.LoadInt32(&attempts))
	}
}

func TestHTTPClient_Get_ContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(5 * time.Second)
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	var result map[string]string
	err := client.Get(ctx, "/", &result)

	if err == nil {
		t.Fatal("expected error from cancelled context")
	}
}

func TestHTTPClient_Get_ContextTimeout(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
			return
		case <-time.After(500 * time.Millisecond):
		}
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0), WithTimeout(50*time.Millisecond))
	var result map[string]string

	start := time.Now()
	err := client.Get(context.Background(), "/", &result)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("expected error from timed-out request")
	}
	// Should timeout around 100ms, not wait 5 seconds
	if elapsed > 2*time.Second {
		t.Errorf("request took too long: %v (expected ~100ms timeout)", elapsed)
	}
}

func TestHTTPClient_Get_ContextCancelledDuringRetry(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(5))
	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	var result map[string]string
	err := client.Get(ctx, "/", &result)

	if err == nil {
		t.Fatal("expected error from context timeout during retries")
	}
	// Should not have completed all 6 attempts due to context cancellation
	if atomic.LoadInt32(&attempts) >= 6 {
		t.Errorf("context should have cancelled some retries, attempts: %d", atomic.LoadInt32(&attempts))
	}
}

func TestHTTPClient_Get_NilTarget(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ignored": true}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	err := client.Get(context.Background(), "/", nil)

	if err != nil {
		t.Fatalf("expected no error with nil target, got: %v", err)
	}
}

func TestHTTPClient_Get_UnreachableServer(t *testing.T) {
	client := NewHTTPClient(
		"http://127.0.0.1:1",
		WithRetries(0),
		WithTimeout(200*time.Millisecond),
	)

	var result map[string]string
	err := client.Get(context.Background(), "/", &result)

	if err == nil {
		t.Fatal("expected error for unreachable server")
	}
	if !strings.Contains(err.Error(), "executing request") {
		t.Errorf("expected connection error, got: %v", err)
	}
}

func TestHTTPClient_GetRaw_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"key":"value"}`))
	}))
	defer server.Close()

	client := NewHTTPClient(server.URL, WithRetries(0))
	raw, err := client.GetRaw(context.Background(), "/test")

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(raw, "value") {
		t.Errorf("expected raw JSON containing 'value', got: %s", raw)
	}
}

func TestHTTPClient_GetRaw_Error(t *testing.T) {
	client := NewHTTPClient(
		"http://127.0.0.1:1",
		WithRetries(0),
		WithTimeout(200*time.Millisecond),
	)

	_, err := client.GetRaw(context.Background(), "/test")
	if err == nil {
		t.Fatal("expected error for unreachable server")
	}
}

func TestNewHTTPClient_Defaults(t *testing.T) {
	client := NewHTTPClient("http://example.com")

	if client.baseURL != "http://example.com" {
		t.Errorf("expected base URL 'http://example.com', got %q", client.baseURL)
	}
	if client.retries != 2 {
		t.Errorf("expected default 2 retries, got %d", client.retries)
	}
	if client.client.Timeout != 30*time.Second {
		t.Errorf("expected default 30s timeout, got %v", client.client.Timeout)
	}
}

func TestWithTimeout(t *testing.T) {
	client := NewHTTPClient("http://example.com", WithTimeout(5*time.Second))
	if client.client.Timeout != 5*time.Second {
		t.Errorf("expected 5s timeout, got %v", client.client.Timeout)
	}
}

func TestWithRetries(t *testing.T) {
	client := NewHTTPClient("http://example.com", WithRetries(5))
	if client.retries != 5 {
		t.Errorf("expected 5 retries, got %d", client.retries)
	}
}

func TestWithAPIKey(t *testing.T) {
	client := NewHTTPClient("http://example.com", WithAPIKey("secret"))
	if client.apiKey != "secret" {
		t.Errorf("expected API key 'secret', got %q", client.apiKey)
	}
}

func TestWithMultipleOptions(t *testing.T) {
	client := NewHTTPClient(
		"http://example.com",
		WithTimeout(10*time.Second),
		WithRetries(3),
		WithAPIKey("key123"),
	)

	if client.client.Timeout != 10*time.Second {
		t.Errorf("expected 10s timeout, got %v", client.client.Timeout)
	}
	if client.retries != 3 {
		t.Errorf("expected 3 retries, got %d", client.retries)
	}
	if client.apiKey != "key123" {
		t.Errorf("expected API key 'key123', got %q", client.apiKey)
	}
}
