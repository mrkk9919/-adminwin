"""Dashboard API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(db: Session = Depends(get_db)):
    """Return dashboard statistics."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    banned_users = db.query(func.count(User.id)).filter(User.is_banned.is_(True)).scalar() or 0
    active_users = total_users - banned_users
    bot_users = db.query(func.count(User.id)).filter(User.is_bot.is_(True)).scalar() or 0

    return {
        "total_users": total_users,
        "banned_users": banned_users,
        "active_users": active_users,
        "bot_users": bot_users,
    }
