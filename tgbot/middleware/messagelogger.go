package middleware

import (
	"log"
	"tgbot/db"

	tele "gopkg.in/telebot.v3"
)

// MessageLogger returns a telebot middleware that persists every incoming
// update (text message or callback) to the shared SQLite database. The row
// is written BEFORE the handler runs so the admin panel sees user messages
// in near-real-time even if the handler is slow.
//
// botName tags each row with the bot instance that received it (e.g.
// "wing-bank" or "aba-bank") so the admin panel can route replies through
// the correct bot token.
//
// Customer records are also upserted on every update so the admin panel
// always has a current display name / username for every telegram_id.
//
// Errors from DB writes are logged but never propagated — the bot's core
// UX must not break if the admin database is temporarily unreachable.
func MessageLogger(store *db.DB, botName string) tele.MiddlewareFunc {
	return func(next tele.HandlerFunc) tele.HandlerFunc {
		return func(c tele.Context) error {
			if store == nil {
				return next(c)
			}

			sender := c.Sender()
			if sender == nil {
				return next(c)
			}

			// Best-effort upsert: keep username / display name fresh.
			if err := store.UpsertCustomer(
				sender.ID,
				sender.Username,
				sender.FirstName,
				sender.LastName,
			); err != nil {
				log.Printf("[MessageLogger] upsert customer %d: %v", sender.ID, err)
			}

			// Persist the update itself.
			if msg := c.Message(); msg != nil {
				contentType := "text"
				if msg.Photo != nil {
					contentType = "photo"
				} else if msg.Document != nil {
					contentType = "document"
				} else if msg.Video != nil {
					contentType = "video"
				} else if msg.Sticker != nil {
					contentType = "sticker"
				}
				if err := store.InsertMessage(
					int64(msg.ID),
					sender.ID,
					"in",
					contentType,
					msg.Text,
					"bot",
					botName,
				); err != nil {
					log.Printf("[MessageLogger] insert message %d: %v", msg.ID, err)
				}
			} else if cb := c.Callback(); cb != nil {
				var msgID int64
				if cb.Message != nil {
					msgID = int64(cb.Message.ID)
				}
				if err := store.InsertMessage(
					msgID,
					sender.ID,
					"in",
					"callback",
					cb.Data,
					"bot",
					botName,
				); err != nil {
					log.Printf("[MessageLogger] insert callback: %v", err)
				}
			}

			return next(c)
		}
	}
}
