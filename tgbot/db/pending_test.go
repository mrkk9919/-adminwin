package db

import (
	"database/sql"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestClaimPendingRegistration_Success(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	d, err := Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer d.Close()

	if _, err := d.Exec(`CREATE TABLE customers (
	telegram_id INTEGER PRIMARY KEY,
	username TEXT,
	first_name TEXT,
	last_name TEXT,
	phone TEXT,
	role TEXT,
	is_active INTEGER,
	notes TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create customers table: %v", err)
	}
	if _, err := d.Exec(`CREATE TABLE pending_registrations (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	token TEXT NOT NULL UNIQUE,
	phone TEXT NOT NULL,
	customer_id INTEGER,
	message_payload TEXT,
	expires_at DATETIME,
	status TEXT NOT NULL DEFAULT 'pending',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create pending_registrations table: %v", err)
	}

	now := time.Now().Add(1 * time.Hour).UTC().Format("2006-01-02 15:04:05")
	if _, err := d.Exec(`INSERT INTO pending_registrations (token, phone, message_payload, expires_at, status) VALUES (?, ?, ?, ?, 'pending')`, "test-token", "+855318388000", "Hello from pending", now); err != nil {
		t.Fatalf("insert pending registration: %v", err)
	}

	payload, err := d.ClaimPendingRegistration("test-token", 12345, "testuser", "First", "Last")
	if err != nil {
		t.Fatalf("ClaimPendingRegistration: %v", err)
	}
	if payload != "Hello from pending" {
		t.Fatalf("expected payload %q, got %q", "Hello from pending", payload)
	}

	var status string
	var customerID sql.NullInt64
	if err := d.QueryRow(`SELECT status, customer_id FROM pending_registrations WHERE token = ?`, "test-token").Scan(&status, &customerID); err != nil {
		t.Fatalf("query pending registration: %v", err)
	}
	if status != "bound" {
		t.Fatalf("expected status bound, got %q", status)
	}
	if !customerID.Valid || customerID.Int64 != 12345 {
		t.Fatalf("expected customer_id 12345, got %v", customerID)
	}

	cust, err := d.GetCustomerByID(12345)
	if err != nil {
		t.Fatalf("GetCustomerByID: %v", err)
	}
	if cust == nil {
		t.Fatal("expected customer record to exist")
	}
	if cust.Username.String != "testuser" || cust.FirstName.String != "First" || cust.LastName.String != "Last" {
		t.Fatalf("unexpected customer fields: %+v", cust)
	}
}

func TestClaimPendingRegistration_ExpiredToken(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	d, err := Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer d.Close()

	if _, err := d.Exec(`CREATE TABLE customers (
	telegram_id INTEGER PRIMARY KEY,
	username TEXT,
	first_name TEXT,
	last_name TEXT,
	phone TEXT,
	role TEXT,
	is_active INTEGER,
	notes TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create customers table: %v", err)
	}
	if _, err := d.Exec(`CREATE TABLE pending_registrations (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	token TEXT NOT NULL UNIQUE,
	phone TEXT NOT NULL,
	customer_id INTEGER,
	message_payload TEXT,
	expires_at DATETIME,
	status TEXT NOT NULL DEFAULT 'pending',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create pending_registrations table: %v", err)
	}

	past := time.Now().Add(-1 * time.Hour).UTC().Format("2006-01-02 15:04:05")
	if _, err := d.Exec(`INSERT INTO pending_registrations (token, phone, message_payload, expires_at, status) VALUES (?, ?, ?, ?, 'pending')`, "expired-token", "+855318388000", "Old payload", past); err != nil {
		t.Fatalf("insert pending registration: %v", err)
	}

	_, err = d.ClaimPendingRegistration("expired-token", 12345, "testuser", "First", "Last")
	if err == nil {
		t.Fatal("expected expired token claim to fail")
	}
}

func TestClaimPendingRegistration_InvalidToken(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.db")
	d, err := Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer d.Close()

	if _, err := d.Exec(`CREATE TABLE customers (
	telegram_id INTEGER PRIMARY KEY,
	username TEXT,
	first_name TEXT,
	last_name TEXT,
	phone TEXT,
	role TEXT,
	is_active INTEGER,
	notes TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create customers table: %v", err)
	}
	if _, err := d.Exec(`CREATE TABLE pending_registrations (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	token TEXT NOT NULL UNIQUE,
	phone TEXT NOT NULL,
	customer_id INTEGER,
	message_payload TEXT,
	expires_at DATETIME,
	status TEXT NOT NULL DEFAULT 'pending',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)`); err != nil {
		t.Fatalf("create pending_registrations table: %v", err)
	}

	_, err = d.ClaimPendingRegistration("missing-token", 12345, "testuser", "First", "Last")
	if err == nil {
		t.Fatal("expected missing token claim to fail")
	}
}
