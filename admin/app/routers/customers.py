"""Customers router — list, search, detail, balance, and profile editing."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings
from app.services import telegram as tg

router = APIRouter(prefix="/customers",
                   dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


def _fmt_balance(amount: int, currency: str) -> str:
    if currency == "USD":
        return f"${amount / 100:.2f}"
    return f"៛{amount:,}"


def _search_customers(
    q: str = "", page: int = 1, limit: int = 20
) -> tuple[list[dict], int]:
    """Search customers by username, phone, name, Telegram ID, account number, or KYC name."""
    offset = (page - 1) * limit

    with database.get_conn() as conn:
        if q.strip():
            like = f"%{q.strip()}%"
            # Also find customers by account number or KYC name
            total = conn.execute(
                "SELECT COUNT(DISTINCT c.telegram_id) FROM customers c "
                "LEFT JOIN accounts a ON a.customer_id = c.telegram_id "
                "LEFT JOIN kyc_records k ON k.customer_id = c.telegram_id "
                "WHERE c.username LIKE ? OR c.phone LIKE ? OR c.first_name LIKE ? "
                "  OR c.last_name LIKE ? OR CAST(c.telegram_id AS TEXT) LIKE ? "
                "  OR c.email LIKE ? OR a.account_number LIKE ? "
                "  OR k.full_name LIKE ? OR k.document_number LIKE ?",
                (like, like, like, like, like, like, like, like, like),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT c.*, "
                "  (SELECT COUNT(*) FROM messages m WHERE m.customer_id = c.telegram_id) AS msg_count, "
                "  (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.telegram_id) AS order_count, "
                "  (SELECT COALESCE(SUM(balance),0) FROM accounts WHERE customer_id = c.telegram_id AND currency='USD') AS usd_balance, "
                "  (SELECT COALESCE(SUM(balance),0) FROM accounts WHERE customer_id = c.telegram_id AND currency='KHR') AS khr_balance, "
                "  (SELECT account_number FROM accounts WHERE customer_id = c.telegram_id AND currency='USD' LIMIT 1) AS usd_account, "
                "  (SELECT account_number FROM accounts WHERE customer_id = c.telegram_id AND currency='KHR' LIMIT 1) AS khr_account, "
                "  (SELECT status FROM kyc_records WHERE customer_id = c.telegram_id ORDER BY id DESC LIMIT 1) AS kyc_status "
                "FROM customers c "
                "LEFT JOIN accounts a ON a.customer_id = c.telegram_id "
                "LEFT JOIN kyc_records k ON k.customer_id = c.telegram_id "
                "WHERE c.username LIKE ? OR c.phone LIKE ? OR c.first_name LIKE ? "
                "  OR c.last_name LIKE ? OR CAST(c.telegram_id AS TEXT) LIKE ? "
                "  OR c.email LIKE ? OR a.account_number LIKE ? "
                "  OR k.full_name LIKE ? OR k.document_number LIKE ? "
                "GROUP BY c.telegram_id "
                "ORDER BY c.updated_at DESC LIMIT ? OFFSET ?",
                (like, like, like, like, like, like, like, like, like, limit, offset),
            ).fetchall()
        else:
            total = conn.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT c.*, "
                "  (SELECT COUNT(*) FROM messages m WHERE m.customer_id = c.telegram_id) AS msg_count, "
                "  (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.telegram_id) AS order_count, "
                "  (SELECT COALESCE(SUM(balance),0) FROM accounts WHERE customer_id = c.telegram_id AND currency='USD') AS usd_balance, "
                "  (SELECT COALESCE(SUM(balance),0) FROM accounts WHERE customer_id = c.telegram_id AND currency='KHR') AS khr_balance, "
                "  (SELECT account_number FROM accounts WHERE customer_id = c.telegram_id AND currency='USD' LIMIT 1) AS usd_account, "
                "  (SELECT account_number FROM accounts WHERE customer_id = c.telegram_id AND currency='KHR' LIMIT 1) AS khr_account, "
                "  (SELECT status FROM kyc_records WHERE customer_id = c.telegram_id ORDER BY id DESC LIMIT 1) AS kyc_status "
                "FROM customers c "
                "ORDER BY c.updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [dict(r) for r in rows], total


@router.get("")
def customers_list(
    request: Request,
    q: str = "",
    page: int = 1,
    username: str = Depends(auth.require_admin),
):
    customers, total = _search_customers(q, page)
    limit = 20
    return _templates.TemplateResponse(
        "customers/list.html",
        {
            "request": request,
            "username": username,
            "active": "customers",
            "customers": customers,
            "total": total,
            "q": q,
            "page": page,
            "pages": max(1, (total + limit - 1) // limit),
        },
    )


@router.get("/{telegram_id}")
def customer_detail(
    request: Request,
    telegram_id: int,
    username: str = Depends(auth.require_admin),
):
    customer = database.fetchone(
        "SELECT * FROM customers WHERE telegram_id = ?", (telegram_id,)
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    accounts = [
        dict(r) for r in database.fetchall(
            "SELECT * FROM accounts WHERE customer_id = ? ORDER BY currency DESC",
            (telegram_id,),
        )
    ]
    kyc = database.fetchone(
        "SELECT * FROM kyc_records WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
        (telegram_id,),
    )
    messages = [
        dict(r) for r in database.fetchall(
            "SELECT * FROM messages WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20",
            (telegram_id,),
        )
    ]
    orders = [
        dict(r) for r in database.fetchall(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY updated_at DESC LIMIT 10",
            (telegram_id,),
        )
    ]
    transactions = [
        dict(r) for r in database.fetchall(
            "SELECT t.*, fa.account_number as from_acct, ta.account_number as to_acct "
            "FROM transactions t "
            "LEFT JOIN accounts fa ON fa.id = t.from_account_id "
            "LEFT JOIN accounts ta ON ta.id = t.to_account_id "
            "WHERE fa.customer_id = ? OR ta.customer_id = ? "
            "ORDER BY t.created_at DESC LIMIT 10",
            (telegram_id, telegram_id),
        )
    ]
    acct_numbers = [a["account_number"] for a in accounts]
    return _templates.TemplateResponse(
        "customers/detail.html",
        {
            "request": request,
            "username": username,
            "customer": dict(customer),
            "accounts": accounts,
            "acct_numbers": acct_numbers,
            "kyc": dict(kyc) if kyc else None,
            "messages": messages,
            "orders": orders,
            "transactions": transactions,
        },
    )


@router.post("/{telegram_id}/edit")
def customer_edit(
    telegram_id: int,
    role: str = Form(...),
    is_active: str = Form("1"),
    phone: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    notes: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    active = 1 if is_active in ("1", "on", "true") else 0
    # The customers table does not have an 'email' column in the current schema,
    # so omit email from the UPDATE to avoid sqlite OperationalError.
    database.execute(
        "UPDATE customers SET role=?, is_active=?, phone=?, first_name=?, last_name=?, notes=?, "
        "updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?",
        (role, active, phone.strip(), first_name.strip(), last_name.strip(), notes, telegram_id),
    )
    return RedirectResponse(
        url=f"/customers/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/add-balance")
def customer_add_balance(
    telegram_id: int,
    currency: str = Form("USD"),
    amount: str = Form(""),
    description: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Add balance to a customer's account (admin credit)."""
    try:
        amt = float(amount)
    except ValueError:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=invalid-amount",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if amt <= 0:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=invalid-amount",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    acct = database.fetchone(
        "SELECT id, account_number, balance FROM accounts WHERE customer_id=? AND currency=? AND status='active'",
        (telegram_id, currency),
    )
    if not acct:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=no-account",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    cents = int(round(amt * 100)) if currency == "USD" else int(round(amt))
    new_balance = acct["balance"] + cents

    with database.get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_balance, acct["id"]),
        )
        conn.execute(
            "INSERT INTO transactions (to_account_id, amount, currency, type, status, description, reference_id, created_at) "
            "VALUES (?, ?, ?, 'deposit', 'completed', ?, ?, datetime('now'))",
            (acct["id"], cents, currency,
             description or f"Admin credit by {_username}",
             f"ADM{int(__import__('time').time())}"),
        )

    return RedirectResponse(
        url=f"/customers/{telegram_id}?balance=ok",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/deduct-balance")
def customer_deduct_balance(
    telegram_id: int,
    currency: str = Form("USD"),
    amount: str = Form(""),
    description: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Deduct balance from a customer's account."""
    try:
        amt = float(amount)
    except ValueError:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=invalid-amount",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if amt <= 0:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=invalid-amount",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    acct = database.fetchone(
        "SELECT id, account_number, balance FROM accounts WHERE customer_id=? AND currency=? AND status='active'",
        (telegram_id, currency),
    )
    if not acct:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=no-account",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    cents = int(round(amt * 100)) if currency == "USD" else int(round(amt))
    if acct["balance"] < cents:
        return RedirectResponse(
            url=f"/customers/{telegram_id}?error=insufficient",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    new_balance = acct["balance"] - cents

    with database.get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_balance, acct["id"]),
        )
        conn.execute(
            "INSERT INTO transactions (from_account_id, amount, currency, type, status, description, reference_id, created_at) "
            "VALUES (?, ?, ?, 'withdrawal', 'completed', ?, ?, datetime('now'))",
            (acct["id"], cents, currency,
             description or f"Admin deduction by {_username}",
             f"ADM{int(__import__('time').time())}"),
        )

    return RedirectResponse(
        url=f"/customers/{telegram_id}?balance=ok",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/ban")
def customer_ban(telegram_id: int, _username: str = Depends(auth.require_admin)):
    database.execute(
        "UPDATE customers SET role='banned', is_active=0, updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?",
        (telegram_id,),
    )
    return RedirectResponse(
        url=f"/customers/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/unban")
def customer_unban(telegram_id: int, _username: str = Depends(auth.require_admin)):
    database.execute(
        "UPDATE customers SET role='customer', is_active=1, updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?",
        (telegram_id,),
    )
    return RedirectResponse(
        url=f"/customers/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/send-notify")
async def customer_send_notify(
    telegram_id: int,
    message: str = Form(...),
    force: str = Form("0"),
    username: str = Depends(auth.require_admin),
):
    """Send a custom notification message to a customer via ABA bot.

    Development/testing helper: include a form field `force=1` to bypass the
    placeholder-chat-id validation when testing against local/demo accounts.
    This bypass is restricted to authenticated admins only.
    """
    allowed_users = {"Usdt991990", "admin"}
    if username not in allowed_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: only authorized admins can send notifications"
        )

    customer = database.fetchone(
        "SELECT telegram_id, first_name, username FROM customers WHERE telegram_id=?",
        (telegram_id,)
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # If force flag is provided by an authenticated admin, skip the placeholder
    # Telegram ID check. This is intentionally explicit (force=1) so devs must
    # opt-in when testing against demo accounts.
    do_force = str(force).lower() in ("1", "on", "true")

    if not do_force:
        ok, validation_error = tg.validate_telegram_chat_id(telegram_id)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_error or "This customer has an invalid Telegram chat id.",
            )

    settings = get_settings()
    bot_name = settings.aba_bot_name if settings.aba_bot_token else ""
    result = await tg.send_message(telegram_id, message, bot_name=bot_name, skip_validation=do_force)

    if result.ok:
        database.execute(
            "INSERT INTO messages "
            "(telegram_message_id, customer_id, direction, content_type, "
            "content, source, replied_by, bot_name) "
            "VALUES (?, ?, 'out', 'text', ?, 'admin-notify', ?, ?)",
            (result.message_id or 0, telegram_id, message,
             username, bot_name or "wing-bank"),
        )
        return RedirectResponse(
            url=f"/customers?notify=ok",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    elif result.queued:
        return RedirectResponse(
            url=f"/customers?notify=queued&link={result.start_link or ''}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    else:
        return RedirectResponse(
            url=f"/customers?notify=fail&error={result.error}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
