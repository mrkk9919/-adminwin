package db

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// DB wraps a *sql.DB with helper accessors for the Wing Bank tables.
//
// The package is intentionally driver-agnostic: callers import a SQLite
// driver (e.g. modernc.org/sqlite or github.com/mattn/go-sqlite3) in their
// main package and pass driverName="sqlite" or "sqlite3" here.
type DB struct {
	*sql.DB
	path string
}

// Open connects to the SQLite database at path, enables WAL mode for safe
// concurrent access with the admin panel, and returns a wrapped *DB.
//
// driverName is the registered sql driver (e.g. "sqlite" for modernc.org/sqlite,
// "sqlite3" for github.com/mattn/go-sqlite3).
func Open(driverName, path string) (*DB, error) {
	dsn := fmt.Sprintf(
		"file:%s?_pragma=journal_mode(WAL)&_pragma=busy_timeout(5000)&_pragma=foreign_keys(1)",
		path,
	)
	conn, err := sql.Open(driverName, dsn)
	if err != nil {
		return nil, fmt.Errorf("db.Open(%s): %w", driverName, err)
	}
	// SQLite is single-writer; keep one connection to avoid lock contention.
	conn.SetMaxOpenConns(1)
	if err := conn.Ping(); err != nil {
		_ = conn.Close()
		return nil, fmt.Errorf("db.Open ping: %w", err)
	}
	return &DB{DB: conn, path: path}, nil
}

// Path returns the filesystem path of the database file.
func (d *DB) Path() string { return d.path }

// RunMigrations executes every .sql file under migrationsDir in
// lexicographic order. Each file is expected to use CREATE TABLE IF NOT EXISTS
// so re-running is safe.
//
// migrationsDir is typically "./migrations" (relative to the working directory
// where the bot binary is launched) but may be overridden for tests.
func (d *DB) RunMigrations(migrationsDir string) error {
	// Normalise the path once; reject anything containing ".." components
	// (path traversal) or that resolves outside the working directory.
	clean := filepath.Clean(migrationsDir)
	if strings.Contains(clean, "..") {
		return fmt.Errorf("RunMigrations: suspicious path %q (clean=%q)", migrationsDir, clean)
	}

	entries, err := os.ReadDir(clean)
	if err != nil {
		return fmt.Errorf("RunMigrations readdir %s: %w", clean, err)
	}

	var names []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		// Only process plain .sql files; ignore backups, editor swaps, etc.
		if !strings.HasSuffix(name, ".sql") || strings.HasPrefix(name, ".") {
			continue
		}
		// Reject any name that tries to escape the migrations directory.
		if filepath.Clean(name) != name || strings.ContainsRune(name, os.PathSeparator) {
			log.Printf("[db] skipping suspicious migration path: %s", name)
			continue
		}
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		full := filepath.Join(clean, name)
		body, err := os.ReadFile(full)
		if err != nil {
			return fmt.Errorf("RunMigrations read %s: %w", full, err)
		}
		if _, err := d.Exec(string(body)); err != nil {
			errStr := err.Error()
			// Skip migrations that have already been applied (idempotent migrations)
			// This handles cases where columns/indexes already exist
			if strings.Contains(errStr, "duplicate column name") ||
				strings.Contains(errStr, "already exists") ||
				strings.Contains(errStr, "table") && strings.Contains(errStr, "already exists") {
				log.Printf("[db] migration already applied: %s (skipping)", name)
				continue
			}
			return fmt.Errorf("RunMigrations exec %s: %w", name, err)
		}
		log.Printf("[db] migration applied: %s", name)
	}
	return nil
}
