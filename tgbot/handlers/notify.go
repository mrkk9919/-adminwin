package handlers

import (
	tele "gopkg.in/telebot.v3"
)

// NOTE: notify handlers were moved to the central admin panel. Minimal stubs
// are kept here so the bot process continues to build and run without the
// admin send/notify functionality.

// RegisterNotifyCommands is intentionally a no-op in this build.
func RegisterNotifyCommands(b *tele.Bot) {}

// HandleNotifyText is a no-op placeholder to satisfy build-time references.
func HandleNotifyText(c tele.Context) error { return nil }

