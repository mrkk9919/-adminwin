package config

import (
	"os"
	"testing"
	"time"
)

func setEnv(t *testing.T, key, value string) {
	t.Helper()
	t.Setenv(key, value)
}

func clearEnv(t *testing.T, key string) {
	t.Helper()
	t.Setenv(key, "")
	os.Unsetenv(key)
}

func TestLoad_Success(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	setEnv(t, "API_BASE_URL", "https://api.example.com")
	setEnv(t, "API_KEY", "my-key")
	setEnv(t, "POLLER_TIMEOUT", "15s")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.BotToken != "123456:ABC-DEF" {
		t.Errorf("expected token '123456:ABC-DEF', got %q", cfg.BotToken)
	}
	if cfg.APIBaseURL != "https://api.example.com" {
		t.Errorf("expected API base URL, got %q", cfg.APIBaseURL)
	}
	if cfg.APIKey != "my-key" {
		t.Errorf("expected API key 'my-key', got %q", cfg.APIKey)
	}
	if cfg.PollerTimeout != 15*time.Second {
		t.Errorf("expected 15s poller timeout, got %v", cfg.PollerTimeout)
	}
}

func TestLoad_MinimalConfig(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	clearEnv(t, "API_BASE_URL")
	clearEnv(t, "API_KEY")
	clearEnv(t, "POLLER_TIMEOUT")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.BotToken != "123456:ABC-DEF" {
		t.Errorf("expected token, got %q", cfg.BotToken)
	}
	if cfg.APIBaseURL != "" {
		t.Errorf("expected empty API base URL, got %q", cfg.APIBaseURL)
	}
	if cfg.APIKey != "" {
		t.Errorf("expected empty API key, got %q", cfg.APIKey)
	}
	// Default timeout
	if cfg.PollerTimeout != 10*time.Second {
		t.Errorf("expected default 10s timeout, got %v", cfg.PollerTimeout)
	}
}

func TestLoad_MissingBotToken(t *testing.T) {
	clearEnv(t, "BOT_TOKEN")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error for missing BOT_TOKEN")
	}
	if err.Error() != "BOT_TOKEN environment variable is required" {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestLoad_EmptyBotToken(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error for empty BOT_TOKEN")
	}
}

func TestLoad_InvalidPollerTimeout(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	setEnv(t, "POLLER_TIMEOUT", "not-a-duration")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error for invalid POLLER_TIMEOUT")
	}
	if got := err.Error(); got == "" {
		t.Error("expected non-empty error message")
	}
}

func TestLoad_ZeroPollerTimeout(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	setEnv(t, "POLLER_TIMEOUT", "0s")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.PollerTimeout != 0 {
		t.Errorf("expected 0 timeout, got %v", cfg.PollerTimeout)
	}
}

func TestLoad_NegativePollerTimeout(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	setEnv(t, "POLLER_TIMEOUT", "-5s")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.PollerTimeout != -5*time.Second {
		t.Errorf("expected -5s timeout, got %v", cfg.PollerTimeout)
	}
}

func TestLoad_MillisecondTimeout(t *testing.T) {
	setEnv(t, "BOT_TOKEN", "123456:ABC-DEF")
	setEnv(t, "POLLER_TIMEOUT", "500ms")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.PollerTimeout != 500*time.Millisecond {
		t.Errorf("expected 500ms timeout, got %v", cfg.PollerTimeout)
	}
}

func TestLoad_WhitespaceToken(t *testing.T) {
	// Whitespace-only token should be treated as a valid value
	// (trimming is not implemented — documents current behavior)
	setEnv(t, "BOT_TOKEN", "   ")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.BotToken != "   " {
		t.Errorf("expected whitespace token preserved, got %q", cfg.BotToken)
	}
}
