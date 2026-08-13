package db

import (
	"database/sql"
	"fmt"
	"time"
)

// Heartbeat records the liveness of a single bot instance.
type Heartbeat struct {
	BotName       string
	LastHeartbeat time.Time
	Status        string // alive | degraded | dead | unknown
	Version       sql.NullString
	UptimeSeconds sql.NullInt64
	Meta          sql.NullString // JSON payload for extra metrics
}

// TouchHeartbeat upserts the liveness row for the given bot. Call this every
// ~30 seconds from a background goroutine; the admin panel treats a bot as
// dead when now() - last_heartbeat > 60s.
func (d *DB) TouchHeartbeat(botName, version, status string, uptime time.Duration, metaJSON string) error {
	if botName == "" {
		return fmt.Errorf("TouchHeartbeat: empty botName")
	}
	const q = `
INSERT INTO bot_heartbeats (bot_name, last_heartbeat, status, version, uptime_seconds, meta)
VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
ON CONFLICT(bot_name) DO UPDATE SET
  last_heartbeat = CURRENT_TIMESTAMP,
  status         = excluded.status,
  version        = COALESCE(excluded.version, bot_heartbeats.version),
  uptime_seconds = excluded.uptime_seconds,
  meta           = COALESCE(excluded.meta, bot_heartbeats.meta)`
	_, err := d.Exec(q,
		botName,
		status,
		nullStr(version),
		nullInt64(int64(uptime.Seconds())),
		nullStr(metaJSON),
	)
	if err != nil {
		return fmt.Errorf("TouchHeartbeat(%s): %w", botName, err)
	}
	return nil
}
