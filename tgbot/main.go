package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	tele "gopkg.in/telebot.v3"

	// Pure-Go SQLite driver (no CGO). Imported here so tgbot/db stays
	// driver-agnostic. The driver registers itself under the name "sqlite".
	_ "modernc.org/sqlite"

	"tgbot/config"
	"tgbot/db"
	"tgbot/handlers"
	"tgbot/middleware"
	"tgbot/services"
)

func main() {
	// Load configuration from environment variables.
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Open the shared SQLite database (used by tgbot + admin panel).
	store, err := db.Open("sqlite", cfg.DatabasePath)
	if err != nil {
		log.Fatalf("Failed to open database %q: %v", cfg.DatabasePath, err)
	}
	defer store.Close()

	if err := store.RunMigrations(cfg.MigrationsDir); err != nil {
		log.Fatalf("Failed to run migrations: %v", err)
	}

	// Initialize push notification service.
	services.InitPushService(cfg.PushBaseURL, cfg.APIKey)

	// Create the main bot with long-polling (full Wing Bank feature set).
	pref := tele.Settings{
		Token:  cfg.BotToken,
		Poller: &tele.LongPoller{Timeout: cfg.PollerTimeout},
	}

	b, err := tele.NewBot(pref)
	if err != nil {
		log.Fatalf("Failed to create bot: %v", err)
	}

	// Register middleware.
	b.Use(middleware.Logger())
	b.Use(middleware.MessageLogger(store, cfg.BotName))

	// Register command handlers (/start, /help, /ping).
	handlers.Store = store
	handlers.RegisterCommands(b)

	// Register inline keyboard menu handlers.
	handlers.RegisterMenuHandlers(b)

	// Register conversation handler for multi-step flows (e.g., account verification).
	handlers.RegisterConversationHandler(b)

	// Register admin notification commands on the main bot (operator sends
	// /notify <customer_id>, bot looks up transfer and dispatches via ABA bot).
	handlers.RegisterAdminNotifyCommands(b)

	// Heartbeat goroutine: tell the admin panel this bot instance is alive.
	// Runs every 30s for the lifetime of the process.
	startTime := time.Now()
	go heartbeatLoop(store, cfg.BotName, cfg.BotVersion, startTime)

	// Optional secondary ABA BANK bot: chat-only relay (message logging +
	// minimal /start welcome). No menus, no conversation flows.
	var abaBot *tele.Bot
	if cfg.AbaBotToken != "" {
		abaPref := tele.Settings{
			Token:  cfg.AbaBotToken,
			Poller: &tele.LongPoller{Timeout: cfg.PollerTimeout},
		}
		abaBot, err = tele.NewBot(abaPref)
		if err != nil {
			log.Printf("Failed to create ABA bot (skipping secondary bot): %v", err)
		} else {
			abaBot.Use(middleware.Logger())
			abaBot.Use(middleware.MessageLogger(store, cfg.AbaBotName))
			abaBot.Handle("/start", func(c tele.Context) error {
				return c.Send("Welcome to ABA BANK notifications.\n" +
					"You will receive transaction alerts and account updates here.\n" +
					"Our support team can also reach you through this chat.")
			})
			// Register notify commands for admin use
			handlers.RegisterNotifyCommands(abaBot)
			// Register payment commands for admin use
			handlers.RegisterPaymentCommands(abaBot)
			// Expose ABA bot to main bot handlers so /notify can send through it
			handlers.AbaBot = abaBot
			go heartbeatLoop(store, cfg.AbaBotName, cfg.BotVersion, startTime)
			log.Printf("ABA BANK bot (%s) started in chat-only mode", cfg.AbaBotName)
		}
	}

	// Graceful shutdown on interrupt signals.
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-quit
		log.Println("Shutting down bot...")
		// Mark the bots as dead before shutting down so the admin panel
		// doesn't have to wait for the heartbeat timeout.
		if err := store.TouchHeartbeat(cfg.BotName, cfg.BotVersion, "dead", time.Since(startTime), ""); err != nil {
			log.Printf("[heartbeat] shutdown: %v", err)
		}
		if cfg.AbaBotToken != "" {
			if err := store.TouchHeartbeat(cfg.AbaBotName, cfg.BotVersion, "dead", time.Since(startTime), ""); err != nil {
				log.Printf("[heartbeat] shutdown: %v", err)
			}
		}
		b.Stop()
		if abaBot != nil {
			abaBot.Stop()
		}
		log.Println("Bot stopped gracefully")
	}()

	log.Println("Bot started. Press Ctrl+C to stop.")
	if abaBot != nil {
		// Run the secondary bot's polling loop in the background; the main
		// bot blocks here until Stop() is called.
		go abaBot.Start()
	}
	b.Start()
}

// heartbeatLoop touches the bot_heartbeats row every 30 seconds until the
// process exits. The first beat fires immediately so the admin panel lights
// up right away.
func heartbeatLoop(store *db.DB, botName, version string, startTime time.Time) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	if err := store.TouchHeartbeat(botName, version, "alive", time.Since(startTime), ""); err != nil {
		log.Printf("[heartbeat] initial: %v", err)
	}
	for {
		select {
		case <-ticker.C:
			if err := store.TouchHeartbeat(botName, version, "alive", time.Since(startTime), ""); err != nil {
				log.Printf("[heartbeat]: %v", err)
			}
		}
	}
}
