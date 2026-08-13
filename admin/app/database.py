"""Thin wrapper around the shared SQLite database.

The tgbot process owns the writes (messages, heartbeats, customers). The
admin panel mostly reads, with a few write paths (admin replies, manual
order edits, sms_logs).

We use the stdlib sqlite3 directly instead of SQLAlchemy:
* The schema is already defined by tgbot/migrations/*.sql — no ORM migration.
* SQLite's WAL mode handles concurrent readers fine.
* Raw SQL keeps queries auditable and lets us reuse the exact column names.

Every public function accepts an optional connection so callers can batch
multiple calls inside a transaction if needed.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    path = get_settings().resolved_db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Shared SQLite database not found at {path}. "
            "Start tgbot once so it creates the file and runs migrations."
        )
    conn = sqlite3.connect(
        f"file:{path}?mode=rw", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Defensive: don't let a slow admin query block tgbot writes forever.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = 1")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Generic helpers -------------------------------------------------------


def fetchone(sql: str, params: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()


def fetchall(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Execute a write query and return lastrowid."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid or 0


# --- Health ----------------------------------------------------------------


def db_info() -> dict[str, Any]:
    """Return metadata about the shared DB (file size, row counts, etc.)."""
    path: Path = get_settings().resolved_db_path()
    size = path.stat().st_size if path.exists() else 0
    with get_conn() as conn:
        tables = {
            name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("customers", "messages", "orders", "bot_heartbeats", "sms_logs",
                         "accounts", "transactions", "kyc_records")
        }
    return {"path": str(path), "size_bytes": size, "rows": tables}
