"""Client-facing REST API for the Wing Bank mobile app / frontend.

Public endpoints (no admin JWT required):
  POST /api/client/auth/register   — phone + password signup
  POST /api/client/auth/login      — phone + password login, returns JWT
  GET  /api/client/accounts        — list caller's USD/KHR accounts
  POST /api/client/transfer        — move money by phone or account number
  GET  /api/client/transactions    — caller's transaction history

Auth: Bearer JWT in Authorization header (issued at register/login).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt as pyjwt

from app import database
from app.config import get_settings

router = APIRouter(prefix="/api/client", tags=["client"])

# ── Password hashing (PBKDF2-SHA256) ─────────────────────────────────────

_PBKDF2_ITERS = 100_000


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERS)
    return dk.hex(), salt


def _verify_password(password: str, password_hash: str, salt: str) -> bool:
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, password_hash)


# ── JWT helpers ──────────────────────────────────────────────────────────

CLIENT_TOKEN_EXPIRE_HOURS = 24 * 30  # 30 days


def _create_client_token(telegram_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc).timestamp() + CLIENT_TOKEN_EXPIRE_HOURS * 3600
    payload = {"sub": str(telegram_id), "type": "client", "exp": expire}
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_client_token(token: str) -> Optional[int]:
    settings = get_settings()
    try:
        payload = pyjwt.decode(token, settings.jwt_secret,
                               algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "client":
            return None
        return int(payload["sub"])
    except (pyjwt.PyJWTError, KeyError, ValueError):
        return None


_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> int:
    """Return telegram_id from Bearer token or 401."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tid = _decode_client_token(credentials.credentials)
    if tid is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Verify user still exists and is active
    row = database.fetchone(
        "SELECT telegram_id, is_active FROM customers WHERE telegram_id=?", (tid,))
    if not row:
        raise HTTPException(status_code=401, detail="Account not found")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Account is banned")
    return tid


# ── Account number generation ────────────────────────────────────────────

def _generate_account_number(currency: str) -> str:
    """Generate a 9-digit account number unique per currency."""
    for _ in range(100):
        num = "0" + str(secrets.randbelow(900000000) + 100000000)
        exists = database.fetchone(
            "SELECT id FROM accounts WHERE account_number=? AND currency=?",
            (num, currency))
        if not exists:
            return num
    raise RuntimeError("Could not generate unique account number")


# ── Money formatting ─────────────────────────────────────────────────────

def _to_display(amount_cents: int, currency: str) -> str:
    if currency == "USD":
        return f"{amount_cents / 100:.2f}"
    return str(amount_cents)  # KHR stored as whole riel


def _to_cents(amount_str: str, currency: str) -> int:
    try:
        val = float(amount_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if val <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if currency == "USD":
        return int(round(val * 100))
    return int(round(val))


# ── Pydantic models ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    password: str = Field(..., min_length=4, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    phone: str
    password: str


class TransferRequest(BaseModel):
    to_phone: Optional[str] = None
    to_account: Optional[str] = None
    amount: str
    currency: str = Field("USD", pattern="^(USD|KHR)$")
    description: Optional[str] = Field(None, max_length=500)


# ── Auth endpoints ───────────────────────────────────────────────────────

@router.post("/auth/register")
def register(body: RegisterRequest):
    """Register a new customer with phone + password."""
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    existing = database.fetchone(
        "SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if existing:
        raise HTTPException(status_code=409, detail="Phone number already registered")

    pw_hash, salt = _hash_password(body.password)

    # Generate a pseudo telegram_id for web-registered users (start from 9000000000)
    row = database.fetchone(
        "SELECT MAX(telegram_id) as mx FROM customers WHERE telegram_id >= 9000000000")
    next_id = (row["mx"] or 9000000000) + 1 if row and row["mx"] else 9000000001

    tid = database.execute(
        """INSERT INTO customers
           (telegram_id, phone, first_name, last_name, password_hash, password_salt,
            role, is_active, web_registered, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'customer', 1, 1, datetime('now'), datetime('now'))""",
        (next_id, phone, body.first_name or "", body.last_name or "", pw_hash, salt))

    # Create USD and KHR accounts
    usd_acct = _generate_account_number("USD")
    khr_acct = _generate_account_number("KHR")
    database.execute(
        "INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'USD', 0, 'active', 'wallet')",
        (next_id, usd_acct))
    database.execute(
        "INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'KHR', 0, 'active', 'wallet')",
        (next_id, khr_acct))

    token = _create_client_token(next_id)
    return {
        "ok": True,
        "token": token,
        "customer": {
            "telegram_id": next_id,
            "phone": phone,
            "first_name": body.first_name or "",
            "last_name": body.last_name or "",
        },
        "accounts": [
            {"account_number": usd_acct, "currency": "USD", "balance": "0.00"},
            {"account_number": khr_acct, "currency": "KHR", "balance": "0"},
        ],
    }


@router.post("/auth/login")
def login(body: LoginRequest):
    """Login with phone + password, returns JWT."""
    phone = body.phone.strip()
    row = database.fetchone(
        """SELECT telegram_id, phone, first_name, last_name, password_hash, password_salt, is_active
           FROM customers WHERE phone=?""", (phone,))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Account is banned")
    if not row["password_hash"]:
        raise HTTPException(status_code=401, detail="Account not registered with password")
    if not _verify_password(body.password, row["password_hash"], row["password_salt"] or ""):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    token = _create_client_token(row["telegram_id"])
    return {
        "ok": True,
        "token": token,
        "customer": {
            "telegram_id": row["telegram_id"],
            "phone": row["phone"],
            "first_name": row["first_name"] or "",
            "last_name": row["last_name"] or "",
        },
    }


# ── Accounts endpoint ────────────────────────────────────────────────────

@router.get("/accounts")
def list_accounts(tid: int = Depends(get_current_user)):
    """List caller's accounts with balances."""
    rows = database.fetchall(
        """SELECT a.id, a.account_number, a.currency, a.balance, a.status, a.type, a.created_at
           FROM accounts a WHERE a.customer_id=? ORDER BY a.currency DESC""", (tid,))
    accounts = []
    for r in rows:
        accounts.append({
            "id": r["id"],
            "account_number": r["account_number"],
            "currency": r["currency"],
            "balance": _to_display(r["balance"], r["currency"]),
            "balance_raw": r["balance"],
            "status": r["status"],
            "type": r["type"],
        })
    return {"ok": True, "accounts": accounts}


# ── Transfer endpoint ────────────────────────────────────────────────────

@router.post("/transfer")
def transfer(body: TransferRequest, tid: int = Depends(get_current_user)):
    """Transfer money by recipient phone or account number."""
    if not body.to_phone and not body.to_account:
        raise HTTPException(status_code=400, detail="Must specify to_phone or to_account")

    amount_cents = _to_cents(body.amount, body.currency)

    # Find sender's account in the currency
    sender_acct = database.fetchone(
        "SELECT id, account_number, balance, status FROM accounts WHERE customer_id=? AND currency=?",
        (tid, body.currency))
    if not sender_acct:
        raise HTTPException(status_code=400, detail=f"No {body.currency} account found")
    if sender_acct["status"] != "active":
        raise HTTPException(status_code=400, detail="Your account is not active")
    if sender_acct["balance"] < amount_cents:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Find recipient
    recipient_acct = None
    recipient_tid = None
    if body.to_account:
        recipient_acct = database.fetchone(
            """SELECT a.id, a.account_number, a.balance, a.customer_id, a.status, a.currency
               FROM accounts a WHERE a.account_number=? AND a.currency=?""",
            (body.to_account.strip(), body.currency))
    elif body.to_phone:
        recipient_acct = database.fetchone(
            """SELECT a.id, a.account_number, a.balance, a.customer_id, a.status, a.currency
               FROM accounts a
               JOIN customers c ON c.telegram_id = a.customer_id
               WHERE c.phone=? AND a.currency=? AND c.is_active=1""",
            (body.to_phone.strip(), body.currency))

    if not recipient_acct:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient_acct["status"] != "active":
        raise HTTPException(status_code=400, detail="Recipient account is not active")
    if recipient_acct["customer_id"] == tid:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself")

    recipient_tid = recipient_acct["customer_id"]
    ref_id = "TXN" + str(int(time.time() * 1000))[-10:]

    # Execute transfer in a transaction
    with database.get_conn() as conn:
        # Deduct from sender
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now') WHERE id=?",
            (amount_cents, sender_acct["id"]))
        # Add to recipient
        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id=?",
            (amount_cents, recipient_acct["id"]))
        # Record transaction
        conn.execute(
            """INSERT INTO transactions
               (from_account_id, to_account_id, amount, currency, type, status, description, reference_id, created_at)
               VALUES (?, ?, ?, ?, 'transfer', 'completed', ?, ?, datetime('now'))""",
            (sender_acct["id"], recipient_acct["id"], amount_cents, body.currency,
             body.description or "Transfer", ref_id))

    return {
        "ok": True,
        "reference_id": ref_id,
        "amount": _to_display(amount_cents, body.currency),
        "currency": body.currency,
        "from_account": sender_acct["account_number"],
        "to_account": recipient_acct["account_number"],
        "to_customer_id": recipient_tid,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Transactions endpoint ────────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(
    tid: int = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
):
    """Get caller's transaction history."""
    limit = min(max(limit, 1), 100)
    rows = database.fetchall(
        """SELECT t.id, t.from_account_id, t.to_account_id, t.amount, t.currency,
                  t.type, t.status, t.description, t.reference_id, t.created_at,
                  fa.account_number as from_num, ta.account_number as to_num,
                  fc.phone as from_phone, tc.phone as to_phone,
                  fc.first_name as from_name, tc.first_name as to_name
           FROM transactions t
           LEFT JOIN accounts fa ON fa.id = t.from_account_id
           LEFT JOIN accounts ta ON ta.id = t.to_account_id
           LEFT JOIN customers fc ON fc.telegram_id = fa.customer_id
           LEFT JOIN customers tc ON tc.telegram_id = ta.customer_id
           WHERE fa.customer_id = ? OR ta.customer_id = ?
           ORDER BY t.created_at DESC
           LIMIT ? OFFSET ?""",
        (tid, tid, limit, offset))

    total = database.fetchone(
        """SELECT COUNT(*) as cnt FROM transactions t
           LEFT JOIN accounts fa ON fa.id = t.from_account_id
           LEFT JOIN accounts ta ON ta.id = t.to_account_id
           WHERE fa.customer_id = ? OR ta.customer_id = ?""",
        (tid, tid))["cnt"]

    txns = []
    for r in rows:
        direction = "out" if r["from_num"] and _is_sender(r, tid) else "in"
        txns.append({
            "id": r["id"],
            "direction": direction,
            "type": r["type"],
            "amount": _to_display(r["amount"], r["currency"]),
            "amount_raw": r["amount"],
            "currency": r["currency"],
            "status": r["status"],
            "description": r["description"] or "",
            "reference_id": r["reference_id"] or "",
            "from_account": r["from_num"] or "",
            "to_account": r["to_num"] or "",
            "from_name": r["from_name"] or r["from_phone"] or "",
            "to_name": r["to_name"] or r["to_phone"] or "",
            "created_at": r["created_at"],
        })

    return {"ok": True, "transactions": txns, "total": total, "limit": limit, "offset": offset}


def _is_sender(row, tid: int) -> bool:
    """Helper: check if this customer is the sender of a transaction."""
    # We need to check if the from account belongs to this customer
    acct = database.fetchone(
        "SELECT customer_id FROM accounts WHERE id=?", (row["from_account_id"],))
    return acct and acct["customer_id"] == tid
