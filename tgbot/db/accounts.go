package db

import (
	"database/sql"
	"fmt"
)

// Account represents a bank account row.
type Account struct {
	ID            int64
	CustomerID    int64 // matches customers.telegram_id
	AccountNumber string
	Currency      string // USD | KHR
	Balance       int64  // stored as integer (cents for USD, whole for KHR)
	Status        string // active | frozen | closed
	Type          string // savings | current | wallet
}

// GetAccountByNumber finds an account by its account number.
// Returns nil, nil if not found.
func (d *DB) GetAccountByNumber(accountNumber string) (*Account, error) {
	const q = `
	SELECT id, customer_id, account_number, currency, balance, status, type
	FROM accounts
	WHERE account_number = ?
	`
	var acc Account
	err := d.QueryRow(q, accountNumber).Scan(
		&acc.ID,
		&acc.CustomerID,
		&acc.AccountNumber,
		&acc.Currency,
		&acc.Balance,
		&acc.Status,
		&acc.Type,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("GetAccountByNumber(%s): %w", accountNumber, err)
	}
	return &acc, nil
}

// GetCustomerIDByAccount finds the customer (telegram) ID for a given account number.
// Returns 0, nil if account not found.
func (d *DB) GetCustomerIDByAccount(accountNumber string) (int64, error) {
	acc, err := d.GetAccountByNumber(accountNumber)
	if err != nil {
		return 0, err
	}
	if acc == nil {
		return 0, nil
	}
	return acc.CustomerID, nil
}
