"""Bakong QR router — manage users, hierarchy, QR codes, transactions."""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database

log = logging.getLogger(__name__)

router = APIRouter(prefix="/bakong-qr", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

# Directory where QR images are stored (served via /bakong-qr static mount in main.py)
_QR_DIR = Path(__file__).resolve().parent.parent.parent / "deploy" / "bakong-qr"
_QR_DIR.mkdir(parents=True, exist_ok=True)


@router.get("")
def bakong_qr_list(request: Request, page: int = 1, q: str = ""):
    """BAKONG QR transaction list."""
    page_size = 20
    offset = (page - 1) * page_size
    where = "t.type = 'bakong_qr'"
    params = []
    if q:
        where += " AND (t.description LIKE ? OR t.reference_id LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    total = database.fetchone(f"SELECT COUNT(*) as cnt FROM transactions t WHERE {where}", params)["cnt"]
    rows = database.fetchall(
        f"""SELECT t.*, fa.account_number as from_account_number, ta.account_number as to_account_number
            FROM transactions t
            LEFT JOIN accounts fa ON fa.id = t.from_account_id
            LEFT JOIN accounts ta ON ta.id = t.to_account_id
            WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )
    total_pages = (total + page_size - 1) // page_size
    return _templates.TemplateResponse("bakong_qr/list.html", {
        "request": request, "transactions": [dict(r) for r in rows],
        "total": total, "page": page, "total_pages": total_pages, "q": q, "active": "bakong_qr",
    })


@router.get("/users")
def bakong_qr_users(request: Request, q: str = "", qr_type: str = ""):
    """User hierarchy management page."""
    where = "1=1"
    params = []
    if q:
        where += " AND (c.first_name LIKE ? OR c.last_name LIKE ? OR c.phone LIKE ? OR c.referrer_code LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if qr_type:
        where += " AND c.qr_type = ?"
        params.append(qr_type)
    users = database.fetchall(
        f"""SELECT c.telegram_id, c.first_name, c.last_name, c.phone, c.qr_type, c.parent_id,
                   c.referrer_code, c.created_at,
                   p.first_name as parent_first, p.last_name as parent_last
            FROM customers c
            LEFT JOIN customers p ON p.telegram_id = c.parent_id
            WHERE {where} ORDER BY c.qr_type, c.created_at DESC LIMIT 200""",
        params,
    )
    # Get all admins for parent selection
    admins = database.fetchall(
        "SELECT telegram_id, first_name, last_name, referrer_code FROM customers WHERE qr_type IN ('master', 'admin') ORDER BY qr_type, first_name"
    )
    return _templates.TemplateResponse("bakong_qr/users.html", {
        "request": request, "users": [dict(u) for u in users],
        "admins": [dict(a) for a in admins], "q": q, "qr_type": qr_type, "active": "bakong_qr",
    })


@router.post("/users/bind-parent")
def bind_parent(request: Request, customer_id: str = Form(...), parent_id: str = Form("")):
    """Bind a user to a parent (supervisor/admin)."""
    if parent_id:
        parent = database.fetchone("SELECT telegram_id FROM customers WHERE telegram_id=?", (parent_id,))
        if not parent:
            raise HTTPException(404, "Parent not found")
    database.execute("UPDATE customers SET parent_id=?, updated_at=datetime('now', '+7 hours') WHERE telegram_id=?", (parent_id or None, customer_id))
    return RedirectResponse(url="/bakong-qr/users", status_code=303)


@router.post("/users/set-type")
def set_user_type(request: Request, customer_id: str = Form(...), qr_type: str = Form("user")):
    """Set user QR type (master/admin/user)."""
    if qr_type not in ("master", "admin", "user"):
        raise HTTPException(400, "Invalid qr_type")
    database.execute("UPDATE customers SET qr_type=?, updated_at=datetime('now', '+7 hours') WHERE telegram_id=?", (qr_type, customer_id))
    return RedirectResponse(url="/bakong-qr/users", status_code=303)


@router.get("/users/create-admin")
def create_admin_form(request: Request):
    """Create admin account form."""
    admins = database.fetchall(
        "SELECT telegram_id, first_name, last_name, referrer_code FROM customers WHERE qr_type IN ('master', 'admin') ORDER BY first_name"
    )
    return _templates.TemplateResponse("bakong_qr/create_admin.html", {
        "request": request, "admins": [dict(a) for a in admins], "active": "bakong_qr",
    })


@router.post("/users/create-admin")
def create_admin(request: Request, phone: str = Form(...), password: str = Form(...),
                 first_name: str = Form(""), last_name: str = Form(""), parent_id: str = Form("")):
    """Create a new admin account."""
    existing = database.fetchone("SELECT telegram_id FROM customers WHERE phone=?", (phone,))
    if existing:
        raise HTTPException(409, "Phone already registered")
    row = database.fetchone("SELECT MAX(telegram_id) as mx FROM customers WHERE telegram_id >= 8000000000")
    next_id = (row["mx"] or 8000000000) + 1 if row and row["mx"] else 8000000001
    import hashlib, secrets
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    referrer_code = "A" + str(next_id)[-6:]
    parent = parent_id or "MASTER001"
    database.execute(
        """INSERT INTO customers (telegram_id, phone, first_name, last_name, password_hash, password_salt,
           role, is_active, web_registered, parent_id, referrer_code, qr_type, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'admin', 1, 1, ?, ?, 'admin', datetime('now', '+7 hours'), datetime('now', '+7 hours'))""",
        (next_id, phone, first_name, last_name, pw_hash, salt, parent, referrer_code))
    # Create accounts
    for currency in ("USD", "KHR"):
        num = "0" + str(secrets.randbelow(90000000) + 10000000)
        database.execute("INSERT INTO accounts (customer_id, account_number, currency, balance, status, type) VALUES (?, ?, ?, 0, 'active', 'wallet')", (next_id, num, currency))
    return RedirectResponse(url="/bakong-qr/users", status_code=303)


@router.get("/generate")
def bakong_qr_generate_form(request: Request):
    accounts = database.fetchall(
        "SELECT a.id, a.account_number, a.currency, a.balance, "
        "COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '') AS holder "
        "FROM accounts a LEFT JOIN customers c ON c.telegram_id = a.customer_id ORDER BY a.account_number"
    )
    return _templates.TemplateResponse("bakong_qr/generate.html", {
        "request": request, "accounts": [dict(a) for a in accounts], "active": "bakong_qr",
    })


@router.post("/generate")
def bakong_qr_generate(request: Request, account_id: int = Form(...), amount: float = Form(...),
                       currency: str = Form("USD"), description: str = Form("")):
    account = database.fetchone("SELECT * FROM accounts WHERE id=?", (account_id,))
    if not account:
        raise HTTPException(404, "Account not found")
    ref_id = f"BK{uuid.uuid4().hex[:10].upper()}"
    database.execute(
        "INSERT INTO transactions (from_account_id, amount, currency, type, status, description, reference_id, created_at) "
        "VALUES (?, ?, ?, 'bakong_qr', 'pending', ?, ?, datetime('now', '+7 hours'))",
        (account_id, int(amount * 100), currency, description or f"Bakong QR {amount} {currency}", ref_id),
    )
    return RedirectResponse(url="/bakong-qr", status_code=303)


@router.post("/upload-qr")
async def upload_qr_image(
    request: Request,
    customer_id: str = Form(...),
    currency: str = Form("USD"),
    qr_image: UploadFile = File(...),
):
    """Manually upload a BAKONG QR image for a user."""
    # Validate customer exists
    customer = database.fetchone("SELECT telegram_id, first_name, last_name FROM customers WHERE telegram_id=?", (customer_id,))
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Validate currency
    currency = currency.upper()
    if currency not in ("USD", "KHR"):
        raise HTTPException(400, "Currency must be USD or KHR")

    # Validate file
    if not qr_image.filename:
        raise HTTPException(400, "No file uploaded")

    # Save image
    filename = f"{customer_id}_{currency.lower()}.png"
    dest_path = _QR_DIR / filename

    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(qr_image.file, buffer)
        log.info(f"Uploaded QR image for customer {customer_id} ({currency}): {filename}")
    except Exception as e:
        log.error(f"Failed to save QR image: {e}")
        raise HTTPException(500, f"Failed to save image: {e}")

    # Update or insert bakong_qr record
    account = database.fetchone(
        "SELECT id, account_number FROM accounts WHERE customer_id=? AND currency=?",
        (customer_id, currency),
    )
    if account:
        qr_data = f'{{"bank": "WING", "account": "{account["account_number"]}", "name": "{customer["first_name"] or ""} {customer["last_name"] or ""}", "currency": "{currency}", "type": "bakong_qr", "qr_type": "user"}}'
        database.execute(
            "INSERT OR REPLACE INTO bakong_qr (customer_id, account_number, currency, merchant_name, qr_data, qr_image_path, qr_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '+7 hours'))",
            (customer_id, account["account_number"], currency, f'{customer["first_name"] or ""} {customer["last_name"] or ""}'.strip(), qr_data, f"/qr-images/{filename}", "user"),
        )

    return RedirectResponse(url="/bakong-qr/users", status_code=303)
