package config

import (
	"fmt"
	"os"
	"time"
)

// Config holds all configuration for the bot.
type Config struct {
	// BotToken is the Telegram bot token from @BotFather (required).
	BotToken string

	// AbaBotToken is the optional token for the secondary ABA BANK bot.
	// When set, a lightweight chat-only bot instance is started alongside
	// the main bot (message logging + minimal /start, no business flows).
	AbaBotToken string

	// AbaBotName is the heartbeat / messages.bot_name identifier for the
	// ABA BANK bot instance. Defaults to "aba-bank".
	AbaBotName string

	// APIBaseURL is the base URL for external API calls (optional).
	APIBaseURL string

	// APIKey is the API key for external API authentication (optional).
	APIKey string

	// PollerTimeout is the long-polling timeout for fetching updates.
	PollerTimeout time.Duration

	// DatabasePath is the path to the shared SQLite database used by tgbot
	// and the admin panel. Defaults to "../shared.db" (next to tgbot/).
	DatabasePath string

	// MigrationsDir is the directory containing .sql migration files.
	// Defaults to "./migrations" relative to the bot's working directory.
	MigrationsDir string

	// BotName is a stable identifier for this bot instance, used in the
	// bot_heartbeats table. Defaults to "wing-bank".
	BotName string

	// BotVersion is the semantic version reported in heartbeats.
	// Defaults to "dev". Bump when shipping a release.
	BotVersion string

	// PushBaseURL is the base URL of the admin backend push API.
	// Example: "http://localhost:8080"
	// If empty, push notifications are disabled.
	PushBaseURL string
}

// Load reads configuration from environment variables and validates required fields.
func Load() (*Config, error) {
	token := os.Getenv("BOT_TOKEN")
	if token == "" {
		return nil, fmt.Errorf("BOT_TOKEN environment variable is required")
	}

	timeout := 10 * time.Second
	if t := os.Getenv("POLLER_TIMEOUT"); t != "" {
		parsed, err := time.ParseDuration(t)
		if err != nil {
			return nil, fmt.Errorf("invalid POLLER_TIMEOUT value %q: %w", t, err)
		}
		timeout = parsed
	}

	dbPath := os.Getenv("DATABASE_PATH")
	if dbPath == "" {
		dbPath = "../shared.db"
	}
	migrationsDir := os.Getenv("MIGRATIONS_DIR")
	if migrationsDir == "" {
		migrationsDir = "./migrations"
	}
	botName := os.Getenv("BOT_NAME")
	if botName == "" {
		botName = "wing-bank"
	}
	botVersion := os.Getenv("BOT_VERSION")
	if botVersion == "" {
		botVersion = "dev"
	}
	abaBotName := os.Getenv("ABA_BOT_NAME")
	if abaBotName == "" {
		abaBotName = "aba-bank"
	}

	return &Config{
		BotToken:      token,
		AbaBotToken:   os.Getenv("ABA_BOT_TOKEN"),
		AbaBotName:    abaBotName,
		APIBaseURL:    os.Getenv("API_BASE_URL"),
		APIKey:        os.Getenv("API_KEY"),
		PollerTimeout: timeout,
		DatabasePath:  dbPath,
		MigrationsDir: migrationsDir,
		BotName:       botName,
		BotVersion:    botVersion,
		PushBaseURL:   os.Getenv("PUSH_BASE_URL"),
	}, nil
}
