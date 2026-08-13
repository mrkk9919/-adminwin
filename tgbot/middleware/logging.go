package middleware

import (
	"log"
	"time"

	tele "gopkg.in/telebot.v3"
)

// Logger returns a telebot middleware that logs every incoming message
// with timestamp, user info, and message content.
func Logger() tele.MiddlewareFunc {
	return func(next tele.HandlerFunc) tele.HandlerFunc {
		return func(c tele.Context) error {
			start := time.Now()

			msg := c.Message()
			if msg != nil {
				user := msg.Sender
				log.Printf("[%s] %s %s (id=%d): %s",
					start.Format("2006-01-02 15:04:05"),
					user.FirstName,
					user.LastName,
					user.ID,
					msg.Text,
				)
			} else if cb := c.Callback(); cb != nil {
				log.Printf("[%s] callback from %s %s (id=%d): %s",
					start.Format("2006-01-02 15:04:05"),
					cb.Sender.FirstName,
					cb.Sender.LastName,
					cb.Sender.ID,
					cb.Data,
				)
			}

			err := next(c)

			log.Printf("[%s] processed in %v",
				time.Now().Format("2006-01-02 15:04:05"),
				time.Since(start),
			)

			return err
		}
	}
}
