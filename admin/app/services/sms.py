"""SMS provider abstraction — WINGSMS + Camintel (placeholder).

The default WINGSMS provider generates OTP codes and logs them.
The Camintel provider is a skeleton ready for real API credentials.
"""
from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class SendResult:
    ok: bool
    provider_msg_id: str | None = None
    error: str | None = None
    cost_cents: int = 0


class SMSProvider(Protocol):
    async def send(self, phone: str, message: str) -> SendResult: ...


class WingSMSProvider:
    """Wing Bank SMS provider — generates OTP, sends via internal system."""

    async def send(self, phone: str, message: str) -> SendResult:
        msg_id = f'WING-{random.randint(10000, 99999)}'
        log.info("WINGSMS → %s: %s (id=%s)", phone, message, msg_id)
        return SendResult(ok=True, provider_msg_id=msg_id, cost_cents=0)


class CamintelSMSProvider:
    """Production SMS provider for Cambodia. Needs SMS_API_KEY + SMS_API_SECRET."""

    async def send(self, phone: str, message: str) -> SendResult:
        settings = get_settings()
        if not settings.sms_api_key:
            return SendResult(ok=False, error="SMS_API_KEY not configured")

        # TODO: Replace with real Camintel API call.
        # Example endpoint: https://api.camintel.com/v1/sms/send
        # Headers: X-API-Key, X-API-Secret
        # Body: {to, message, from}
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.camintel.com/v1/sms/send",
                    json={"to": phone, "message": message, "from": "WingBank"},
                    headers={
                        "X-API-Key": settings.sms_api_key,
                        "X-API-Secret": settings.sms_api_secret,
                    },
                )
        except httpx.HTTPError as exc:
            return SendResult(ok=False, error=f"http: {exc}")

        if resp.status_code >= 400:
            return SendResult(ok=False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        return SendResult(
            ok=True,
            provider_msg_id=str(body.get("id", "")),
            cost_cents=body.get("cost_cents", 0),
        )


def get_provider() -> SMSProvider:
    """Return the configured SMS provider instance."""
    settings = get_settings()
    if settings.sms_provider == "camintel":
        return CamintelSMSProvider()
    return WingSMSProvider()


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code."""
    return "".join(str(random.randint(0, 9)) for _ in range(length))
