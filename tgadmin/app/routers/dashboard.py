"""Dashboard routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Render dashboard page with statistics."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    banned_users = db.query(func.count(User.id)).filter(User.is_banned.is_(True)).scalar() or 0
    active_users = total_users - banned_users
    bot_users = db.query(func.count(User.id)).filter(User.is_bot.is_(True)).scalar() or 0

    stats = {
        "total_users": total_users,
        "banned_users": banned_users,
        "active_users": active_users,
        "bot_users": bot_users,
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats},
    )
