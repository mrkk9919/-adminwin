"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or .env file."""

    app_name: str = "TGAdmin"
    debug: bool = True

    # Server binding
    host: str = "127.0.0.1"
    port: int = 8000

    # Telegram Bot
    bot_token: str = ""

    # Database
    database_url: str = f"sqlite:///{BASE_DIR / 'tgadmin.db'}"

    # CORS
    cors_origins_raw: str = ""

    # Pagination
    page_size: int = 20

    class Config:
        env_file = ".env"
        env_prefix = "TGADMIN_"

    def __init__(self, **values):
        if "cors_origins_raw" not in values:
            cors_env = os.getenv("TGADMIN_CORS_ORIGINS")
            if cors_env:
                values["cors_origins_raw"] = cors_env
        super().__init__(**values)

    @property
    def cors_origins(self) -> list[str]:
        if self.cors_origins_raw:
            return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]
        return [
            "http://localhost:3000",  # Vite dev server
            "http://localhost:5173",  # Vite default
        ]


settings = Settings()
