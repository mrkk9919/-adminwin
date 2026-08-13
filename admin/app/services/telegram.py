"""Telegram Bot API client used by the admin panel.

Covers sendMessage, getMe, getChat, getWebhookInfo.
The heavy lifting (long-polling, callback handling) stays inside tgbot.

Multi-bot aware: every outbound call accepts an optional ``bot_name`` which
is resolved to the matching token via ``Settings.token_for_bot`` (e.g. the
ABA BANK bot for transaction notifications). An empty / unknown name falls
back to the primary bot token.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from app import database
from app.config import get_settings

_TIMEOUT = httpx.Timeout(10.0)


def validate_telegram_chat_id(chat_id: int | str | None) -> tuple[bool, str | None]:
    """Validate a Telegram chat id and return a human-readable reason on failure.

    Customer conversations should use a real private-chat id. Placeholder values
    such as 1..100000 are common in demo data and will be rejected by Telegram
    before the message is sent.
    """
    if chat_id is None:
        return False, "No Telegram chat id was provided."
    try:
        value = int(chat_id)
    except (TypeError, ValueError):
        return False, "Telegram chat id must be a numeric value."
    if value <= 0:
        return False, "Telegram chat id must be a positive number."
    if value <= 100000:
        return (
            False,
            (
                "This customer record uses a placeholder/test Telegram chat id. "
                f"Received {chat_id!r}. Real Telegram user chats are normally "
                "larger than 100000."
            ),
        )
    return True, None


def is_plausible_telegram_chat_id(chat_id: int | str | None) -> bool:
    """Backward-compatible boolean wrapper around validate_telegram_chat_id."""
    ok, _ = validate_telegram_chat_id(chat_id)
    return ok


def _api_url(method: str, bot_name: str = "") -> str:
    token = get_settings().token_for_bot(bot_name)
    return f"https://api.telegram.org/bot{token}/{method}"


@dataclass
class SendResult:
    ok: bool
    message_id: int | None = None
    error: str | None = None
    queued: bool = False
    start_link: str | None = None


@dataclass
class BotInfo:
    ok: bool
    id: int | None = None
    first_name: str | None = None
    username: str | None = None
    pending_updates: int = 0
    webhook_url: str = ""
    last_error: str | None = None
    error: str | None = None


@dataclass
class ChatInfo:
    ok: bool
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    type: str | None = None
    bio: str | None = None
    error: str | None = None


async def get_me(bot_name: str = "") -> dict[str, Any]:
    """Return the bot's public profile (id, username, first_name)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_api_url("getMe", bot_name))
        resp.raise_for_status()
        return resp.json()


async def get_bot_info() -> BotInfo:
    """Get comprehensive bot status from Telegram API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # getMe
        try:
            me_resp = await client.get(_api_url("getMe"))
            me_body = me_resp.json()
            if not me_body.get("ok"):
                return BotInfo(ok=False, error=me_body.get("description", "getMe failed"))
            me = me_body["result"]
        except Exception as e:
            return BotInfo(ok=False, error=str(e))

        # getWebhookInfo
        pending = 0
        webhook_url = ""
        last_error = None
        try:
            wh_resp = await client.get(_api_url("getWebhookInfo"))
            wh_body = wh_resp.json()
            if wh_body.get("ok"):
                wh = wh_body["result"]
                pending = wh.get("pending_update_count", 0)
                webhook_url = wh.get("url") or "(long polling)"
                last_error = wh.get("last_error_message")
        except Exception:
            pass

    return BotInfo(
        ok=True,
        id=me.get("id"),
        first_name=me.get("first_name"),
        username=me.get("username"),
        pending_updates=pending,
        webhook_url=webhook_url,
        last_error=last_error,
    )


async def get_chat(chat_id: int, bot_name: str = "") -> ChatInfo:
    """Get chat info for a specific Telegram user."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _api_url("getChat", bot_name),
                json={"chat_id": chat_id},
            )
            body = resp.json()
            if not body.get("ok"):
                return ChatInfo(
                    ok=False, error=body.get("description", "Unknown error")
                )
            chat = body["result"]
            return ChatInfo(
                ok=True,
                id=chat.get("id"),
                first_name=chat.get("first_name"),
                last_name=chat.get("last_name"),
                username=chat.get("username"),
                type=chat.get("type"),
                bio=chat.get("bio"),
            )
        except ValueError as exc:
            return ChatInfo(ok=False, error=str(exc))
        except Exception as e:
            return ChatInfo(ok=False, error=str(e))


def _should_queue_proactive_message(error: str | None) -> bool:
    """Return True when an error means the message should be queued for first-use deep-link delivery."""
    if not error:
        return False
    lowered = error.lower()
    if "bot can't initiate conversation" in lowered or "initiate conversation" in lowered:
        return True
    if "chat not found" in lowered:
        return True
    if "not found" in lowered and "chat" in lowered:
        return True
    return False


def _build_start_link(bot_username: str | None, token: str) -> str | None:
    """Build a Telegram deep-link that opens the bot and delivers a queued payload."""
    if not bot_username:
        return None
    username = bot_username.lstrip("@")
    if not username:
        return None
    return f"https://t.me/{username}?start={quote(token)}"


async def _queue_pending_message(chat_id: int, text: str, bot_name: str = "") -> str | None:
    """Persist a queued message payload and return a start link for the customer."""
    token = secrets.token_urlsafe(16)
    customer = database.fetchone(
        "SELECT phone FROM customers WHERE telegram_id = ?",
        (chat_id,),
    )
    phone = customer["phone"] if customer and customer["phone"] else ""
    database.execute(
        "INSERT INTO pending_registrations (token, phone, customer_id, message_payload, expires_at, status) "
        "VALUES (?, ?, ?, ?, datetime('now', '+1 day'), 'pending')",
        (token, phone, chat_id, text),
    )

    try:
        me = await get_me(bot_name)
    except Exception:
        return None
    result = me.get("result") or {}
    username = result.get("username")
    return _build_start_link(username, token)


async def send_message(chat_id: int, text: str, bot_name: str = "", skip_validation: bool = False) -> SendResult:
    """Send a plain-text message to a customer chat.

    ``bot_name`` selects which bot instance sends the message (e.g.
    "aba-bank" for transaction notifications); empty means the primary bot.

    ``skip_validation`` bypasses the placeholder-chat-id validation. This is
    intended for development/testing only and defaults to False.

    Returns SendResult with ok=True and the Telegram message_id on success,
    or ok=False + error string on failure. Never raises.
    """
    if not skip_validation:
        ok, validation_error = validate_telegram_chat_id(chat_id)
        if not ok:
            return SendResult(ok=False, error=validation_error or "Invalid Telegram chat id")

    settings = get_settings()
    bot_token = settings.token_for_bot(bot_name)
    if not bot_token:
        return SendResult(
            ok=False,
            error=(
                f"No Telegram bot token is configured for bot_name='{bot_name or 'primary'}'. "
                "Please verify the bot token in admin settings before sending."
            ),
        )

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                _api_url("sendMessage", bot_name),
                json={"chat_id": chat_id, "text": text},
            )
        except ValueError as exc:
            return SendResult(ok=False, error=str(exc))
        except httpx.HTTPError as exc:
            return SendResult(ok=False, error=f"http: {exc}")

        body = resp.json() if resp.status_code < 500 else {}
        if resp.status_code >= 400 or not body.get("ok", False):
            desc = body.get("description") or f"HTTP {resp.status_code}"
            lowered = desc.lower()
            if resp.status_code == 401 or desc == "Unauthorized":
                desc = (
                    "Unauthorized: bot token invalid or revoked. "
                    f"Verify BOT_TOKEN/TGADMIN_BOT_TOKEN for bot_name='{bot_name or 'primary'}'."
                )
            elif "chat not found" in lowered or "not found" in lowered and "chat" in lowered:
                desc = (
                    "Telegram rejected this chat id. The customer may not have started a chat with the bot, "
                    "or the stored chat id is still invalid. "
                    f"Original Telegram response: {desc}"
                )
            elif "bot can't initiate conversation" in lowered or "initiate conversation" in lowered:
                desc = (
                    "Telegram rejected the message because the bot cannot message this user yet. "
                    "The customer must start a conversation with the bot first. "
                    f"Original Telegram response: {desc}"
                )
            elif "blocked by the user" in lowered:
                desc = (
                    "Telegram rejected the message because the user blocked the bot or disabled messages. "
                    f"Original Telegram response: {desc}"
                )
            elif "forbidden" in lowered:
                desc = (
                    "Telegram rejected the message because the bot is not allowed to send to this chat. "
                    f"Original Telegram response: {desc}"
                )

            if _should_queue_proactive_message(desc):
                start_link = await _queue_pending_message(chat_id, text, bot_name)
                return SendResult(ok=False, error=desc, queued=True, start_link=start_link)
            return SendResult(ok=False, error=desc)

        result = body.get("result") or {}
        return SendResult(ok=True, message_id=result.get("message_id"))
