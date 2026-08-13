"""Messages router — inbox + per-customer conversation view + reply.

The admin panel reads from the shared messages table (written by tgbot) and
pushes replies through the Telegram Bot API (via app.services.telegram).
Also provides API endpoints to probe bot status and chat info in real-time.

Multi-bot aware: every message row carries a bot_name (which bot instance
received it), and replies are routed through the matching bot token.

Scheduled sending: supports delayed message delivery via asyncio background tasks.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings
from app.services import telegram as tg

log = logging.getLogger(__name__)

router = APIRouter(prefix="/messages",
                   dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates"))


# ── Scheduled message sending ────────────────────────────────────────────


async def _send_delayed_message(telegram_id: int, text: str, bot_name: str, username: str, delay_seconds: int):
    """Background task: send a message after a delay."""
    await asyncio.sleep(delay_seconds)
    result = await tg.send_message(telegram_id, text, bot_name=bot_name)
    if result.ok:
        message_id = result.message_id or 0
        database.execute(
            "INSERT INTO messages "
            "(telegram_message_id, customer_id, direction, content_type, "
            "content, source, replied_by, bot_name) "
            "VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)",
            (message_id, telegram_id, text, username,
             bot_name or "wing-bank"),
        )
        log.info("Scheduled message sent to %s after %ds delay", telegram_id, delay_seconds)
    else:
        log.warning("Scheduled message failed for %s: %s", telegram_id, result.error)


def _conversations(limit: int = 50, bot_name: str = "") -> list[dict]:
    """One row per customer: last message preview, unread count, display name.
    Shows ALL customers — those with messages first, then recently added.
    If bot_name is given, only shows customers who have messaged that bot.
    """
    params: list = [bot_name, bot_name, limit]

    sql = f"""
    SELECT
      c.telegram_id,
      COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, '') AS display_name,
      c.username,
      c.phone,
      c.role,
      c.is_active,
      (SELECT COUNT(*) FROM messages m
         WHERE m.customer_id = c.telegram_id
           AND m.direction = 'in'
           AND m.read_at IS NULL) AS unread,
      (SELECT content FROM messages
         WHERE customer_id = c.telegram_id
         ORDER BY created_at DESC LIMIT 1) AS last_message,
      (SELECT created_at FROM messages
         WHERE customer_id = c.telegram_id
         ORDER BY created_at DESC LIMIT 1) AS last_at,
      (SELECT bot_name FROM messages
         WHERE customer_id = c.telegram_id
         ORDER BY created_at DESC LIMIT 1) AS last_bot
    FROM customers c
    WHERE c.telegram_id IN (
        SELECT DISTINCT customer_id FROM messages
        WHERE bot_name = ? OR ? = ''
    )
    ORDER BY
      CASE WHEN last_at IS NULL THEN 1 ELSE 0 END,
      last_at DESC,
      c.updated_at DESC
    LIMIT ?
    """
    return [dict(r) for r in database.fetchall(sql, tuple(params))]


def _conversation(telegram_id: int) -> dict:
    customer = database.fetchone(
        "SELECT telegram_id, username, first_name, last_name, phone, role, "
        "is_active, notes, created_at "
        "FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )
    if not customer:
        raise HTTPException(
            status_code=404, detail=f"Customer {telegram_id} not found")
    messages = [
        dict(r) for r in database.fetchall(
            "SELECT id, direction, content_type, content, source, "
            "replied_by, bot_name, created_at "
            "FROM messages WHERE customer_id = ? ORDER BY created_at ASC",
            (telegram_id,),
        )
    ]
    # The bot the customer last talked to — used as the default reply route.
    default_bot = ""
    for m in reversed(messages):
        if m.get("bot_name"):
            default_bot = m["bot_name"]
            break
    return {"customer": dict(customer), "messages": messages,
            "default_bot": default_bot}


# ── Pages ──────────────────────────────────────────────────────────────


@router.get("")
def inbox(
    request: Request,
    bot: str = "",
    username: str = Depends(auth.require_admin),
):
    convos = _conversations(bot_name=bot)
    total_unread = sum(c.get("unread", 0) for c in convos)
    settings = get_settings()
    # Build bot list for the filter bar
    bot_list = [{"name": "", "label": "All Bots"}]
    if settings.bot_token:
        bot_list.append({"name": "wing-bank", "label": "Wing Bank Bot"})
    if settings.aba_bot_token:
        bot_list.append({"name": settings.aba_bot_name, "label": "ABA BANK Bot"})
    return _templates.TemplateResponse(
        "messages/inbox.html",
        {
            "request": request,
            "username": username,
            "active": "messages",
            "conversations": convos,
            "total_unread": total_unread,
            "bot_list": bot_list,
            "current_bot": bot,
        },
    )


@router.get("/{telegram_id}")
def conversation(
    request: Request,
    telegram_id: int,
    username: str = Depends(auth.require_admin),
):
    view = _conversation(telegram_id)
    # Mark all inbound messages as read when the operator opens the conversation.
    database.execute(
        "UPDATE messages SET read_at = CURRENT_TIMESTAMP "
        "WHERE customer_id = ? AND direction = 'in' AND read_at IS NULL",
        (telegram_id,),
    )
    settings = get_settings()
    return _templates.TemplateResponse(
        "messages/conversation.html",
        {
            "request": request,
            "username": username,
            "aba_bot_name": settings.aba_bot_name,
            "aba_configured": bool(settings.aba_bot_token),
            **view,
        },
    )


# ── Actions ────────────────────────────────────────────────────────────


@router.post("/{telegram_id}/reply")
async def reply(
    telegram_id: int,
    text: str = Form(...),
    bot_name: str = Form(""),
    delay_seconds: int = Form(0),
    username: str = Depends(auth.require_admin),
):
    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty reply")

    # Default routing: reply via the bot the customer last messaged.
    if not bot_name:
        row = database.fetchone(
            "SELECT bot_name FROM messages WHERE customer_id = ? "
            "AND bot_name IS NOT NULL AND bot_name != '' "
            "ORDER BY created_at DESC LIMIT 1",
            (telegram_id,),
        )
        bot_name = row["bot_name"] if row else ""

    # Scheduled sending: if delay > 0, schedule background task
    if delay_seconds > 0:
        asyncio.create_task(_send_delayed_message(telegram_id, text, bot_name, username, delay_seconds))
        return RedirectResponse(
            url=f"/messages/{telegram_id}?scheduled={delay_seconds}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Immediate sending
    ok, validation_error = tg.validate_telegram_chat_id(telegram_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_error or "This customer record has an invalid Telegram chat id.",
        )

    # Prefer the selected bot, but if Telegram reports the customer chat is not
    # available on that bot (for example an ABA bot selection for a Wing Bank
    # customer), automatically retry with the alternate configured bot instead of
    # failing the reply.
    settings = get_settings()
    bot_candidates: list[str] = []
    if bot_name:
        bot_candidates.append(bot_name)
    if bot_name != "wing-bank" and settings.bot_token:
        bot_candidates.append("wing-bank")
    if bot_name != settings.aba_bot_name and settings.aba_bot_token:
        bot_candidates.append(settings.aba_bot_name)
    seen: set[str] = set()
    bot_candidates = [b for b in bot_candidates if not (b in seen or seen.add(b))]
    if not bot_candidates:
        bot_candidates = ["wing-bank"]

    result = None
    failed_errors: list[str] = []
    for candidate in bot_candidates:
        result = await tg.send_message(telegram_id, text, bot_name=candidate)
        if result.ok:
            bot_name = candidate
            break
        failed_errors.append(f"{candidate}: {result.error}")
        lower = (result.error or "").lower()
        if "chat not found" in lower or "bot can't initiate conversation" in lower or "not allowed to send" in lower:
            continue
        break

    if result is None or not result.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram API error: {'; '.join(failed_errors) if failed_errors else 'Unknown error'}",
        )

    message_id = result.message_id or 0
    database.execute(
        "INSERT INTO messages "
        "(telegram_message_id, customer_id, direction, content_type, "
        "content, source, replied_by, bot_name) "
        "VALUES (?, ?, 'out', 'text', ?, 'admin', ?, ?)",
        (message_id, telegram_id, text, username,
         bot_name or "wing-bank"),
    )
    return RedirectResponse(
        url=f"/messages/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/mark-read")
def mark_read(telegram_id: int, _username: str = Depends(auth.require_admin)):
    database.execute(
        "UPDATE messages SET read_at = CURRENT_TIMESTAMP "
        "WHERE customer_id = ? AND direction = 'in' AND read_at IS NULL",
        (telegram_id,),
    )
    return {"ok": True}


# ── API endpoints (JSON) ───────────────────────────────────────────────


@router.get("/api/search-customer")
def api_search_customer(
    q: str = "",
    _username: str = Depends(auth.require_admin),
):
    """Search customers by username, phone, or telegram_id."""
    q = q.strip().lstrip("@")
    if not q or len(q) < 2:
        return {"ok": True, "results": []}

    like = f"%{q}%"
    rows = database.fetchall(
        """SELECT telegram_id,
                  COALESCE(first_name,'') || ' ' || COALESCE(last_name,'') AS display_name,
                  username, phone, role, is_active
           FROM customers
           WHERE username LIKE ? OR phone LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?
           ORDER BY updated_at DESC LIMIT 10""",
        (like, like, like),
    )
    return {"ok": True, "results": [dict(r) for r in rows]}


@router.post("/api/add-customer")
async def api_add_customer(
    request: Request,
    _username: str = Depends(auth.require_admin),
):
    """Add a customer by Telegram ID, username, or phone.

    Accepts form fields: telegram_id (optional), tg_username (optional),
    phone (optional). At least telegram_id is required for messaging.
    If telegram_id is given, also fetches name from Telegram API.
    """
    form = await request.form()
    raw_id = (form.get("telegram_id") or "").strip()
    raw_username = (form.get("tg_username") or "").strip().lstrip("@")
    raw_phone = (form.get("phone") or "").strip()

    if not raw_id and not raw_username and not raw_phone:
        return {"ok": False, "error": "Please enter at least a Telegram ID, username, or phone."}

    telegram_id = int(raw_id) if raw_id else None

    # Check if already exists by telegram_id.
    if telegram_id:
        existing = database.fetchone(
            "SELECT telegram_id FROM customers WHERE telegram_id = ?",
            (telegram_id,),
        )
        if existing:
            return {"ok": True, "existing": True, "telegram_id": telegram_id}

    # Check if already exists by username.
    if raw_username:
        existing = database.fetchone(
            "SELECT telegram_id FROM customers WHERE username = ?",
            (raw_username,),
        )
        if existing:
            return {"ok": True, "existing": True, "telegram_id": existing["telegram_id"]}

    # Fetch info from Telegram API if we have an ID.
    first_name = ""
    last_name = ""
    tg_username = raw_username or None
    phone = raw_phone or None

    if telegram_id:
        info = await tg.get_chat(telegram_id)
        first_name = info.first_name or ""
        last_name = info.last_name or ""
        if info.username:
            tg_username = info.username

    # Generate a placeholder ID if none provided.
    if not telegram_id:
        # Use negative ID for pending customers (no real Telegram ID yet).
        row = database.fetchone("SELECT MIN(telegram_id) FROM customers")
        min_id = row[0] if row and row[0] else 0
        telegram_id = min(min_id, -1) - 1

    database.execute(
        """INSERT OR IGNORE INTO customers
           (telegram_id, first_name, last_name, username, phone, role, is_active,
            balance_khr, balance_usd, status, kyc_status)
           VALUES (?, ?, ?, ?, ?, 'customer', 1, 0, 0, 'active', 'none')""",
        (telegram_id, first_name, last_name, tg_username, phone),
    )

    return {
        "ok": True,
        "existing": False,
        "telegram_id": telegram_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": tg_username,
        "phone": phone,
        "can_message": telegram_id > 0,
    }


@router.get("/api/bot-status")
async def api_bot_status(_username: str = Depends(auth.require_admin)):
    """Check bot connection status via Telegram API."""
    info = await tg.get_bot_info()
    return {
        "ok": info.ok,
        "bot_id": info.id,
        "first_name": info.first_name,
        "username": info.username,
        "pending_updates": info.pending_updates,
        "webhook_url": info.webhook_url,
        "last_error": info.last_error,
        "error": info.error,
    }


@router.get("/api/chat/{chat_id}")
async def api_chat_info(
    chat_id: int, _username: str = Depends(auth.require_admin)
):
    """Get real-time chat info from Telegram API for a specific user."""
    info = await tg.get_chat(chat_id)
    return {
        "ok": info.ok,
        "id": info.id,
        "first_name": info.first_name,
        "last_name": info.last_name,
        "username": info.username,
        "type": info.type,
        "bio": info.bio,
        "error": info.error,
    }
