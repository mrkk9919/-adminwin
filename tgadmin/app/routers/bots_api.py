"""Bot management API routes (JSON endpoints for SPA frontend)."""

import math
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bot import TelegramBot
from app.schemas.bot import (
    BotCreate,
    BotUpdate,
    BotResponse,
    BotListResponse,
    BotTokenResponse,
)
from app.services.telegram import get_bot_info

router = APIRouter(prefix="/api/bots", tags=["bots-api"])


@router.get("", response_model=BotListResponse)
async def list_bots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    """List bots with pagination and filters."""
    query = db.query(TelegramBot)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (TelegramBot.name.ilike(like)) | (TelegramBot.username.ilike(like))
        )

    if status == "active":
        query = query.filter(TelegramBot.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(TelegramBot.is_active.is_(False))

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    bots = query.order_by(TelegramBot.created_at.desc()).offset(offset).limit(page_size).all()

    return BotListResponse(
        items=[BotResponse.from_model(b) for b in bots],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=BotResponse, status_code=201)
async def create_bot(bot_data: BotCreate, db: Session = Depends(get_db)):
    """Create a new bot. Validates the token via Telegram's getMe and
    auto-fills the username when possible."""
    existing = db.query(TelegramBot).filter(TelegramBot.bot_token == bot_data.bot_token).first()
    if existing:
        raise HTTPException(status_code=400, detail="该 Bot Token 已存在")

    try:
        info = await get_bot_info(bot_data.bot_token)
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Bot Token 无效或无法访问 Telegram API: {e}")

    bot = TelegramBot(
        name=bot_data.name,
        bot_token=bot_data.bot_token,
        username=info.get("username"),
        is_active=bot_data.is_active,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return BotResponse.from_model(bot)


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(bot_id: int, db: Session = Depends(get_db)):
    """Get bot by internal ID."""
    bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse.from_model(bot)


@router.get("/{bot_id}/token", response_model=BotTokenResponse)
async def reveal_bot_token(bot_id: int, db: Session = Depends(get_db)):
    """Reveal the full, unmasked bot token. Used only by an explicit
    'view'/edit action in the frontend, never in list responses."""
    bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotTokenResponse(id=bot.id, bot_token=bot.bot_token)


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(bot_id: int, bot_data: BotUpdate, db: Session = Depends(get_db)):
    """Update bot info. Re-validates and refreshes the username if the token changes."""
    bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    update_data = bot_data.model_dump(exclude_unset=True)

    if "bot_token" in update_data and update_data["bot_token"] != bot.bot_token:
        new_token = update_data["bot_token"]
        existing = (
            db.query(TelegramBot)
            .filter(TelegramBot.bot_token == new_token, TelegramBot.id != bot_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="该 Bot Token 已存在")
        try:
            info = await get_bot_info(new_token)
        except (httpx.HTTPError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Bot Token 无效或无法访问 Telegram API: {e}")
        bot.username = info.get("username")

    for field, value in update_data.items():
        setattr(bot, field, value)

    bot.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(bot)
    return BotResponse.from_model(bot)


@router.put("/{bot_id}/toggle", response_model=BotResponse)
async def toggle_bot(bot_id: int, db: Session = Depends(get_db)):
    """Enable or disable a bot (flips is_active)."""
    bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    bot.is_active = not bot.is_active
    bot.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(bot)
    return BotResponse.from_model(bot)


@router.delete("/{bot_id}", status_code=204)
async def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """Delete a bot."""
    bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    db.delete(bot)
    db.commit()
