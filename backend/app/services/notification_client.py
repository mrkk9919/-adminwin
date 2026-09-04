"""Notification Service Client - calls the standalone notification-service API.

This client integrates with the notification-service running on port 9000.
It creates notification records that the worker process will send via Telegram.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

# Notification service base URL
NOTIFICATION_SERVICE_URL = "http://127.0.0.1:9000"


class NotificationClient:
    """Client for the notification-service API."""

    def __init__(self, base_url: str = NOTIFICATION_SERVICE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, data: dict) -> Optional[dict]:
        """POST JSON to notification service."""
        url = f"{self.base_url}{path}"
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            result = json.loads(resp.read().decode("utf-8"))
            return result
        except Exception as e:
            log.warning("Notification service POST %s failed: %s", path, e)
            return None

    def _get(self, path: str) -> Optional[dict]:
        """GET from notification service."""
        url = f"{self.base_url}{path}"
        try:
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("Notification service GET %s failed: %s", path, e)
            return None

    def create_notification(
        self,
        customer_id: str,
        bot_type: str,
        message: str,
        telegram_user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        scheduled_at: Optional[str] = None,
    ) -> Optional[dict]:
        """Create a notification to be sent by the worker.

        Args:
            customer_id: Customer ID (telegram_id from customers table)
            bot_type: "wing" or "aba"
            message: Message text to send
            telegram_user_id: Optional Telegram user ID (overrides lookup)
            chat_id: Optional chat ID (overrides lookup)
            scheduled_at: Optional ISO datetime for scheduled sending

        Returns:
            Notification record dict, or None on failure
        """
        # Ensure customer_id has "C" prefix (notification-service format)
        cid = str(customer_id)
        if not cid.startswith("C"):
            cid = "C" + cid

        data = {
            "customer_id": cid,
            "bot_type": bot_type,
            "message": message,
        }
        if telegram_user_id is not None:
            data["telegram_user_id"] = telegram_user_id
        if chat_id is not None:
            data["chat_id"] = chat_id
        if scheduled_at:
            data["scheduled_at"] = scheduled_at

        return self._post("/api/notifications", data)

    def register_telegram_user(
        self,
        customer_id: str,
        telegram_user_id: int,
        chat_id: int,
        bot_type: str = "wing",
        username: Optional[str] = None,
    ) -> Optional[dict]:
        """Register a customer's Telegram ID for notifications.

        Args:
            customer_id: Customer ID
            telegram_user_id: Telegram user ID
            chat_id: Telegram chat ID
            bot_type: "wing" or "aba"
            username: Optional Telegram username

        Returns:
            TelegramUser record dict, or None on failure
        """
        # Ensure customer_id has "C" prefix
        cid = str(customer_id)
        if not cid.startswith("C"):
            cid = "C" + cid

        data = {
            "customer_id": cid,
            "telegram_user_id": telegram_user_id,
            "chat_id": chat_id,
            "bot_type": bot_type,
            "notification_enabled": True,
            "status": "active",
        }
        if username:
            data["username"] = username

        return self._post("/telegram-users", data)

    def get_telegram_users(
        self,
        customer_id: Optional[str] = None,
        bot_type: Optional[str] = None,
    ) -> Optional[list]:
        """List Telegram users, optionally filtered."""
        params = []
        if customer_id:
            cid = str(customer_id)
            if not cid.startswith("C"):
                cid = "C" + cid
            params.append(f"customer_id={cid}")
        if bot_type:
            params.append(f"bot_type={bot_type}")
        path = "/telegram-users"
        if params:
            path += "?" + "&".join(params)
        return self._get(path)

    def list_notifications(
        self,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> Optional[list]:
        """List notifications, optionally filtered."""
        params = []
        if status:
            params.append(f"status={status}")
        if customer_id:
            cid = str(customer_id)
            if not cid.startswith("C"):
                cid = "C" + cid
            params.append(f"customer_id={cid}")
        path = "/notifications"
        if params:
            path += "?" + "&".join(params)
        return self._get(path)

    def register_bot(
        self,
        name: str,
        bot_type: str,
        bot_token: str,
        bot_username: Optional[str] = None,
    ) -> Optional[dict]:
        """Register a Telegram bot in the notification service."""
        data = {
            "name": name,
            "bot_type": bot_type,
            "bot_token": bot_token,
            "status": "active",
        }
        if bot_username:
            data["bot_username"] = bot_username
        return self._post("/telegram-bots", data)


# Global singleton
_notification_client: Optional[NotificationClient] = None


def get_notification_client() -> NotificationClient:
    """Get or create the global notification client."""
    global _notification_client
    if _notification_client is None:
        _notification_client = NotificationClient()
    return _notification_client


def send_transfer_notification_via_service(
    customer_id: str,
    amount_str: str,
    currency: str,
    from_account: str,
    to_name: str,
    to_account: str,
    ref_id: str,
    description: str = "",
    channel: str = "Wing bank",
    bot_type: str = "wing",
) -> bool:
    """Send a transfer notification via the notification service.

    Returns True if notification was created successfully, False otherwise.
    """
    from datetime import datetime, timezone

    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    short_hash = ref_id[-6:] if len(ref_id) >= 6 else ref_id

    desc_line = f"Description: Channel: {channel} | Hash: {short_hash}"
    if description:
        desc_line += f" | {description}"

    message = (
        f"✅ Transaction Successful\n\n"
        f"Type: Transfer\n\n"
        f"Amount: {amount_str} {currency}\n\n"
        f"From: {from_account}\n\n"
        f"To: {to_name} — {to_account}\n"
        f"{desc_line}\n\n"
        f"Date: {now_str}"
    )

    client = get_notification_client()
    result = client.create_notification(
        customer_id=str(customer_id),
        bot_type=bot_type,
        message=message,
    )
    return result is not None
