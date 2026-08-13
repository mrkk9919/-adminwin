package db

import (
	"database/sql"
	"fmt"
	"time"
)

// PendingRegistration represents a pending registration created by sending
// a deep-link token to a phone number.
type PendingRegistration struct {
	ID        int64
	Token     string
	Phone     string
	CustomerID sql.NullInt64
	MessagePayload sql.NullString
	ExpiresAt time.Time
	Status    string
	CreatedAt time.Time
}

// GetPendingByToken returns the pending registration row by token, or nil if not found.
func (d *DB) GetPendingByToken(token string) (*PendingRegistration, error) {
	const q = `SELECT id, token, phone, customer_id, message_payload, expires_at, status, created_at FROM pending_registrations WHERE token = ? LIMIT 1` 
	var p PendingRegistration
	var custID sql.NullInt64
	var payload sql.NullString
	var expires string
	if err := d.QueryRow(q, token).Scan(&p.ID, &p.Token, &p.Phone, &custID, &payload, &expires, &p.Status, &p.CreatedAt); err == sql.ErrNoRows {
		return nil, nil
	} else if err != nil {
		return nil, fmt.Errorf("GetPendingByToken(%s): %w", token, err)
	}
	p.CustomerID = custID
	p.MessagePayload = payload
	if t, err := time.Parse("2006-01-02 15:04:05", expires); err == nil {
		p.ExpiresAt = t
	} else if t, err := time.Parse(time.RFC3339, expires); err == nil {
		p.ExpiresAt = t
	}
	return &p, nil
}

// ClaimPendingRegistration atomically marks the pending registration as bound
// and upserts the customer record. Returns the message_payload to send (if any).
func (d *DB) ClaimPendingRegistration(token string, telegramID int64, username, firstName, lastName string) (string, error) {
	// Transactional: ensure only one claimant wins.
	tx, err := d.Begin()
	if err != nil {
		return "", fmt.Errorf("ClaimPendingRegistration begin: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	const selectQ = `SELECT id, phone, message_payload, expires_at, status FROM pending_registrations WHERE token = ?`
	var id int64
	var phone string
	var payload sql.NullString
	var expires string
	var status string
	if err := tx.QueryRow(selectQ, token).Scan(&id, &phone, &payload, &expires, &status); err == sql.ErrNoRows {
		return "", fmt.Errorf("token not found")
	} else if err != nil {
		return "", fmt.Errorf("Claim select: %w", err)
	}
	if status != "pending" {
		return "", fmt.Errorf("token status is not pending: %s", status)
	}
	// Check expiry
	if expires != "" {
		if t, err := time.Parse("2006-01-02 15:04:05", expires); err == nil {
			if time.Now().After(t) {
				return "", fmt.Errorf("token expired")
			}
		} else if t, err := time.Parse(time.RFC3339, expires); err == nil {
			if time.Now().After(t) {
				return "", fmt.Errorf("token expired")
			}
		}
	}

	// Update pending_registrations: set status='bound', customer_id = telegramID
	const updateQ = `UPDATE pending_registrations SET status = 'bound', customer_id = ? WHERE id = ?`
	if _, err := tx.Exec(updateQ, telegramID, id); err != nil {
		return "", fmt.Errorf("claim update: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return "", fmt.Errorf("claim commit: %w", err)
	}

	// Upsert customer record and phone binding after the claim succeeds.
	if err := d.UpsertCustomerWithPhone(telegramID, username, firstName, lastName, phone); err != nil {
		return "", fmt.Errorf("upsert customer with phone: %w", err)
	}

	// Retrieve message_payload to return
	var msg string
	if payload.Valid {
		msg = payload.String
	}
	return msg, nil
}
