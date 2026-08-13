"""Transactions router — list, filter, detail, create + notify.

Creating a transaction also pushes a formatted statement to the customer
through the ABA BANK bot (falling back gracefully when the customer has
never messaged the bot — Telegram blocks unsolicited first messages).
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings
from app.services import telegram as tg
from app.services import sms as sms_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

_TX_TYPES = ("transfer", "deposit", "withdrawal", "exchange")
_TX_STATUSES = ("completed", "pending", "failed", "reversed")
_CURRENCIES = ("USD", "KHR")


# ── Helpers ────────────────────────────────────────────────────────────


def _account_options() -> list[dict]:
    """Accounts joined with their holder name, for form dropdowns."""
    rows = database.fetchall(
        "SELECT a.id, a.customer_id, a.account_number, a.currency, a.status, "
        "COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '') AS holder "
        "FROM accounts a LEFT JOIN customers c ON c.telegram_id = a.customer_id "
        "ORDER BY a.account_number"
    )
    return [dict(r) for r in rows]


def _notify_customers() -> list[dict]:
    """Distinct account holders that can receive a transaction statement.

    Capped at 300 rows — the full customer base is too large to render
    in a dropdown; use the search field for anyone not listed.
    """
    rows = database.fetchall(
        "SELECT DISTINCT c.telegram_id, "
        "COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '') AS display_name, "
        "c.username "
        "FROM customers c JOIN accounts a ON a.customer_id = c.telegram_id "
        "ORDER BY display_name LIMIT 300"
    )
    return [dict(r) for r in rows]


def _account_holder(account_id: int | None) -> int | None:
    """Return the telegram_id owning an account (or None)."""
    if not account_id:
        return None
    row = database.fetchone(
        "SELECT customer_id FROM accounts WHERE id = ?", (account_id,))
    return row["customer_id"] if row else None


def _find_customer_by_phone(phone: str) -> dict | None:
    """Find a customer by phone number.
    
    Tries exact match first, then tries with/without country code prefix.
    Returns the customer row dict or None.
    """
    if not phone:
        return None
    
    phone = phone.strip()
    
    # Try exact match
    row = database.fetchone(
        "SELECT * FROM customers WHERE phone = ?", (phone,))
    if row:
        return dict(row)
    
    # Try with + prefix
    if not phone.startswith('+'):
        row = database.fetchone(
            "SELECT * FROM customers WHERE phone = ?", (f"+{phone}",))
        if row:
            return dict(row)
    
    # Try without + prefix
    if phone.startswith('+'):
        row = database.fetchone(
            "SELECT * FROM customers WHERE phone = ?", (phone[1:],))
        if row:
            return dict(row)
    
    # Try partial match (last 10 digits)
    if len(phone) >= 10:
        last_digits = phone[-10:]
        row = database.fetchone(
            "SELECT * FROM customers WHERE phone LIKE ? ORDER BY created_at DESC LIMIT 1",
            (f"%{last_digits}",))
        if row:
            return dict(row)
    
    return None


def _get_customer_name(customer: dict | None) -> str:
    """Get display name from customer dict."""
    if not customer:
        return ""
    first = customer.get('first_name') or ''
    last = customer.get('last_name') or ''
    name = f"{first} {last}".strip()
    return name or (customer.get('username') or str(customer.get('telegram_id', '')))


def _account_number(account_id: int | None) -> str:
    if not account_id:
        return ""
    row = database.fetchone(
        "SELECT account_number FROM accounts WHERE id = ?", (account_id,))
    if row and row["account_number"]:
        return row["account_number"]
    return str(account_id)


def _fmt_amount(amount: int, currency: str) -> str:
    """Human-readable amount. USD is stored in cents, KHR as whole units."""
    if currency == "KHR":
        return f"{amount:,.0f} KHR"
    return f"{amount / 100:,.2f} USD"


def _tx_statement(tx: dict, to_name: str = "", to_phone: str = "") -> str:
    """Format a transaction row as a customer-facing statement message.
    
    Matches the ABA Bank transaction receipt format.
    """
    lines = ["✅ Transaction Successful", ""]
    lines.append(f"Type: {tx['type'].capitalize()}")
    lines.append("")
    lines.append(f"Amount: {_fmt_amount(tx['amount'], tx['currency'])}")
    lines.append("")
    
    from_num = _account_number(tx.get("from_account_id"))
    if from_num:
        lines.append(f"From: {from_num}")
        lines.append("")
    
    # Format To field with name and phone if available
    if to_name or to_phone:
        to_display = ""
        if to_name:
            to_display = to_name
        if to_phone:
            if to_display:
                to_display += f" — {to_phone}"
            else:
                to_display = to_phone
        lines.append(f"To: {to_display}")
        lines.append("")
    elif tx.get("external_to"):
        lines.append(f"To: {tx['external_to']}")
        lines.append("")
    
    if tx.get("description"):
        lines.append(f"Description: {tx['description']}")
        lines.append("")
    
    if tx.get("reference_id"):
        lines.append(f"Ref: {tx['reference_id']}")
        lines.append("")
    
    # Format date nicely
    date_str = tx.get('created_at') or ''
    if date_str:
        # Try to format as YYYY-MM-DD HH:MM
        if 'T' in date_str:
            date_str = date_str.replace('T', ' ')
        if len(date_str) > 16:
            date_str = date_str[:16]
    lines.append(f"Date: {date_str}")
    lines.append("")
    lines.append("Thank you for banking with ABA.")
    return "\n".join(lines)


async def _notify_customer(
    tx_id: int,
    customer_id: int | None = None,
    notify_method: str = "telegram",
    group_id: int | None = None,
    phone: str = "",
) -> tuple[bool, str]:
    """Send the transaction statement to a customer via Telegram bot and/or SMS, or to a group.

    notify_method: 'telegram', 'sms', 'both', or 'group'
    group_id: notification_groups.id (if notify_method == 'group')
    phone: phone number to look up customer (used if customer_id is None)
    Returns (ok, detail). Logs the outgoing message on success.
    """
    tx_row = database.fetchone(
        "SELECT * FROM transactions WHERE id = ?", (tx_id,))
    if not tx_row:
        return False, "Transaction not found"
    tx = dict(tx_row)

    settings = get_settings()
    bot_name = settings.aba_bot_name if settings.aba_bot_token else ""
    admin_id = settings.admin_telegram_id

    # Look up customer by phone if customer_id is not provided
    customer = None
    if not customer_id and phone:
        customer = _find_customer_by_phone(phone)
        if customer:
            customer_id = customer.get('telegram_id')
            log.info("tx %s: found customer %s by phone %s", tx_id, customer_id, phone)
        else:
            log.info("tx %s: no customer found for phone %s", tx_id, phone)
            # Notify admin that customer was not found
            admin_text = (
                f"⚠️ *Customer Not Found*\n\n"
                f"Transaction #{tx_id}\n"
                f"Phone: {phone}\n"
                f"Amount: {_fmt_amount(tx['amount'], tx['currency'])}\n\n"
                f"Please check if this customer has registered their Telegram account."
            )
            if admin_id:
                try:
                    admin_id_int = int(admin_id)
                    await tg.send_message(admin_id_int, admin_text, bot_name=bot_name)
                except Exception as e:
                    log.warning("Failed to notify admin about missing customer: %s", e)
            return False, f"Customer not found for phone: {phone} (admin notified)"

    # Get customer info for the statement
    to_name = ""
    to_phone = ""
    if customer:
        to_name = _get_customer_name(customer)
        to_phone = customer.get('phone') or phone
    elif customer_id:
        cust_row = database.fetchone(
            "SELECT * FROM customers WHERE telegram_id = ?", (customer_id,))
        if cust_row:
            cust = dict(cust_row)
            to_name = _get_customer_name(cust)
            to_phone = cust.get('phone') or ""

    text = _tx_statement(tx, to_name=to_name, to_phone=to_phone)

    results = []

    # Group notification
    if notify_method == "group" and group_id:
        group = database.fetchone(
            "SELECT * FROM notification_groups WHERE id = ? AND is_active = 1", (group_id,))
        if group:
            result = await tg.send_message(group["chat_id"], text, bot_name=bot_name)
            if result.ok:
                results.append(f"Group: OK (chat_id={group['chat_id']})")
            else:
                results.append(f"Group: {result.error or 'send failed'}")
        else:
            results.append("Group: Not found or inactive")
        ok = all("OK" in r for r in results)
        detail = "; ".join(results)
        log.info("tx %s: notify group %s: %s", tx_id, group_id, detail)
        return ok, detail

    # Customer notification (Telegram + SMS)
    if not customer_id or customer_id <= 0:
        return False, "No customer to notify"

    # Telegram notification
    if notify_method in ("telegram", "both"):
        if not tg.is_plausible_telegram_chat_id(customer_id):
            results.append(
                "Telegram: invalid customer chat_id; this record likely uses a placeholder/test ID"
            )
        else:
            result = await tg.send_message(customer_id, text, bot_name=bot_name)
            if result.ok:
                message_id = result.message_id or 0
                database.execute(
                    "INSERT INTO messages "
                    "(telegram_message_id, customer_id, direction, content_type, "
                    "content, source, replied_by, bot_name) "
                    "VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)",
                    (message_id, customer_id, text,
                     "tx-notify", bot_name or "wing-bank"),
                )
                results.append(f"Telegram: OK (msg #{message_id})")
            else:
                results.append(f"Telegram: {result.error or 'send failed'}")
                # Notify admin about failed send
                if admin_id:
                    try:
                        admin_id_int = int(admin_id)
                        fail_text = (
                            f"❌ *Notification Failed*\n\n"
                            f"Transaction #{tx_id}\n"
                            f"Customer: {to_name or customer_id}\n"
                            f"Phone: {to_phone or 'N/A'}\n"
                            f"Error: {result.error or 'send failed'}\n\n"
                            f"Please check the customer's Telegram account."
                        )
                        await tg.send_message(admin_id_int, fail_text, bot_name=bot_name)
                    except Exception as e:
                        log.warning("Failed to notify admin about send failure: %s", e)

    # SMS notification
    if notify_method in ("sms", "both"):
        cust = database.fetchone(
            "SELECT phone FROM customers WHERE telegram_id = ?", (customer_id,))
        if cust and cust["phone"]:
            sms_provider = sms_service.get_provider()
            sms_result = await sms_provider.send(cust["phone"], text)
            if sms_result.ok:
                database.execute(
                    "INSERT INTO sms_logs "
                    "(phone, message, provider, provider_msg_id, status, cost_cents) "
                    "VALUES (?, ?, ?, ?, 'sent', ?)",
                    (cust["phone"], text, "wingsms", sms_result.provider_msg_id, sms_result.cost_cents),
                )
                results.append(f"SMS: OK (id={sms_result.provider_msg_id})")
            else:
                results.append(f"SMS: {sms_result.error}")
        else:
            results.append("SMS: No phone number")

    ok = all("OK" in r for r in results)
    detail = "; ".join(results)
    log.info("tx %s: notify customer %s via %s: %s", tx_id, customer_id, notify_method, detail)
    return ok, detail


# ── Pages ──────────────────────────────────────────────────────────────


@router.get("")
def transactions_list(
    request: Request,
    tx_type: str = "",
    status: str = "",
    currency: str = "",
    q: str = "",
    page: int = 1,
    username: str = Depends(auth.require_admin),
):
    where_clauses = []
    params: list = []

    if tx_type:
        where_clauses.append("t.type = ?")
        params.append(tx_type)
    if status:
        where_clauses.append("t.status = ?")
        params.append(status)
    if currency:
        where_clauses.append("t.currency = ?")
        params.append(currency)
    if q.strip():
        like = f"%{q.strip()}%"
        where_clauses.append(
            "(t.description LIKE ? OR t.reference_id LIKE ? OR t.external_to LIKE ?)")
        params.extend([like, like, like])

    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    limit = 20
    offset = (page - 1) * limit

    with database.get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM transactions t WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT t.*, "
            f"  (SELECT c.first_name || ' ' || c.last_name FROM customers c "
            f"   JOIN accounts a ON a.customer_id = c.telegram_id WHERE a.id = t.from_account_id) as from_name, "
            f"  (SELECT c.first_name || ' ' || c.last_name FROM customers c "
            f"   JOIN accounts a ON a.customer_id = c.telegram_id WHERE a.id = t.to_account_id) as to_name "
            f"FROM transactions t WHERE {where} "
            f"ORDER BY t.created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return _templates.TemplateResponse(
        "transactions/list.html",
        {
            "request": request,
            "username": username,
            "active": "transactions",
            "transactions": [dict(r) for r in rows],
            "total": total,
            "tx_type": tx_type,
            "status_filter": status,
            "currency": currency,
            "q": q,
            "page": page,
            "pages": max(1, (total + limit - 1) // limit),
        },
    )


@router.get("/api/account-search")
def account_search(
    q: str = "",
    limit: int = 20,
    _username: str = Depends(auth.require_admin),
):
    """JSON search over the account base (used by the create form).

    Matches account number or holder name; capped at `limit` results.
    """
    q = q.strip()
    if not q:
        return JSONResponse({"ok": True, "accounts": []})
    limit = max(1, min(limit, 50))
    like = f"%{q}%"
    rows = database.fetchall(
        "SELECT a.id, a.account_number, a.currency, a.status, "
        "COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '') AS holder "
        "FROM accounts a LEFT JOIN customers c ON c.telegram_id = a.customer_id "
        "WHERE a.account_number LIKE ? OR CAST(a.id AS TEXT) = ? OR holder LIKE ? "
        "ORDER BY a.account_number LIMIT ?",
        (like, q, like, limit),
    )
    return JSONResponse({"ok": True, "accounts": [dict(r) for r in rows]})


@router.get("/create")
def transactions_create_page(
    request: Request,
    username: str = Depends(auth.require_admin),
):
    """Render the transaction creation form."""
    # Get active notification groups
    try:
        groups = database.fetchall(
            "SELECT id, chat_title, chat_id FROM notification_groups WHERE is_active = 1 ORDER BY created_at DESC"
        )
    except Exception:
        groups = []
    
    return _templates.TemplateResponse(
        "transactions/create.html",
        {
            "request": request,
            "username": username,
            "active": "transactions",
            "notify_customers": _notify_customers(),
            "notify_groups": [dict(g) for g in groups],
            "tx_types": _TX_TYPES,
            "currencies": _CURRENCIES,
            "tx_statuses": _TX_STATUSES,
        },
    )


@router.post("/create")
async def transactions_create(
    tx_type: str = Form("transfer"),
    amount: str = Form(...),
    currency: str = Form("USD"),
    from_account_id: str = Form(""),
    to_account_id: str = Form(""),
    description: str = Form(""),
    reference_id: str = Form(""),
    external_to: str = Form(""),
    status: str = Form("completed"),
    notify_customer_id: str = Form(""),
    notify_phone: str = Form(""),
    notify_method: str = Form("telegram"),
    notify_group_id: str = Form(""),
    channel: str = Form(""),
    hash_code: str = Form(""),
    username: str = Depends(auth.require_admin),
):
    """Create a transaction and notify the customer via the ABA bot.
    
    Supports customer lookup by phone number for automatic notification.
    """
    # --- Validation ---------------------------------------------------------
    if tx_type not in _TX_TYPES:
        raise HTTPException(400, detail=f"Invalid type: {tx_type}")
    if status not in _TX_STATUSES:
        raise HTTPException(400, detail=f"Invalid status: {status}")
    if currency not in _CURRENCIES:
        raise HTTPException(400, detail=f"Invalid currency: {currency}")

    try:
        amount_val = float(amount)
    except ValueError:
        raise HTTPException(400, detail="Amount must be a number")
    if amount_val <= 0:
        raise HTTPException(400, detail="Amount must be positive")
    # USD stored as cents, KHR as whole units.
    amount_int = int(round(amount_val * 100)) if currency == "USD" else int(round(amount_val))

    from_id = int(from_account_id) if from_account_id else None
    to_id = int(to_account_id) if to_account_id else None
    ext_to = external_to.strip() or None
    
    if tx_type == "transfer" and not from_id:
        raise HTTPException(400, detail="Transfer requires a from account")
    if tx_type == "transfer" and not (to_id or ext_to or notify_phone):
        raise HTTPException(
            400, detail="Transfer requires a to account, external beneficiary, or phone number")

    # Build description with channel and hash if provided
    full_description = description.strip() or ""
    if channel or hash_code:
        parts = []
        if channel:
            parts.append(f"Channel: {channel}")
        if hash_code:
            parts.append(f"Hash: {hash_code}")
        channel_hash = " | ".join(parts)
        if full_description:
            full_description = f"{full_description} | {channel_hash}"
        else:
            full_description = channel_hash

    # --- Insert -------------------------------------------------------------
    tx_id = database.execute(
        "INSERT INTO transactions "
        "(from_account_id, to_account_id, amount, currency, type, status, "
        "description, reference_id, external_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (from_id, to_id, amount_int, currency, tx_type, status,
         full_description or None, reference_id.strip() or None, ext_to),
    )

    # --- Notify -------------------------------------------------------------
    notify_id = int(notify_customer_id) if notify_customer_id else None
    phone = notify_phone.strip() or ""
    
    # Determine target: explicit ID > phone lookup > account holder
    target = notify_id
    group_id = int(notify_group_id) if notify_group_id else None
    phone_lookup_failed = False
    
    if not target and phone:
        # Look up by phone
        customer = _find_customer_by_phone(phone)
        if customer:
            target = customer.get('telegram_id')
            log.info("tx %s: found customer %s by phone %s", tx_id, target, phone)
        else:
            log.info("tx %s: no customer found for phone %s, will notify admin", tx_id, phone)
            phone_lookup_failed = True
    
    # Fallback to account holder only if no phone was specified
    if not target and not phone:
        target = _account_holder(from_id) or _account_holder(to_id)
    
    ok, detail = await _notify_customer(
        tx_id, 
        target, 
        notify_method=notify_method, 
        group_id=group_id,
        phone=phone if phone_lookup_failed or (phone and not target) else "",
    )
    log.info("tx %s created by %s; notify ok=%s (%s)",
             tx_id, username, ok, detail)

    return RedirectResponse(
        url=f"/transactions/{tx_id}?notify={'ok' if ok else 'fail'}",
        status_code=303,
    )


@router.get("/{tx_id}")
def transaction_detail(
    request: Request,
    tx_id: int,
    notify: str = "",
    username: str = Depends(auth.require_admin),
):
    tx = database.fetchone("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx = dict(tx)
    # Resolve account holders
    if tx.get("from_account_id"):
        from_acct = database.fetchone(
            "SELECT a.*, c.first_name, c.last_name, c.username "
            "FROM accounts a LEFT JOIN customers c ON c.telegram_id = a.customer_id "
            "WHERE a.id = ?", (tx["from_account_id"],)
        )
        tx["from_account"] = dict(from_acct) if from_acct else None
    if tx.get("to_account_id"):
        to_acct = database.fetchone(
            "SELECT a.*, c.first_name, c.last_name, c.username "
            "FROM accounts a LEFT JOIN customers c ON c.telegram_id = a.customer_id "
            "WHERE a.id = ?", (tx["to_account_id"],)
        )
        tx["to_account"] = dict(to_acct) if to_acct else None

    # Candidate customers that can receive the statement.
    notify_targets = []
    for key, label in (("from_account", "From"), ("to_account", "To")):
        acct = tx.get(key)
        if acct and acct.get("customer_id"):
            name = f"{acct.get('first_name') or ''} {acct.get('last_name') or ''}".strip()
            notify_targets.append({
                "customer_id": acct["customer_id"],
                "label": f"{label}: {name or acct['customer_id']}",
            })

    return _templates.TemplateResponse(
        "transactions/detail.html",
        {
            "request": request,
            "username": username,
            "active": "transactions",
            "tx": tx,
            "notify_targets": notify_targets,
            "notify_result": notify,
            "statement_preview": _tx_statement(tx),
        },
    )


@router.post("/{tx_id}/notify")
async def transaction_notify(
    tx_id: int,
    customer_id: int = Form(...),
    notify_method: str = Form("telegram"),
    _username: str = Depends(auth.require_admin),
):
    """(Re)send the transaction statement to a customer via Telegram and/or SMS."""
    ok, detail = await _notify_customer(tx_id, customer_id, notify_method=notify_method)
    if not ok:
        raise HTTPException(502, detail=f"Notify failed: {detail}")
    return RedirectResponse(
        url=f"/transactions/{tx_id}?notify=ok", status_code=303)
