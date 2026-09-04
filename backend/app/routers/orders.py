"""Orders router — hash lookup, list, create, and notifications."""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings
from app.services import telegram as tg

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/orders", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))

# Public payment-callback API (token-protected, no admin session required).
api_router = APIRouter(prefix="/orders")


@api_router.post("/api/notify")
async def api_notify(request: Request):
    """Internal API: notify a customer with a payment template.

    Authentication: X-Push-Token header OR X-API-Key header must match settings.push_api_token.
    Payload (JSON): {"recipient": "@username|telegram_id", "order_hash": "..."}

    Returns JSON {ok: True/False, detail: str}
    """
    settings = get_settings()
    token = request.headers.get("X-Push-Token") or request.headers.get("X-API-Key")
    if not settings.push_api_token or not token or token != settings.push_api_token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Invalid or missing push token"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    recipient = str(body.get("recipient") or "").strip()
    order_hash = str(body.get("order_hash") or "").strip()

    order = None
    customer_id = None

    if order_hash:
        row = database.fetchone("SELECT * FROM orders WHERE hash = ?", (order_hash,))
        if not row:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found"})
        order = dict(row)
        customer_id = order.get("customer_id")

    if recipient:
        if recipient.startswith("@"):
            username = recipient.lstrip("@")
            c = database.fetchone("SELECT telegram_id FROM customers WHERE username = ?", (username,))
            if not c:
                return JSONResponse(status_code=404, content={"ok": False, "error": f"Customer not found for username @{username}"})
            customer_id = c["telegram_id"]
        else:
            try:
                customer_id = int(recipient)
            except ValueError:
                if not order:
                    row = database.fetchone("SELECT * FROM orders WHERE hash = ?", (recipient,))
                    if not row:
                        return JSONResponse(status_code=400, content={"ok": False, "error": "Unrecognized recipient or order hash"})
                    order = dict(row)
                    customer_id = order.get("customer_id")

    if not order and customer_id:
        row = database.fetchone(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1", (customer_id,)
        )
        if not row:
            return JSONResponse(status_code=404, content={"ok": False, "error": "No orders found for recipient"})
        order = dict(row)

    if not order:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Order not found; supply order_hash or recipient with orders"})

    if not customer_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Unable to resolve recipient Telegram ID"})

    bot_name = settings.aba_bot_name if settings.aba_bot_token else ""
    notes = (order.get("notes") or "")
    from_account = ""
    if notes.startswith("from:"):
        from_account = notes.split(" | ")[0][len("from:"):].strip()

    text = _payment_template(order, from_account=from_account)

    result = await tg.send_message(customer_id, text, bot_name=bot_name)
    if not result.ok:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": result.error or "Telegram API error: failed to send message",
            },
        )

    database.execute(
        "INSERT INTO messages (telegram_message_id, customer_id, direction, content_type, content, source, replied_by, bot_name) VALUES (?, ?, 'out', 'text', ?, 'bot', ?, ?)",
        (result.message_id or 0, customer_id, text, "push-api", bot_name or "wing-bank"),
    )

    return JSONResponse({"ok": True, "detail": f"sent (msg #{result.message_id})"})



@api_router.post("/api/payment-confirm")
async def payment_confirm(request: Request):
    """Payment-success callback: record the order, auto-build the
    transaction template and push it to the customer via the ABA bot.

    Called by the payment frontend / gateway after a QR transfer succeeds.
    Auth: X-API-Token header must match PAYMENT_API_TOKEN in .env.

    Body (JSON):
        hash (required), customer_id, amount, currency, bank,
        receiver (name), receiver_account, from_account, tx_id (Ref),
        tx_date ("YYYY-MM-DD HH:MM", defaults to now)
    """
    settings = get_settings()
    if not settings.payment_api_token:
        return JSONResponse(status_code=503, content={
            "ok": False, "error": "Payment API not configured (PAYMENT_API_TOKEN missing)"})
    if request.headers.get("X-API-Token") != settings.payment_api_token:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Invalid token"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    order_hash = str(body.get("hash") or "").strip()
    if not order_hash:
        return JSONResponse(status_code=400, content={"ok": False, "error": "hash is required"})

    # Recipient line: "NAME — account" (account optional).
    receiver = str(body.get("receiver") or "").strip()
    receiver_account = str(body.get("receiver_account") or "").strip()
    receiver_line = f"{receiver} — {receiver_account}" if receiver_account else receiver

    tx_date = str(body.get("tx_date") or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M")

    # Customer binding: explicit value wins, otherwise reuse previous order row.
    customer_id = body.get("customer_id")
    try:
        customer_id = int(customer_id) if customer_id else None
    except (TypeError, ValueError):
        customer_id = None
    from_account = str(body.get("from_account") or "").strip()

    existing = database.fetchone(
        "SELECT customer_id, notes FROM orders WHERE hash = ?", (order_hash,))
    if not customer_id and existing:
        customer_id = existing["customer_id"]

    # Persist from_account in notes so re-notifications keep the full context.
    notes = str(body.get("notes") or "").strip()
    if from_account:
        notes = f"from:{from_account}" + (f" | {notes}" if notes else "")

    database.execute(
        "INSERT OR REPLACE INTO orders "
        "(hash, customer_id, amount, currency, status, bank, receiver, tx_date, tx_id, notes) "
        "VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?)",
        (order_hash, customer_id, str(body.get("amount") or ""),
         str(body.get("currency") or "USD"), str(body.get("bank") or ""),
         receiver_line or "-", tx_date, str(body.get("tx_id") or ""), notes or None),
    )

    order = dict(database.fetchone("SELECT * FROM orders WHERE hash = ?", (order_hash,)))

    # Auto-send the notification template to the recipient.
    sent, detail = await _send_payment_notice(order, from_account=from_account)

    return JSONResponse(content={
        "ok": True,
        "order_hash": order_hash,
        "notified": sent,
        "notify_detail": detail,
        "template": _payment_template(order, from_account),
    })


def _payment_template(order: dict, from_account: str = "") -> str:
    """Build the fixed payment-success notification template.

    Variable fields: tx date, recipient name, recipient account, bank
    (channel) and hash — everything else is constant.
    """
    try:
        amount_str = f"{float(order.get('amount') or 0):,.2f}"
    except (TypeError, ValueError):
        amount_str = str(order.get('amount') or '0')
    currency = order.get('currency') or 'USD'

    lines = ["✅ Transaction Successful", ""]
    lines.append("Type: Transfer")
    lines.append(f"Amount: {amount_str} {currency}")
    if from_account:
        lines.append(f"From: {from_account}")
    lines.append(f"To: {order.get('receiver') or '-'}")
    lines.append(
        f"Description: Channel: {order.get('bank') or 'eMoney'} | "
        f"Hash: {order.get('hash') or '-'}")
    if order.get('tx_id'):
        lines.append(f"Ref: {order['tx_id']}")
    lines.append(f"Date: {(order.get('tx_date') or '')[:16]}")
    lines.append("")
    lines.append("Thank you for banking with ABA.")
    return "\n".join(lines)


async def _send_payment_notice(order: dict, from_account: str = "") -> tuple[bool, str]:
    """Send the payment template to the bound customer via the ABA bot."""
    customer_id = order.get('customer_id')
    if not customer_id:
        return False, "Order has no customer bound"

    settings = get_settings()
    bot_name = settings.aba_bot_name if settings.aba_bot_token else ""
    text = _payment_template(order, from_account)

    result = await tg.send_message(customer_id, text, bot_name=bot_name)
    if not result.ok:
        return False, result.error or "send failed"

    database.execute(
        "INSERT INTO messages "
        "(telegram_message_id, customer_id, direction, content_type, "
        "content, source, replied_by, bot_name) "
        "VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)",
        (result.message_id or 0, customer_id, text,
         "payment-notify", bot_name or "wing-bank"),
    )
    log.info("payment notice sent for order %s to %s (msg #%s)",
             order.get('hash'), customer_id, result.message_id)
    return True, f"sent (msg #{result.message_id})"


def _list_orders(q: str = "", limit: int = 100) -> list[dict]:
    if q.strip():
        like = f"%{q.strip()}%"
        rows = database.fetchall(
            "SELECT o.*, c.username, c.first_name, c.last_name "
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
            "WHERE o.hash LIKE ? OR CAST(o.customer_id AS TEXT) LIKE ? "
            "  OR o.bank LIKE ? OR o.status LIKE ? "
            "ORDER BY o.updated_at DESC LIMIT ?",
            (like, like, like, like, limit),
        )
    else:
        rows = database.fetchall(
            "SELECT o.*, c.username, c.first_name, c.last_name "
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
            "ORDER BY o.updated_at DESC LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in rows]


@router.get("/hash-lookup")
def hash_lookup_page(
    request: Request,
    q: str = "",
    username: str = Depends(auth.require_admin),
):
    """Hash Lookup page — enter a hash/reference_id to see transfer details.

    Searches both:
    1. orders.hash  (external bank transfer orders)
    2. transactions.reference_id  (internal transfers + QR payments from frontend)
    """
    order = None
    record_type = None
    if q.strip():
        query = q.strip()
        # 1. Try orders table first
        row = database.fetchone(
            "SELECT o.*, c.username, c.first_name, c.last_name "
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
            "WHERE o.hash = ?",
            (query,),
        )
        if row:
            order = dict(row)
            record_type = "order"
        else:
            # 2. Try transactions table (internal transfers + QR payments)
            txn = database.fetchone(
                """SELECT t.*,
                          fa.account_number AS from_account,
                          ta.account_number AS to_account,
                          fc.phone AS from_phone,
                          fc.first_name AS from_first_name,
                          fc.last_name AS from_last_name,
                          tc.phone AS to_phone,
                          tc.first_name AS to_first_name,
                          tc.last_name AS to_last_name
                   FROM transactions t
                   LEFT JOIN accounts fa ON t.from_account_id = fa.id
                   LEFT JOIN accounts ta ON t.to_account_id = ta.id
                   LEFT JOIN customers fc ON fa.customer_id = fc.telegram_id
                   LEFT JOIN customers tc ON ta.customer_id = tc.telegram_id
                   WHERE t.reference_id = ?""",
                (query,),
            )
            if txn:
                # Normalize transaction record to match template expectations
                txn_dict = dict(txn)
                txn_dict["hash"] = txn_dict["reference_id"]
                txn_dict["bank"] = "Wing (Internal)"
                txn_dict["receiver"] = (
                    f"{txn_dict.get('to_first_name') or ''} {txn_dict.get('to_last_name') or ''}".strip()
                    or txn_dict.get("to_account") or "—"
                )
                txn_dict["tx_date"] = txn_dict.get("created_at")
                txn_dict["tx_id"] = txn_dict.get("reference_id")
                txn_dict["customer_id"] = (
                    database.fetchone(
                        "SELECT customer_id FROM accounts WHERE id=?",
                        (txn_dict["from_account_id"],),
                    )["customer_id"]
                    if txn_dict.get("from_account_id")
                    else None
                )
                txn_dict["first_name"] = txn_dict.get("from_first_name")
                txn_dict["last_name"] = txn_dict.get("from_last_name")
                txn_dict["username"] = txn_dict.get("from_phone")
                txn_dict["notes"] = txn_dict.get("description") or ""
                txn_dict["created_at"] = txn_dict.get("created_at")
                txn_dict["updated_at"] = txn_dict.get("created_at")
                order = txn_dict
                record_type = "transaction"

    # Recent orders for the initial (no-query) view.
    recent_rows = database.fetchall(
        "SELECT o.hash, o.amount, o.currency, o.status, o.bank, o.tx_date "
        "FROM orders o ORDER BY o.updated_at DESC LIMIT 10"
    )
    recent_orders = [dict(r) for r in recent_rows]

    # Also show recent transactions
    recent_txns = database.fetchall(
        """SELECT t.reference_id AS hash, t.amount, t.currency, t.status,
                  'Wing' AS bank, t.created_at AS tx_date, t.type
           FROM transactions t ORDER BY t.id DESC LIMIT 10"""
    )
    recent_transactions = [dict(r) for r in recent_txns]

    return _templates.TemplateResponse(
        "orders/hash_lookup.html",
        {
            "request": request,
            "username": username,
            "order": order,
            "record_type": record_type,
            "q": q,
            "recent_orders": recent_orders,
            "recent_transactions": recent_transactions,
        },
    )


@router.get("/api/hash-lookup")
def api_hash_lookup(
    q: str = "",
    _username: str = Depends(auth.require_admin),
):
    """JSON API — look up a single order or transaction by hash/reference_id."""
    q = q.strip()
    if not q:
        return {"ok": True, "found": False}
    # 1. Try orders table
    row = database.fetchone(
        "SELECT o.*, c.username, c.first_name, c.last_name "
        "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
        "WHERE o.hash = ?",
        (q,),
    )
    if row:
        return {"ok": True, "found": True, "type": "order", "order": dict(row)}
    # 2. Try transactions table
    txn = database.fetchone(
        """SELECT t.*,
                  fa.account_number AS from_account,
                  ta.account_number AS to_account,
                  fc.phone AS from_phone,
                  fc.first_name AS from_first_name,
                  fc.last_name AS from_last_name,
                  tc.phone AS to_phone,
                  tc.first_name AS to_first_name,
                  tc.last_name AS to_last_name
           FROM transactions t
           LEFT JOIN accounts fa ON t.from_account_id = fa.id
           LEFT JOIN accounts ta ON t.to_account_id = ta.id
           LEFT JOIN customers fc ON fa.customer_id = fc.telegram_id
           LEFT JOIN customers tc ON ta.customer_id = tc.telegram_id
           WHERE t.reference_id = ?""",
        (q,),
    )
    if not txn:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "type": "transaction", "transaction": dict(txn)}


@router.get("")
def orders_list(
    request: Request,
    q: str = "",
    username: str = Depends(auth.require_admin),
):
    return _templates.TemplateResponse(
        "orders/list.html",
        {
            "request": request,
            "username": username,
            "orders": _list_orders(q),
            "q": q,
        },
    )


@router.get("/{order_hash}")
def order_detail(
    request: Request,
    order_hash: str,
    username: str = Depends(auth.require_admin),
):
    order = database.fetchone(
        "SELECT o.*, c.username, c.first_name, c.last_name "
        "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
        "WHERE o.hash = ?",
        (order_hash,),
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _templates.TemplateResponse(
        "orders/detail.html",
        {"request": request, "username": username, "order": dict(order)},
    )


@router.post("/create")
def order_create(
    hash: str = Form(...),
    customer_id: str = Form(""),
    amount: str = Form(""),
    currency: str = Form("USD"),
    status_val: str = Form("pending"),
    bank: str = Form(""),
    receiver: str = Form(""),
    tx_date: str = Form(""),
    tx_id: str = Form(""),
    notes: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    cid = int(customer_id) if customer_id.strip().isdigit() else None
    database.execute(
        "INSERT OR REPLACE INTO orders "
        "(hash, customer_id, amount, currency, status, bank, receiver, tx_date, tx_id, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (hash.strip(), cid, amount, currency, status_val,
         bank, receiver, tx_date, tx_id, notes),
    )
    return RedirectResponse(url="/orders", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{order_hash}/edit")
def order_edit(
    order_hash: str,
    customer_id: str = Form(""),
    amount: str = Form(""),
    currency: str = Form("USD"),
    status_val: str = Form("pending"),
    bank: str = Form(""),
    receiver: str = Form(""),
    tx_date: str = Form(""),
    tx_id: str = Form(""),
    notes: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    cid = int(customer_id) if customer_id.strip().isdigit() else None
    database.execute(
        "UPDATE orders SET customer_id=?, amount=?, currency=?, status=?, "
        "bank=?, receiver=?, tx_date=?, tx_id=?, notes=?, updated_at=datetime('now', '+7 hours') "
        "WHERE hash=?",
        (cid, amount, currency, status_val,
         bank, receiver, tx_date, tx_id, notes, order_hash),
    )
    return RedirectResponse(
        url=f"/orders/{order_hash}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{order_hash}/delete")
def order_delete(
    order_hash: str,
    _username: str = Depends(auth.require_admin),
):
    """Delete an order permanently."""
    database.execute("DELETE FROM orders WHERE hash = ?", (order_hash,))
    return RedirectResponse(url="/orders", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{order_hash}/notify")
async def order_notify(
    order_hash: str,
    _username: str = Depends(auth.require_admin),
):
    """Push the standard payment template to the customer via the ABA bot."""
    order = database.fetchone(
        "SELECT * FROM orders WHERE hash = ?", (order_hash,))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order["customer_id"]:
        raise HTTPException(
            status_code=400, detail="Order has no customer bound")

    # Recover from_account persisted in notes ("from:<account> | ...").
    from_account = ""
    notes = order["notes"] or ""
    if notes.startswith("from:"):
        from_account = notes.split(" | ")[0][len("from:"):].strip()

    ok, detail = await _send_payment_notice(dict(order), from_account=from_account)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Notify failed: {detail}",
        )
    return RedirectResponse(
        url=f"/orders/{order_hash}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/notify-manual")
async def notify_manual(
    recipient: str = Form(""),
    order_hash: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Manually notify a customer with a payment template.

    Form params:
      - recipient: @username or telegram_id (optional if order_hash binds a customer)
      - order_hash: order hash (optional if recipient provided and has orders)

    Returns JSON: {ok, detail}
    """
    recipient = (recipient or "").strip()
    order_hash = (order_hash or "").strip()

    order = None
    customer_id = None

    if order_hash:
        row = database.fetchone("SELECT * FROM orders WHERE hash = ?", (order_hash,))
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        order = dict(row)
        customer_id = order.get("customer_id")

    # Resolve recipient param if provided
    if recipient:
        if recipient.startswith("@"):
            username = recipient.lstrip("@")
            c = database.fetchone("SELECT telegram_id FROM customers WHERE username = ?", (username,))
            if not c:
                raise HTTPException(status_code=404, detail=f"Customer not found for username @{username}")
            customer_id = c["telegram_id"]
        else:
            # try parse as int id
            try:
                customer_id = int(recipient)
            except ValueError:
                # treat as hash fallback
                if not order:
                    row = database.fetchone("SELECT * FROM orders WHERE hash = ?", (recipient,))
                    if not row:
                        raise HTTPException(status_code=400, detail="Unrecognized recipient or order hash")
                    order = dict(row)
                    customer_id = order.get("customer_id")

    # If no order provided, and we have customer_id, find latest order
    if not order and customer_id:
        row = database.fetchone(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1", (customer_id,)
        )
        if not row:
            raise HTTPException(status_code=404, detail="No orders found for recipient")
        order = dict(row)

    if not order:
        raise HTTPException(status_code=400, detail="Order not found; supply order_hash or recipient with orders")

    # Ensure we have a customer id to send to
    if not customer_id:
        raise HTTPException(status_code=400, detail="Unable to resolve recipient Telegram ID")

    settings = get_settings()
    bot_name = settings.aba_bot_name if settings.aba_bot_token else ""
    notes = (order.get("notes") or "")
    from_account = ""
    if notes.startswith("from:"):
        from_account = notes.split(" | ")[0][len("from:"):].strip()

    text = _payment_template(order, from_account=from_account)

    result = await tg.send_message(customer_id, text, bot_name=bot_name)
    if not result.ok:
        raise HTTPException(status_code=502, detail=f"Telegram API error: {result.error}")

    database.execute(
        "INSERT INTO messages (telegram_message_id, customer_id, direction, content_type, content, source, replied_by, bot_name) VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)",
        (result.message_id or 0, customer_id, text, "manual-notify", bot_name or "wing-bank"),
    )

    return JSONResponse({"ok": True, "detail": f"sent (msg #{result.message_id})"})
