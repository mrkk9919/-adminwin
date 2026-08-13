"""Telegram Bot API service."""

import httpx

from app.config import settings

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramService:
    """Wrapper for Telegram Bot API calls."""

    def __init__(self):
        self.token = settings.bot_token
        self.base_url = f"{TELEGRAM_API_BASE}/bot{self.token}"

    async def get_me(self) -> dict:
        """Get bot info."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/getMe")
            resp.raise_for_status()
            return resp.json()

    async def ban_chat_member(self, chat_id: int, user_id: int) -> bool:
        """Ban a user from a chat."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/banChatMember",
                json={"chat_id": chat_id, "user_id": user_id},
            )
            resp.raise_for_status()
            return resp.json().get("ok", False)

    async def unban_chat_member(self, chat_id: int, user_id: int) -> bool:
        """Unban a user from a chat."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/unbanChatMember",
                json={"chat_id": chat_id, "user_id": user_id, "only_if_banned": True},
            )
            resp.raise_for_status()
            return resp.json().get("ok", False)


telegram_service = TelegramService()


async def get_bot_info(token: str) -> dict:
    """Call Telegram's getMe API for an arbitrary bot token.

    Used to validate a token and auto-fill the bot's @username when
    adding/editing bots in the admin panel. Raises httpx.HTTPStatusError
    or httpx.RequestError if the token is invalid or Telegram is unreachable.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{TELEGRAM_API_BASE}/bot{token}/getMe")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise ValueError(data.get("description", "Invalid bot token"))
        return data["result"]
