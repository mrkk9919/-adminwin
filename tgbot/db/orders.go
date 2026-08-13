package db

import (
	"database/sql"
	"fmt"
	"time"
)

// Order represents a BAKONG transfer row keyed by hash.
type Order struct {
	Hash       string
	CustomerID sql.NullInt64
	Amount     sql.NullString
	Currency   string
	Status     string
	Bank       sql.NullString
	Receiver   sql.NullString
	TxDate     sql.NullString
	TxID       sql.NullString
	Notes      sql.NullString
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

// FindOrderByHash returns an order by hash, or nil if not found.
func (d *DB) FindOrderByHash(hash string) (*Order, error) {
	const q = `
SELECT hash, customer_id, amount, currency, status, bank, receiver, tx_date, tx_id, notes, created_at, updated_at
FROM orders WHERE hash = ?`
	var o Order
	err := d.QueryRow(q, hash).Scan(
		&o.Hash, &o.CustomerID, &o.Amount, &o.Currency, &o.Status,
		&o.Bank, &o.Receiver, &o.TxDate, &o.TxID, &o.Notes,
		&o.CreatedAt, &o.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("FindOrderByHash(%q): %w", hash, err)
	}
	return &o, nil
}

// UpsertOrder inserts or updates an order row. Useful both for the bot
// (writing a new hash from a payment notification) and the admin panel
// (editing order status after manual reconciliation).
func (d *DB) UpsertOrder(o *Order) error {
	if o == nil || o.Hash == "" {
		return fmt.Errorf("UpsertOrder: nil or empty hash")
	}
	const q = `
INSERT INTO orders (hash, customer_id, amount, currency, status, bank, receiver, tx_date, tx_id, notes)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(hash) DO UPDATE SET
  customer_id = COALESCE(excluded.customer_id, orders.customer_id),
  amount      = COALESCE(excluded.amount,      orders.amount),
  currency    = COALESCE(excluded.currency,    orders.currency),
  status      = excluded.status,
  bank        = COALESCE(excluded.bank,        orders.bank),
  receiver    = COALESCE(excluded.receiver,    orders.receiver),
  tx_date     = COALESCE(excluded.tx_date,     orders.tx_date),
  tx_id       = COALESCE(excluded.tx_id,       orders.tx_id),
  notes       = COALESCE(excluded.notes,       orders.notes),
  updated_at  = CURRENT_TIMESTAMP`
	_, err := d.Exec(q,
		o.Hash, o.CustomerID, o.Amount, o.Currency, o.Status,
		o.Bank, o.Receiver, o.TxDate, o.TxID, o.Notes,
	)
	if err != nil {
		return fmt.Errorf("UpsertOrder(%q): %w", o.Hash, err)
	}
	return nil
}

// FindLatestOrderByCustomerID returns the most recent order for the given
// customer (telegram id) or nil if none found.
func (d *DB) FindLatestOrderByCustomerID(telegramID int64) (*Order, error) {
	const q = `
SELECT hash, customer_id, amount, currency, status, bank, receiver, tx_date, tx_id, notes, created_at, updated_at
FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1`
	var o Order
	err := d.QueryRow(q, telegramID).Scan(
		&o.Hash, &o.CustomerID, &o.Amount, &o.Currency, &o.Status,
		&o.Bank, &o.Receiver, &o.TxDate, &o.TxID, &o.Notes,
		&o.CreatedAt, &o.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("FindLatestOrderByCustomerID(%d): %w", telegramID, err)
	}
	return &o, nil
}
