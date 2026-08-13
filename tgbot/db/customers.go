package db

import (
	"database/sql"
	"fmt"
	"strings"
	"time"
)

// Customer is a row from the customers table. telegram_id is the primary key
// and matches Telegram's User.ID.
type Customer struct {
	TelegramID int64
	Username   sql.NullString
	FirstName  sql.NullString
	LastName   sql.NullString
	Phone      sql.NullString
	Role       string // customer | vip | banned
	IsActive   bool
	Notes      sql.NullString
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

// UpsertCustomer inserts a new customer or updates the display fields
// (username / first / last name) if the telegram_id already exists.
// Role, is_active and notes are never overwritten here — they are operator-
// controlled via the admin panel.
func (d *DB) UpsertCustomer(telegramID int64, username, firstName, lastName string) error {
	const q = `
INSERT INTO customers (telegram_id, username, first_name, last_name, role, is_active)
VALUES (?, ?, ?, ?, 'customer', 1)
ON CONFLICT(telegram_id) DO UPDATE SET
  username   = COALESCE(excluded.username,   customers.username),
  first_name = COALESCE(excluded.first_name, customers.first_name),
  last_name  = COALESCE(excluded.last_name,  customers.last_name),
  updated_at = CURRENT_TIMESTAMP`
	_, err := d.Exec(q,
		telegramID,
		nullStr(username),
		nullStr(firstName),
		nullStr(lastName),
	)
	if err != nil {
		return fmt.Errorf("UpsertCustomer(%d): %w", telegramID, err)
	}
	return nil
}

// UpsertCustomerWithPhone inserts or updates a customer record and keeps a
// normalized phone number in sync when a pending registration is claimed.
func (d *DB) UpsertCustomerWithPhone(telegramID int64, username, firstName, lastName, phone string) error {
	normalizedPhone := normalizePhone(phone)
	const q = `
INSERT INTO customers (telegram_id, username, first_name, last_name, phone, role, is_active)
VALUES (?, ?, ?, ?, ?, 'customer', 1)
ON CONFLICT(telegram_id) DO UPDATE SET
  username   = COALESCE(excluded.username,   customers.username),
  first_name = COALESCE(excluded.first_name, customers.first_name),
  last_name  = COALESCE(excluded.last_name,  customers.last_name),
  phone      = COALESCE(excluded.phone,      customers.phone),
  updated_at = CURRENT_TIMESTAMP`
	_, err := d.Exec(q,
		telegramID,
		nullStr(username),
		nullStr(firstName),
		nullStr(lastName),
		nullStr(normalizedPhone),
	)
	if err != nil {
		return fmt.Errorf("UpsertCustomerWithPhone(%d): %w", telegramID, err)
	}
	return nil
}

// IsBanned returns true if the customer exists and has role='banned' or
// is_active=0. Unknown telegram IDs are treated as NOT banned so new users
// can interact with the bot before the DB is seeded.
func (d *DB) IsBanned(telegramID int64) (bool, error) {
	const q = `SELECT role, is_active FROM customers WHERE telegram_id = ?`
	var role string
	var active int
	if err := d.QueryRow(q, telegramID).Scan(&role, &active); err == sql.ErrNoRows {
		return false, nil
	} else if err != nil {
		return false, fmt.Errorf("IsBanned(%d): %w", telegramID, err)
	}
	return role == "banned" || active == 0, nil
}

// GetCustomerByID finds a customer by their telegram ID.
// Returns nil, nil if not found.
func (d *DB) GetCustomerByID(telegramID int64) (*Customer, error) {
	const q = `
	SELECT telegram_id, username, first_name, last_name, phone, role, is_active, notes, created_at, updated_at
	FROM customers
	WHERE telegram_id = ?
	`
	var c Customer
	err := d.QueryRow(q, telegramID).Scan(
		&c.TelegramID,
		&c.Username,
		&c.FirstName,
		&c.LastName,
		&c.Phone,
		&c.Role,
		&c.IsActive,
		&c.Notes,
		&c.CreatedAt,
		&c.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("GetCustomerByID(%d): %w", telegramID, err)
	}
	return &c, nil
}

// GetCustomerByPhone finds a customer by their normalized phone number.
// Returns nil, nil if not found.
func (d *DB) GetCustomerByPhone(phone string) (*Customer, error) {
	normalized := normalizePhone(phone)
	if normalized == "" {
		return nil, nil
	}

	const q = `
	SELECT telegram_id, username, first_name, last_name, phone, role, is_active, notes, created_at, updated_at
	FROM customers
	WHERE phone = ?
	LIMIT 1
	`
	var c Customer
	err := d.QueryRow(q, normalized).Scan(
		&c.TelegramID,
		&c.Username,
		&c.FirstName,
		&c.LastName,
		&c.Phone,
		&c.Role,
		&c.IsActive,
		&c.Notes,
		&c.CreatedAt,
		&c.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("GetCustomerByPhone(%q): %w", phone, err)
	}
	return &c, nil
}

// GetCustomerByUsername finds a customer by their username (without @).
// Returns nil, nil if not found.
func (d *DB) GetCustomerByUsername(username string) (*Customer, error) {
	if username == "" {
		return nil, nil
	}
	const q = `
	SELECT telegram_id, username, first_name, last_name, phone, role, is_active, notes, created_at, updated_at
	FROM customers
	WHERE username = ?
	LIMIT 1
	`
	var c Customer
	err := d.QueryRow(q, username).Scan(
		&c.TelegramID,
		&c.Username,
		&c.FirstName,
		&c.LastName,
		&c.Phone,
		&c.Role,
		&c.IsActive,
		&c.Notes,
		&c.CreatedAt,
		&c.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("GetCustomerByUsername(%q): %w", username, err)
	}
	return &c, nil
}

func normalizePhone(phone string) string {
	phone = strings.TrimSpace(phone)
	phone = strings.ReplaceAll(phone, " ", "")
	phone = strings.ReplaceAll(phone, "-", "")
	phone = strings.ReplaceAll(phone, "(", "")
	phone = strings.ReplaceAll(phone, ")", "")
	phone = strings.ReplaceAll(phone, "+", "")
	return phone
}

func nullStr(s string) sql.NullString {
	if s == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: s, Valid: true}
}
