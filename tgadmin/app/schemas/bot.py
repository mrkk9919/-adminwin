"""Pydantic schemas for TelegramBot."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    bot_token: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class BotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    bot_token: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class BotResponse(BaseModel):
    id: int
    name: str
    username: Optional[str] = None
    is_active: bool
    bot_token_masked: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @staticmethod
    def from_model(bot) -> "BotResponse":
        return BotResponse(
            id=bot.id,
            name=bot.name,
            username=bot.username,
            is_active=bot.is_active,
            bot_token_masked=bot.masked_token,
            created_at=bot.created_at,
            updated_at=bot.updated_at,
        )


class BotTokenResponse(BaseModel):
    """Full, unmasked token — only returned via an explicit 'reveal' action."""

    id: int
    bot_token: str


class BotListResponse(BaseModel):
    items: list[BotResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
