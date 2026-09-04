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
import json
import os
import secrets
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt as pyjwt

import qrcode
import sqlite3
from app import database
from app.config import get_settings
from app.services.notification_client import send_transfer_notification_via_service, get_notification_client

# Telegram Bot Token for notifications
TELEGRAM_BOT_TOKEN = "8845776726:AAEq_KtXjFT-CJxz5ugq1r8GdJXWkSgtfoI"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

router = APIRouter(prefix="/api/client", tags=["client"])
compat_router = APIRouter(prefix="/api", tags=["compat"])

# ── Hash generator (8 chars, uppercase letters + digits) ───────────────────

def _generate_hash(length: int = 8) -> str:
    """Generate a random hash string with uppercase letters and digits."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(secrets.choice(chars) for _ in range(length))

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
    expire = datetime.now().timestamp() + CLIENT_TOKEN_EXPIRE_HOURS * 3600
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
        num = "0" + str(secrets.randbelow(90000000) + 10000000)
        exists = database.fetchone(
            "SELECT id FROM accounts WHERE account_number=? AND currency=?",
            (num, currency))
        if not exists:
            return num
    raise RuntimeError("Could not generate unique account number")


def _generate_bakong_qr(customer_id: str, account_number: str, currency: str, merchant_name: str = "", qr_type: str = "user", referrer: str = "") -> dict:
    """Generate a BAKONG QR code for a customer account."""
    qr_data_obj = {"bank": "WING", "account": account_number, "name": merchant_name or account_number, "currency": currency, "type": "bakong_qr", "qr_type": qr_type}
    if referrer:
        qr_data_obj["referrer"] = referrer
    qr_data = json.dumps(qr_data_obj)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    from pathlib import Path
    # Store BAKONG QR images under the repo deploy directory in dev/test runs so
    # the process does not require writing to /var/www (which needs root).
    img_dir = Path(__file__).resolve().parent.parent.parent / "deploy" / "bakong-qr"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_filename = f"{customer_id}_{currency.lower()}.png"
    img.save(str(img_dir / img_filename))
    # Expose a relative URL path that mirrors the production layout. In dev
    # deployments the static server (or admin) should serve deploy/bakong-qr.
    qr_path = f"/qr-images/{img_filename}"
    # Try inserting the QR record; if the bakong_qr table is missing create it and retry.
    try:
        database.execute(
            "INSERT OR REPLACE INTO bakong_qr (customer_id, account_number, currency, merchant_name, qr_data, qr_image_path, qr_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '+7 hours'))",
            (customer_id, account_number, currency, merchant_name, qr_data, qr_path, qr_type))
    except sqlite3.OperationalError as e:
        # Likely no such table; create it and retry once.
        database.execute(
            "CREATE TABLE IF NOT EXISTS bakong_qr (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, account_number TEXT, currency TEXT, merchant_name TEXT, qr_data TEXT, qr_image_path TEXT, qr_type TEXT, created_at TEXT)"
        )
        database.execute(
            "INSERT OR REPLACE INTO bakong_qr (customer_id, account_number, currency, merchant_name, qr_data, qr_image_path, qr_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '+7 hours'))",
            (customer_id, account_number, currency, merchant_name, qr_data, qr_path, qr_type))
    return {"account_number": account_number, "currency": currency, "merchant_name": merchant_name, "qr_data": qr_data, "qr_image_url": qr_path, "qr_type": qr_type}


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


# ── Telegram notification helper ─────────────────────────────────────────

def _send_telegram_notification_sync(chat_id: int, text: str) -> tuple[bool, str]:
    """Send Telegram message synchronously, return (success, error_message)."""
    try:
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{TELEGRAM_API_URL}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("ok"):
            return True, ""
        return False, result.get("description", "Unknown error")
    except Exception as e:
        return False, str(e)


def _record_failed_notification(recipient_phone: str, recipient_account: str,
                                 recipient_telegram_id: int, amount_cents: int,
                                 currency: str, from_account: str, ref_id: str,
                                 description: str, error_message: str):
    """Record a failed notification for later retry."""
    try:
        database.execute(
            """INSERT INTO failed_notifications
               (recipient_phone, recipient_account, recipient_telegram_id, amount, currency,
                from_account, reference_id, description, error_message, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (recipient_phone, recipient_account, recipient_telegram_id, amount_cents,
             currency, from_account, ref_id, description, error_message))
    except Exception:
        pass


def _send_transfer_notification(chat_id: int, amount_cents: int, currency: str,
                                from_account: str, to_name: str, to_account: str,
                                ref_id: str, description: str = "",
                                channel: str = "Wing bank",
                                recipient_phone: str = ""):
    """Send transfer notification using standard template. Record if fails."""
    amount_str = _to_display(amount_cents, currency)
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    short_hash = ref_id[-6:] if len(ref_id) >= 6 else ref_id

    desc_line = f"Description: Channel: {channel} | Hash: {short_hash}"
    if description:
        desc_line += f" | {description}"

    text = (
        f"✅ Transaction Successful\n\n"
        f"Type: Transfer\n\n"
        f"Amount: {amount_str} {currency}\n\n"
        f"From: {from_account}\n\n"
        f"To: {to_name} — {to_account}\n"
        f"{desc_line}\n\n"
        f"Date: {now_str}"
    )

    # Check if we have a valid Telegram ID
    if not chat_id or chat_id >= 9000000000:
        _record_failed_notification(
            recipient_phone=recipient_phone,
            recipient_account=to_account,
            recipient_telegram_id=chat_id or 0,
            amount_cents=amount_cents,
            currency=currency,
            from_account=from_account,
            ref_id=ref_id,
            description=description,
            error_message="No valid Telegram ID (web-registered user or unknown)"
        )
        return

    # Try to send
    success, error = _send_telegram_notification_sync(chat_id, text)
    if not success:
        _record_failed_notification(
            recipient_phone=recipient_phone,
            recipient_account=to_account,
            recipient_telegram_id=chat_id,
            amount_cents=amount_cents,
            currency=currency,
            from_account=from_account,
            ref_id=ref_id,
            description=description,
            error_message=error
        )


# ── Pydantic models ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    password: str = Field(..., min_length=4, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    referrer: Optional[str] = Field(None, max_length=50)  # 推荐码或上级ID
    pin: Optional[str] = Field(None, min_length=4, max_length=6)  # 支付PIN，注册时可选设置


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
    phone = _normalize_phone(body.phone)
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

    # Resolve referrer (parent admin)
    parent_id = None
    if body.referrer:
        ref = database.fetchone(
            "SELECT telegram_id FROM customers WHERE referrer_code=? OR telegram_id=? OR phone=?",
            (body.referrer, body.referrer, body.referrer))
        if ref:
            parent_id = str(ref["telegram_id"])

    # Generate referrer code for new user
    import uuid as _uuid
    user_referrer_code = "W" + _uuid.uuid4().hex[:6].upper()

    tid = database.execute(
        """INSERT INTO customers
           (telegram_id, phone, first_name, last_name, password_hash, password_salt,
            role, is_active, web_registered, parent_id, referrer_code, qr_type, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'customer', 1, 1, ?, ?, 'user', datetime('now', '+7 hours'), datetime('now', '+7 hours'))""",
        (next_id, phone, body.first_name or "", body.last_name or "", pw_hash, salt, parent_id, user_referrer_code))

    # Create USD and KHR accounts
    usd_acct = _generate_account_number("USD")
    khr_acct = _generate_account_number("KHR")
    database.execute(
        "INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'USD', 0, 'active', 'wallet')",
        (next_id, usd_acct))
    database.execute(
        "INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'KHR', 0, 'active', 'wallet')",
        (next_id, khr_acct))

    # Generate BAKONG QR codes for new user (using registration name)
    merchant_name = f"{body.first_name or ''} {body.last_name or ''}".strip() or usd_acct
    usd_qr = _generate_bakong_qr(str(next_id), usd_acct, "USD", merchant_name, "user", user_referrer_code)
    khr_qr = _generate_bakong_qr(str(next_id), khr_acct, "KHR", merchant_name, "user", user_referrer_code)

    # Set payment PIN if provided during registration
    pin_set = False
    if body.pin and body.pin.isdigit() and 4 <= len(body.pin) <= 6:
        pin_hash, pin_salt = _hash_password(body.pin)
        database.execute(
            "UPDATE customers SET payment_pin_hash=?, payment_pin_salt=?, payment_pin_set_at=datetime('now', '+7 hours') WHERE telegram_id=?",
            (pin_hash, pin_salt, next_id))
        pin_set = True

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
        "bakong_qr": {"USD": usd_qr, "KHR": khr_qr},
        "parent_id": parent_id,
        "referrer_code": user_referrer_code,
        "pin_set": pin_set,
    }


@router.get("/bakong-qr")
def get_bakong_qr(phone: str = "", customer_id: str = ""):
    """Get BAKONG QR codes for a customer by phone or customer_id."""
    if not phone and not customer_id:
        raise HTTPException(status_code=400, detail="phone or customer_id is required")
    if phone:
        customer = database.fetchone("SELECT telegram_id, first_name, last_name FROM customers WHERE phone=?", (phone,))
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        cid = str(customer["telegram_id"])
    else:
        cid = customer_id
        customer = database.fetchone("SELECT telegram_id, first_name, last_name FROM customers WHERE telegram_id=?", (cid,))
    rows = database.fetchall("SELECT * FROM bakong_qr WHERE customer_id=?", (cid,))
    if not rows:
        accounts = database.fetchall("SELECT account_number, currency FROM accounts WHERE customer_id=?", (cid,))
        merchant_name = f"{customer['first_name'] or ''} {customer['last_name'] or ''}".strip() if customer else cid
        result = {}
        for acct in accounts:
            result[acct["currency"]] = _generate_bakong_qr(cid, acct["account_number"], acct["currency"], merchant_name)
        return {"ok": True, "bakong_qr": result}
    result = {}
    for row in rows:
        result[row["currency"]] = {"account_number": row["account_number"], "currency": row["currency"], "merchant_name": row["merchant_name"], "qr_data": row["qr_data"], "qr_image_url": row["qr_image_path"]}
    return {"ok": True, "bakong_qr": result}


class CreateAdminRequest(BaseModel):
    phone: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    parent_id: Optional[str] = None  # 上级管理ID，默认为主二维码
    referrer_code: Optional[str] = None


@router.post("/admin/create")
def create_admin_account(body: CreateAdminRequest):
    """Create a management account (admin QR type)."""
    # Check if phone exists
    existing = database.fetchone("SELECT telegram_id FROM customers WHERE phone=?", (body.phone,))
    if existing:
        raise HTTPException(status_code=409, detail="Phone number already registered")

    # Generate admin ID
    row = database.fetchone("SELECT MAX(telegram_id) as mx FROM customers WHERE telegram_id >= 8000000000")
    next_id = (row["mx"] or 8000000000) + 1 if row and row["mx"] else 8000000001

    pw_hash, salt = _hash_password(body.password)
    parent = body.parent_id or "MASTER001"
    admin_referrer = body.referrer_code or "A" + str(next_id)[-6:]

    database.execute(
        """INSERT INTO customers (telegram_id, phone, first_name, last_name, password_hash, password_salt,
           role, is_active, web_registered, parent_id, referrer_code, qr_type, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'admin', 1, 1, ?, ?, 'admin', datetime('now', '+7 hours'), datetime('now', '+7 hours'))""",
        (next_id, body.phone, body.first_name or "", body.last_name or "", pw_hash, salt, parent, admin_referrer))

    # Create accounts
    usd_acct = _generate_account_number("USD")
    khr_acct = _generate_account_number("KHR")
    database.execute("INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'USD', 0, 'active', 'wallet')", (next_id, usd_acct))
    database.execute("INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, 'KHR', 0, 'active', 'wallet')", (next_id, khr_acct))

    # Generate admin QR codes
    merchant_name = f"{body.first_name or ''} {body.last_name or ''}".strip() or usd_acct
    usd_qr = _generate_bakong_qr(str(next_id), usd_acct, "USD", merchant_name, "admin", admin_referrer)
    khr_qr = _generate_bakong_qr(str(next_id), khr_acct, "KHR", merchant_name, "admin", admin_referrer)

    return {"ok": True, "admin_id": next_id, "phone": body.phone, "referrer_code": admin_referrer, "parent_id": parent, "accounts": [{"account_number": usd_acct, "currency": "USD"}, {"account_number": khr_acct, "currency": "KHR"}], "bakong_qr": {"USD": usd_qr, "KHR": khr_qr}}


@router.get("/hierarchy")
def get_hierarchy(customer_id: str = "", phone: str = ""):
    """Get referral hierarchy tree for a customer."""
    if not customer_id and not phone:
        raise HTTPException(status_code=400, detail="customer_id or phone is required")
    if phone:
        c = database.fetchone("SELECT telegram_id FROM customers WHERE phone=?", (phone,))
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")
        cid = str(c["telegram_id"])
    else:
        cid = customer_id

    # Get direct referrals
    referrals = database.fetchall("SELECT telegram_id, first_name, last_name, phone, qr_type, referrer_code, created_at FROM customers WHERE parent_id=? ORDER BY created_at", (cid,))
    return {"ok": True, "customer_id": cid, "referrals": [dict(r) for r in referrals], "referral_count": len(referrals)}


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


# ── Failed Notification Management API ───────────────────────────────────

class RetryNotificationRequest(BaseModel):
    telegram_id: int


@router.get("/failed-notifications")
def list_failed_notifications(status: str = "pending"):
    """List failed/pending notifications for admin review."""
    rows = database.fetchall(
        """SELECT * FROM failed_notifications WHERE status=? ORDER BY created_at DESC LIMIT 100""",
        (status,))
    return {"ok": True, "notifications": [dict(r) for r in rows]}


@router.post("/failed-notifications/{notification_id}/retry")
def retry_failed_notification(notification_id: int, body: RetryNotificationRequest):
    """Retry sending a failed notification with provided Telegram ID."""
    row = database.fetchone(
        "SELECT * FROM failed_notifications WHERE id=?", (notification_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    if row["status"] == "sent":
        return {"ok": True, "message": "Already sent"}

    # Update customer's telegram_id if needed (skip if already exists)
    if row["recipient_phone"]:
        existing = database.fetchone(
            "SELECT telegram_id FROM customers WHERE phone=?", (row["recipient_phone"],))
        if existing and (not existing["telegram_id"] or existing["telegram_id"] >= 9000000000):
            # Check if target telegram_id already exists
            tid_exists = database.fetchone(
                "SELECT telegram_id FROM customers WHERE telegram_id=?", (body.telegram_id,))
            if not tid_exists:
                database.execute(
                    "UPDATE customers SET telegram_id=? WHERE phone=?",
                    (body.telegram_id, row["recipient_phone"]))

    # Build and send notification
    amount_str = _to_display(row["amount"], row["currency"])
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    short_hash = row["reference_id"][-6:] if len(row["reference_id"]) >= 6 else row["reference_id"]

    # Get recipient name
    cust = database.fetchone(
        "SELECT first_name, last_name FROM customers WHERE phone=?", (row["recipient_phone"],))
    to_name = " ".join(filter(None, [cust["first_name"] or "", cust["last_name"] or ""])) if cust else "Unknown"

    desc_line = f"Description: Channel: Wing bank | Hash: {short_hash}"
    if row["description"]:
        desc_line += f" | {row['description']}"

    text = (
        f"✅ Transaction Successful\n\n"
        f"Type: Transfer\n\n"
        f"Amount: {amount_str} {row['currency']}\n\n"
        f"From: {row['from_account']}\n\n"
        f"To: {to_name} — {row['recipient_account']}\n"
        f"{desc_line}\n\n"
        f"Date: {now_str}"
    )

    success, error = _send_telegram_notification_sync(body.telegram_id, text)
    if success:
        database.execute(
            "UPDATE failed_notifications SET status='sent', sent_at=datetime('now', '+7 hours'), recipient_telegram_id=? WHERE id=?",
            (body.telegram_id, notification_id))
        return {"ok": True, "message": "Notification sent successfully"}
    else:
        database.execute(
            "UPDATE failed_notifications SET error_message=? WHERE id=?",
            (error, notification_id))
        raise HTTPException(status_code=500, detail=f"Send failed: {error}")



def _normalize_phone(phone: str) -> str:
    """Normalize phone number: remove non-digits, strip 855 country code and leading 0."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("855") and len(digits) > 9:
        digits = digits[3:]
    if digits.startswith("0") and len(digits) > 8:
        digits = digits[1:]
    return digits


# ── Frontend compatibility APIs (used by Wing Bank web app) ────────────────

@router.get("/accounts/balance")
@compat_router.get("/accounts/balance")
def frontend_account_balance(phone: str = ""):
    """Get account balance by phone (frontend compatibility)."""
    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    cust = database.fetchone(
        "SELECT telegram_id, phone, first_name, last_name FROM customers WHERE phone=?", (phone,))
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    accounts = database.fetchall(
        "SELECT id, account_number, currency, balance, status, type FROM accounts WHERE customer_id=?", (cust["telegram_id"],))
    return {
        "ok": True,
        "customer": {"phone": cust["phone"], "name": " ".join(filter(None, [cust["first_name"] or "", cust["last_name"] or ""]))},
        "accounts": [{"id": a["id"], "account_number": a["account_number"], "currency": a["currency"], "balance": _to_display(a["balance"], a["currency"]), "status": a["status"], "type": a["type"]} for a in accounts],
        "byAccount": {
            **{a["account_number"]: (float(a["balance"]) / 100.0 if a["currency"] == "USD" else float(a["balance"])) for a in accounts},
            **{a["account_number"].replace(" ", ""): (float(a["balance"]) / 100.0 if a["currency"] == "USD" else float(a["balance"])) for a in accounts},
        },
    }


@router.get("/accounts/transactions")
def frontend_account_transactions(phone: str = "", limit: int = 50):
    """Get transaction history by phone (frontend compatibility)."""
    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    cust = database.fetchone("SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    accts = database.fetchall(
        "SELECT id, account_number FROM accounts WHERE customer_id=?", (cust["telegram_id"],))
    acct_ids = [a["id"] for a in accts]
    if not acct_ids:
        return {"ok": True, "transactions": []}
    placeholders = ",".join("?" * len(acct_ids))
    txs = database.fetchall(
        f"SELECT * FROM transactions WHERE from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}) ORDER BY id DESC LIMIT ?",
        (*acct_ids, *acct_ids, limit))
    
    # Add account numbers to transactions for frontend display
    acct_id_to_num = {a["id"]: a["account_number"] for a in accts}
    result = []
    for t in txs:
        td = dict(t)
        td["from_account"] = acct_id_to_num.get(td.get("from_account_id"), "")
        td["to_account"] = acct_id_to_num.get(td.get("to_account_id"), "")
        result.append(td)
    
    return {"ok": True, "transactions": result}
@router.get("/profile")
def get_user_profile(phone: str = ""):
    """Get user profile by phone (frontend compatibility)."""
    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    cust = database.fetchone(
        "SELECT telegram_id, phone, first_name, last_name, email, role, is_active, created_at, updated_at FROM customers WHERE phone=?",
        (phone,))
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")

    kyc = database.fetchone(
        "SELECT status, full_name, document_number, document_type, date_of_birth, address, "
        "last_name_kh, first_name_kh, last_name_en, first_name_en, gender, nationality, "
        "pob_province, pob_district, pob_commune, pob_village, customer_tier, marital_status, id_expiry "
        "FROM kyc_records WHERE customer_id=? ORDER BY id DESC LIMIT 1",
        (cust["telegram_id"],))

    accounts = database.fetchall(
        "SELECT account_number, currency, balance, status FROM accounts WHERE customer_id=?",
        (cust["telegram_id"],))

    return {
        "ok": True,
        "profile": {
            "telegram_id": cust["telegram_id"],
            "phone": cust["phone"],
            "first_name": cust["first_name"] or "",
            "last_name": cust["last_name"] or "",
            "full_name": " ".join(filter(None, [cust["first_name"] or "", cust["last_name"] or ""])),
            "email": cust["email"] or "",
            "role": cust["role"],
            "is_active": bool(cust["is_active"]),
            "created_at": cust["created_at"],
            "updated_at": cust["updated_at"],
            "registration_date": cust["created_at"],
            "registration_phone": cust["phone"],
            "kyc_status": kyc["status"] if kyc else "none",
            "kyc_full_name": kyc["full_name"] if kyc else "",
            "kyc_document_number": kyc["document_number"] if kyc else "",
            "kyc_document_type": kyc["document_type"] if kyc else "",
            "kyc_date_of_birth": kyc["date_of_birth"] if kyc else "",
            "kyc_address": kyc["address"] if kyc else "",
            "kyc_last_name_kh": kyc["last_name_kh"] if kyc else "",
            "kyc_first_name_kh": kyc["first_name_kh"] if kyc else "",
            "kyc_last_name_en": kyc["last_name_en"] if kyc else "",
            "kyc_first_name_en": kyc["first_name_en"] if kyc else "",
            "kyc_gender": kyc["gender"] if kyc else "",
            "kyc_nationality": kyc["nationality"] if kyc else "",
            "kyc_pob_province": kyc["pob_province"] if kyc else "",
            "kyc_pob_district": kyc["pob_district"] if kyc else "",
            "kyc_pob_commune": kyc["pob_commune"] if kyc else "",
            "kyc_pob_village": kyc["pob_village"] if kyc else "",
            "customer_tier": kyc["customer_tier"] if kyc else "",
            "marital_status": kyc["marital_status"] if kyc else "",
            "id_expiry": kyc["id_expiry"] if kyc else "",
        },
        "accounts": [{"account_number": a["account_number"], "currency": a["currency"], "balance": _to_display(a["balance"], a["currency"]), "status": a["status"]} for a in accounts],
    }


@router.post("/transfer")
def frontend_transfer(body: dict):
    """Transfer money by phone (frontend compatibility - no token required)."""
    phone = body.get("phone", "")
    to_account = body.get("to_account", "")
    to_phone = body.get("to_phone", "")
    amount = body.get("amount", "0")
    currency = body.get("currency", "USD")
    description = body.get("description", "")

    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    if not to_account and not to_phone:
        raise HTTPException(status_code=400, detail="Must specify to_phone or to_account")

    # Find sender
    sender = database.fetchone(
        "SELECT telegram_id, payment_pin_hash, payment_pin_salt FROM customers WHERE phone=?", (phone,))
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    tid = sender["telegram_id"]

    # Optional: verify payment PIN if provided by frontend
    pin = body.get("pin", "")
    if pin:
        _validate_pin_format(pin)
        if not sender["payment_pin_hash"]:
            raise HTTPException(status_code=400, detail="Payment PIN not set. Please set PIN first.")
        if not _verify_password(pin, sender["payment_pin_hash"], sender["payment_pin_salt"] or ""):
            raise HTTPException(status_code=401, detail="Incorrect payment PIN")

    amount_cents = _to_cents(amount, currency)

    # Find sender's account
    sender_acct = database.fetchone(
        "SELECT id, account_number, balance, status FROM accounts WHERE customer_id=? AND currency=?",
        (tid, currency))
    if not sender_acct:
        raise HTTPException(status_code=400, detail=f"No {currency} account found")
    if sender_acct["status"] != "active":
        raise HTTPException(status_code=400, detail="Your account is not active")
    if sender_acct["balance"] < amount_cents:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Find recipient
    recipient_acct = None
    if to_account:
        recipient_acct = database.fetchone(
            """SELECT a.id, a.account_number, a.balance, a.customer_id, a.status, a.currency
               FROM accounts a WHERE a.account_number=? AND a.currency=?""",
            (to_account.strip(), currency))
    elif to_phone:
        to_phone_norm = _normalize_phone(to_phone)
        recipient_acct = database.fetchone(
            """SELECT a.id, a.account_number, a.balance, a.customer_id, a.status, a.currency
               FROM accounts a
               JOIN customers c ON c.telegram_id = a.customer_id
               WHERE c.phone=? AND a.currency=? AND c.is_active=1""",
            (to_phone_norm, currency))

    if not recipient_acct:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient_acct["status"] != "active":
        raise HTTPException(status_code=400, detail="Recipient account is not active")
    if recipient_acct["id"] == sender_acct["id"]:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account")

    recipient_tid = recipient_acct["customer_id"]
    ref_id = _generate_hash(8)

    # Execute transfer
    with database.get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now', '+7 hours') WHERE id=?",
            (amount_cents, sender_acct["id"]))
        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now', '+7 hours') WHERE id=?",
            (amount_cents, recipient_acct["id"]))
        conn.execute(
            """INSERT INTO transactions
               (from_account_id, to_account_id, amount, currency, type, status, description, reference_id, created_at)
               VALUES (?, ?, ?, ?, 'transfer', 'completed', ?, ?, datetime('now', '+7 hours'))""",
            (sender_acct["id"], recipient_acct["id"], amount_cents, currency,
             description or "Transfer", ref_id))

    # Send notification to recipient via notification-service
    try:
        recipient_cust = database.fetchone(
            "SELECT telegram_id, first_name, last_name, phone FROM customers WHERE telegram_id=?",
            (recipient_tid,))
        if recipient_cust:
            to_name = " ".join(filter(None, [recipient_cust["first_name"] or "", recipient_cust["last_name"] or ""])) or "Customer"
            # Try notification-service first, fall back to direct Telegram
            notified = send_transfer_notification_via_service(
                customer_id=str(recipient_tid),
                amount_str=_to_display(amount_cents, currency),
                currency=currency,
                from_account=sender_acct["account_number"],
                to_name=to_name,
                to_account=recipient_acct["account_number"],
                ref_id=ref_id,
                description=description,
                channel="Wing bank",
                bot_type="wing",
            )
            if not notified:
                # Fall back to direct Telegram notification
                _send_transfer_notification(
                    chat_id=recipient_tid,
                    amount_cents=amount_cents,
                    currency=currency,
                    from_account=sender_acct["account_number"],
                    to_name=to_name,
                    to_account=recipient_acct["account_number"],
                    ref_id=ref_id,
                    description=description,
                    channel="Wing bank",
                    recipient_phone=recipient_cust["phone"],
                )
    except Exception as e:
        # Never fail the transfer because of notification issues
        import logging
        logging.getLogger(__name__).warning("Transfer notification failed: %s", e)

    return {
        "ok": True,
        "reference_id": ref_id,
        "amount": _to_display(amount_cents, currency),
        "currency": currency,
        "from_account": sender_acct["account_number"],
        "to_account": recipient_acct["account_number"],
        "status": "completed",
    }


@router.post("/qr-payment")
def frontend_qr_payment(body: dict):
    """Record QR payment transaction (can be to external accounts)."""
    phone = body.get("phone", "")
    amount = body.get("amount", "0")
    currency = body.get("currency", "USD")
    description = body.get("description", "QR Payment")
    payee_name = body.get("payee_name", "")
    payee_account = body.get("payee_account", "")
    payee_bank = body.get("payee_bank", "")
    reference_id = body.get("reference_id", "")

    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    # Find sender
    sender = database.fetchone(
        "SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    tid = sender["telegram_id"]

    amount_cents = _to_cents(amount, currency)

    # Find sender's account
    sender_acct = database.fetchone(
        "SELECT id, account_number, balance, status FROM accounts WHERE customer_id=? AND currency=?",
        (tid, currency))
    if not sender_acct:
        raise HTTPException(status_code=400, detail=f"No {currency} account found")
    if sender_acct["status"] != "active":
        raise HTTPException(status_code=400, detail="Your account is not active")
    if sender_acct["balance"] < amount_cents:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    ref_id = reference_id or _generate_hash(8)
    external_to = f"{payee_name} - {payee_account} - {payee_bank}" if payee_name else f"{payee_account} - {payee_bank}"

    # Deduct from sender and record transaction
    payee_internal = None
    with database.get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now', '+7 hours') WHERE id=?",
            (amount_cents, sender_acct["id"]))
        conn.execute(
            """INSERT INTO transactions
               (from_account_id, to_account_id, amount, currency, type, status, description, reference_id, external_to, created_at)
               VALUES (?, NULL, ?, ?, 'transfer', 'completed', ?, ?, ?, datetime('now', '+7 hours'))""",
            (sender_acct["id"], amount_cents, currency,
             description or "QR Payment", ref_id, external_to))

        # If payee is an internal user, add balance and create income transaction
        if payee_account:
            payee_acct = conn.execute(
                "SELECT id, account_number, customer_id, status FROM accounts WHERE account_number=? AND currency=?",
                (payee_account.strip(), currency)).fetchone()
            if payee_acct and payee_acct["customer_id"] and payee_acct["status"] == "active":
                payee_internal = dict(payee_acct)
                conn.execute(
                    "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now', '+7 hours') WHERE id=?",
                    (amount_cents, payee_acct["id"]))
                conn.execute(
                    """INSERT INTO transactions
                       (from_account_id, to_account_id, amount, currency, type, status, description, reference_id, external_to, created_at)
                       VALUES (NULL, ?, ?, ?, 'transfer', 'completed', ?, ?, ?, datetime('now', '+7 hours'))""",
                    (payee_acct["id"], amount_cents, currency,
                     description or "QR Payment", ref_id, external_to))

    # Send notification if payee is an internal user
    if payee_internal:
        try:
            payee_cust = database.fetchone(
                "SELECT telegram_id, first_name, last_name, phone FROM customers WHERE telegram_id=?",
                (payee_internal["customer_id"],))
            if payee_cust:
                to_name = " ".join(filter(None, [payee_cust["first_name"] or "", payee_cust["last_name"] or ""])) or "Customer"
                channel = payee_bank or "Wing bank"
                send_transfer_notification_via_service(
                    customer_id=str(payee_cust["telegram_id"]),
                    amount_str=_to_display(amount_cents, currency),
                    currency=currency,
                    from_account=sender_acct["account_number"],
                    to_name=to_name,
                    to_account=payee_internal["account_number"],
                    ref_id=ref_id,
                    description=description,
                    channel=channel,
                    bot_type="wing",
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("QR payment notification failed: %s", e)

    return {
        "ok": True,
        "reference_id": ref_id,
        "amount": _to_display(amount_cents, currency),
        "currency": currency,
        "from_account": sender_acct["account_number"],
        "status": "completed",
    }


# ── Telegram User Binding API (for notification-service) ─────────────────

class BindTelegramRequest(BaseModel):
    phone: str
    telegram_user_id: int
    chat_id: int
    bot_type: str = "wing"
    username: Optional[str] = None


@router.post("/telegram/bind")
def bind_telegram_id(body: BindTelegramRequest):
    """Bind a customer's Telegram ID for notifications.

    This registers the customer in the notification-service so that
    the worker can send proactive notifications.
    """
    phone = _normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    customer = database.fetchone(
        "SELECT telegram_id, phone, first_name, last_name FROM customers WHERE phone=?",
        (phone,))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Update customer's telegram_id if it's a web-registered placeholder
    if customer["telegram_id"] >= 9000000000:
        # Check if target telegram_id already exists
        existing = database.fetchone(
            "SELECT telegram_id FROM customers WHERE telegram_id=?",
            (body.telegram_user_id,))
        if not existing:
            database.execute(
                "UPDATE customers SET telegram_id=? WHERE phone=?",
                (body.telegram_user_id, phone))

    # Register in notification-service
    client = get_notification_client()
    result = client.register_telegram_user(
        customer_id=str(customer["telegram_id"]),
        telegram_user_id=body.telegram_user_id,
        chat_id=body.chat_id,
        bot_type=body.bot_type,
        username=body.username,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Notification service unavailable. Please ensure notification-service is running on port 9000.")

    return {
        "ok": True,
        "message": "Telegram ID bound successfully",
        "customer_id": str(customer["telegram_id"]),
        "telegram_user_id": body.telegram_user_id,
        "chat_id": body.chat_id,
        "bot_type": body.bot_type,
    }


@router.get("/telegram/bindings")
def get_telegram_bindings(phone: str = "", customer_id: str = ""):
    """Get Telegram bindings for a customer."""
    if not phone and not customer_id:
        raise HTTPException(status_code=400, detail="phone or customer_id is required")

    if phone:
        phone = _normalize_phone(phone)
        customer = database.fetchone(
            "SELECT telegram_id FROM customers WHERE phone=?", (phone,))
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        cid = str(customer["telegram_id"])
    else:
        cid = customer_id

    client = get_notification_client()
    bindings = client.get_telegram_users(customer_id=cid)

    if bindings is None:
        raise HTTPException(
            status_code=503,
            detail="Notification service unavailable.")

    return {"ok": True, "customer_id": cid, "bindings": bindings or []}


@router.post("/telegram/send-test")
def send_test_notification(body: dict):
    """Send a test notification to a customer."""
    phone = body.get("phone", "")
    message = body.get("message", "✅ Test notification from Wing Bank")
    bot_type = body.get("bot_type", "wing")

    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    customer = database.fetchone(
        "SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    client = get_notification_client()
    result = client.create_notification(
        customer_id=str(customer["telegram_id"]),
        bot_type=bot_type,
        message=message,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Notification service unavailable or customer has no active Telegram binding.")

    return {"ok": True, "message": "Notification queued", "notification": result}


# ═══════════════════════════════════════════════════════════════════════════
# Profile Update API
# ═══════════════════════════════════════════════════════════════════════════

class ProfileUpdateRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=200)


@router.post("/profile/update")
def update_profile(body: ProfileUpdateRequest):
    """Update customer profile (name, email). Frontend calls this after editing."""
    phone = _normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")

    customer = database.fetchone(
        "SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Build dynamic update
    sets = []
    params = []
    if body.first_name is not None:
        sets.append("first_name=?")
        params.append(body.first_name.strip())
    if body.last_name is not None:
        sets.append("last_name=?")
        params.append(body.last_name.strip())
    if body.email is not None:
        sets.append("email=?")
        params.append(body.email.strip())

    if not sets:
        return {"ok": True, "message": "No changes to apply"}

    sets.append("updated_at=datetime('now', '+7 hours')")
    params.append(customer["telegram_id"])

    database.execute(
        f"UPDATE customers SET {', '.join(sets)} WHERE telegram_id=?",
        tuple(params))

    # Return updated profile
    updated = database.fetchone(
        "SELECT telegram_id, phone, first_name, last_name, email, updated_at FROM customers WHERE telegram_id=?",
        (customer["telegram_id"],))
    return {
        "ok": True,
        "message": "Profile updated successfully",
        "profile": {
            "telegram_id": updated["telegram_id"],
            "phone": updated["phone"],
            "first_name": updated["first_name"] or "",
            "last_name": updated["last_name"] or "",
            "full_name": " ".join(filter(None, [updated["first_name"] or "", updated["last_name"] or ""])),
            "email": updated["email"] or "",
            "updated_at": updated["updated_at"],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Payment PIN API (set / verify / reset / forgot)
# ═══════════════════════════════════════════════════════════════════════════

class PinSetRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    pin: str = Field(..., min_length=4, max_length=6)


class PinVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    pin: str = Field(..., min_length=4, max_length=6)


class PinResetRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    new_pin: str = Field(..., min_length=4, max_length=6)
    # Optional: current pin for authenticated change; omit for forgot-password flow
    current_pin: Optional[str] = Field(None, min_length=4, max_length=6)


def _validate_pin_format(pin: str) -> None:
    """Validate PIN is 4-6 digits."""
    if not pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be numeric")
    if len(pin) < 4 or len(pin) > 6:
        raise HTTPException(status_code=400, detail="PIN must be 4-6 digits")


def _get_customer_by_phone(phone: str) -> dict:
    """Fetch customer by normalized phone or 404."""
    phone = _normalize_phone(phone)
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    customer = database.fetchone(
        "SELECT * FROM customers WHERE phone=?", (phone,))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/pin/set")
def set_payment_pin(body: PinSetRequest):
    """Set payment PIN for a customer (first-time setup)."""
    _validate_pin_format(body.pin)
    customer = _get_customer_by_phone(body.phone)

    if customer["payment_pin_hash"]:
        raise HTTPException(status_code=409, detail="PIN already set. Use /pin/reset to change.")

    pin_hash, pin_salt = _hash_password(body.pin)
    database.execute(
        "UPDATE customers SET payment_pin_hash=?, payment_pin_salt=?, payment_pin_set_at=datetime('now', '+7 hours'), updated_at=datetime('now', '+7 hours') WHERE telegram_id=?",
        (pin_hash, pin_salt, customer["telegram_id"]))

    return {"ok": True, "message": "Payment PIN set successfully"}


@router.post("/pin/verify")
def verify_payment_pin(body: PinVerifyRequest):
    """Verify payment PIN. Returns ok=true if correct, 401 if wrong."""
    _validate_pin_format(body.pin)
    customer = _get_customer_by_phone(body.phone)

    if not customer["payment_pin_hash"]:
        raise HTTPException(status_code=400, detail="PIN not set. Please set PIN first.")

    if not _verify_password(body.pin, customer["payment_pin_hash"], customer["payment_pin_salt"] or ""):
        raise HTTPException(status_code=401, detail="Incorrect PIN")

    return {"ok": True, "message": "PIN verified"}


@router.post("/pin/reset")
def reset_payment_pin(body: PinResetRequest):
    """Reset / change payment PIN.

    - If current_pin provided: verifies old PIN before changing (change flow).
    - If current_pin omitted: forgot-password flow (resets directly).
      In production, this should be gated behind OTP/email verification.
    """
    _validate_pin_format(body.new_pin)
    customer = _get_customer_by_phone(body.phone)

    # If current_pin provided, verify it first
    if body.current_pin is not None:
        _validate_pin_format(body.current_pin)
        if not customer["payment_pin_hash"]:
            raise HTTPException(status_code=400, detail="PIN not set")
        if not _verify_password(body.current_pin, customer["payment_pin_hash"], customer["payment_pin_salt"] or ""):
            raise HTTPException(status_code=401, detail="Current PIN is incorrect")

    pin_hash, pin_salt = _hash_password(body.new_pin)
    database.execute(
        "UPDATE customers SET payment_pin_hash=?, payment_pin_salt=?, payment_pin_set_at=datetime('now', '+7 hours'), updated_at=datetime('now', '+7 hours') WHERE telegram_id=?",
        (pin_hash, pin_salt, customer["telegram_id"]))

    return {"ok": True, "message": "Payment PIN reset successfully"}


@router.get("/pin/status")
def get_pin_status(phone: str = ""):
    """Check if payment PIN is set for a customer."""
    customer = _get_customer_by_phone(phone)
    return {
        "ok": True,
        "pin_set": bool(customer["payment_pin_hash"]),
        "pin_set_at": customer["payment_pin_set_at"] or "",
    }


# ═══════════════════════════════════════════════════════════════════════════
# KYC (Know Your Customer) Submission API
# ═══════════════════════════════════════════════════════════════════════════

class KYCSubmitRequest(BaseModel):
    phone: str = Field(..., min_length=4, max_length=20)
    document_type: Optional[str] = Field("national_id", max_length=50)
    document_number: Optional[str] = Field(None, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)
    date_of_birth: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    # Extended fields
    last_name_kh: Optional[str] = Field(None, max_length=100)
    first_name_kh: Optional[str] = Field(None, max_length=100)
    last_name_en: Optional[str] = Field(None, max_length=100)
    first_name_en: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=20)
    nationality: Optional[str] = Field(None, max_length=50)
    pob_province: Optional[str] = Field(None, max_length=100)
    pob_district: Optional[str] = Field(None, max_length=100)
    pob_commune: Optional[str] = Field(None, max_length=100)
    pob_village: Optional[str] = Field(None, max_length=100)
    customer_tier: Optional[str] = Field(None, max_length=50)
    marital_status: Optional[str] = Field(None, max_length=50)
    id_expiry: Optional[str] = Field(None, max_length=50)


@router.post("/kyc/submit")
def submit_kyc(body: KYCSubmitRequest):
    """Submit KYC verification documents for a customer.

    Creates or updates the kyc_records entry and sets customer.kyc_status='pending'.
    Admin can then review and approve/reject from /kyc.
    """
    customer = _get_customer_by_phone(body.phone)
    cid = customer["telegram_id"]

    # Determine full name
    full_name = body.full_name or " ".join(filter(None, [
        body.first_name_en or customer["first_name"] or "",
        body.last_name_en or customer["last_name"] or "",
    ])) or customer["phone"]

    # Check for existing KYC record
    existing = database.fetchone(
        "SELECT id FROM kyc_records WHERE customer_id=? ORDER BY id DESC LIMIT 1",
        (cid,))

    if existing:
        # Update existing record
        database.execute(
            """UPDATE kyc_records SET
               status='pending', document_type=?, document_number=?, full_name=?,
               date_of_birth=?, address=?, last_name_kh=?, first_name_kh=?,
               last_name_en=?, first_name_en=?, gender=?, nationality=?,
               pob_province=?, pob_district=?, pob_commune=?, pob_village=?,
               customer_tier=?, marital_status=?, id_expiry=?, submitted_at=datetime('now', '+7 hours'),
               reviewed_at=NULL, reviewed_by=NULL, rejection_reason=NULL
               WHERE id=?""",
            (body.document_type or "national_id", body.document_number, full_name,
             body.date_of_birth, body.address, body.last_name_kh, body.first_name_kh,
             body.last_name_en, body.first_name_en, body.gender, body.nationality,
             body.pob_province, body.pob_district, body.pob_commune, body.pob_village,
             body.customer_tier, body.marital_status, body.id_expiry, existing["id"]))
        kyc_id = existing["id"]
    else:
        # Create new record
        kyc_id = database.execute(
            """INSERT INTO kyc_records
               (customer_id, status, document_type, document_number, full_name,
                date_of_birth, address, last_name_kh, first_name_kh,
                last_name_en, first_name_en, gender, nationality,
                pob_province, pob_district, pob_commune, pob_village,
                customer_tier, marital_status, id_expiry, submitted_at)
               VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+7 hours'))""",
            (cid, body.document_type or "national_id", body.document_number, full_name,
             body.date_of_birth, body.address, body.last_name_kh, body.first_name_kh,
             body.last_name_en, body.first_name_en, body.gender, body.nationality,
             body.pob_province, body.pob_district, body.pob_commune, body.pob_village,
             body.customer_tier, body.marital_status, body.id_expiry))

    # Update customer kyc_status
    database.execute(
        "UPDATE customers SET kyc_status='pending', updated_at=datetime('now', '+7 hours') WHERE telegram_id=?",
        (cid,))

    return {
        "ok": True,
        "message": "KYC submitted successfully, pending admin review",
        "kyc_id": kyc_id,
        "status": "pending",
        "customer_id": cid,
    }


@router.get("/kyc/status")
def get_kyc_status(phone: str = ""):
    """Get KYC verification status for a customer."""
    customer = _get_customer_by_phone(phone)
    cid = customer["telegram_id"]

    record = database.fetchone(
        "SELECT * FROM kyc_records WHERE customer_id=? ORDER BY id DESC LIMIT 1",
        (cid,))

    if not record:
        return {
            "ok": True,
            "kyc_status": customer["kyc_status"] or "none",
            "has_record": False,
            "record": None,
        }

    return {
        "ok": True,
        "kyc_status": record["status"],
        "has_record": True,
        "record": {
            "id": record["id"],
            "status": record["status"],
            "document_type": record["document_type"] or "",
            "document_number": record["document_number"] or "",
            "full_name": record["full_name"] or "",
            "date_of_birth": record["date_of_birth"] or "",
            "address": record["address"] or "",
            "submitted_at": record["submitted_at"] or "",
            "reviewed_at": record["reviewed_at"] or "",
            "reviewed_by": record["reviewed_by"] or "",
            "rejection_reason": record["rejection_reason"] or "",
            "gender": record["gender"] or "",
            "nationality": record["nationality"] or "",
        },
    }
