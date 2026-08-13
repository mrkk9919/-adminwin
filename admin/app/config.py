"""Application settings loaded from .env.

Use a single source of truth (pydantic-settings) so that typos in variable
names or missing values raise at startup rather than at the first HTTP call.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram ---------------------------------------------------------------
    bot_token: str = Field(..., env=["BOT_TOKEN", "TGADMIN_BOT_TOKEN"])
    # Additional bot tokens (comma-separated) for multi-bot monitoring.
    extra_bot_tokens: str = Field("", env=["EXTRA_BOT_TOKENS", "TGADMIN_EXTRA_BOT_TOKENS"])
    # ABA BANK secondary bot token (chat relay + transaction notifications).
    aba_bot_token: str = Field("", env=["ABA_BOT_TOKEN", "TGADMIN_ABA_BOT_TOKEN"])
    # messages.bot_name value that identifies the ABA bot instance.
    aba_bot_name: str = "aba-bank"

    # Database ---------------------------------------------------------------
    # Path is resolved relative to the admin/ directory so both `uvicorn`
    # launches and `python -m app.main` work regardless of CWD.
    database_path: str = "../shared.db"

    # Auth -------------------------------------------------------------------
    admin_username: str = "admin"
    admin_password: str = "admin123"
    jwt_secret: str = "please-change-me-to-something-random"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # SMS --------------------------------------------------------------------
    sms_provider: str = "WINGSMS"  # "WINGSMS" | "camintel"
    sms_api_key: str = ""
    sms_api_secret: str = ""

    # Server -----------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8080

    # IP Whitelist -----------------------------------------------------------
    # Comma-separated list of allowed IPs. Empty = allow all.
    allowed_ips: str = "127.0.0.1,175.100.46.41"

    # Payment callback ---------------------------------------------------------
    # Token required by the public payment-confirm API (X-API-Token header).
    payment_api_token: str = ""

    # Push API token ----------------------------------------------------------
    # Optional token used by bot-to-admin push notification calls.
    push_api_token: str = ""

    # FCM Push Notification --------------------------------------------------
    fcm_server_key: str = ""

    # Admin Notification -----------------------------------------------------
    # Telegram user ID of the admin to notify when customer lookup fails.
    admin_telegram_id: str = "8619129145"

    def all_bot_tokens(self) -> list[str]:
        """Return all configured bot tokens (primary + extra)."""
        tokens = [self.bot_token]
        if self.extra_bot_tokens:
            tokens.extend(
                t.strip() for t in self.extra_bot_tokens.split(",") if t.strip()
            )
        return tokens

    def token_for_bot(self, bot_name: str) -> str:
        """Resolve the Telegram token for a bot instance name.

        Unknown / empty names fall back to the primary bot token so legacy
        rows (no bot_name) keep working.
        """
        if bot_name == self.aba_bot_name:
            if self.aba_bot_token:
                return self.aba_bot_token
            raise ValueError(
                f"ABA bot token is not configured but bot_name '{bot_name}' was requested. "
                "Set ABA_BOT_TOKEN or TGADMIN_ABA_BOT_TOKEN."
            )
        return self.bot_token

    def resolved_db_path(self) -> Path:
        """Return the absolute path to the SQLite file, resolving relative to
        the admin/ directory (one level above this package)."""
        base = Path(__file__).resolve().parent.parent  # admin/
        p = Path(self.database_path)
        if not p.is_absolute():
            p = (base / p).resolve()
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
