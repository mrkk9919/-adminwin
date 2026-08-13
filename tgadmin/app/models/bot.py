"""Telegram Bot database model."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.database import Base


class TelegramBot(Base):
    """A Telegram bot managed through the admin panel."""

    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    bot_token = Column(String(255), nullable=False, unique=True)
    username = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def masked_token(self) -> str:
        """Return the bot token with the middle portion hidden."""
        token = self.bot_token or ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:6]}...{token[-4:]}"

    def __repr__(self):
        return f"<TelegramBot(name={self.name}, username={self.username})>"
