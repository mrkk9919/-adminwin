"""User management routes (API + page rendering)."""

import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserBan, UserResponse, UserListResponse
from app.config import settings

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")


# ────────────────────────── Page Routes ──────────────────────────


@router.get("")
async def users_page(
    request: Request,
    page: int = Query(1, ge=1),
    search: str = Query("", description="Search by name or username"),
    status: str = Query("", description="Filter: all / banned / active"),
    db: Session = Depends(get_db),
):
    """Render user list page."""
    query = db.query(User)

    # Search filter
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.tg_user_id == int(search) if search.isdigit() else False,
            )
        )

    # Status filter
    if status == "banned":
        query = query.filter(User.is_banned.is_(True))
    elif status == "active":
        query = query.filter(User.is_banned.is_(False))

    total = query.count()
    total_pages = max(1, math.ceil(total / settings.page_size))
    page = min(page, total_pages)
    offset = (page - 1) * settings.page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(settings.page_size).all()

    return templates.TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "users": users,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search": search,
            "status": status,
        },
    )


@router.get("/{user_id}")
async def user_detail_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Render user detail page."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse(
        "users/detail.html",
        {"request": request, "user": user},
    )


# ────────────────────────── API Routes ──────────────────────────


@router.get("/api/list", response_model=UserListResponse)
async def api_list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    """API: list users with pagination."""
    query = db.query(User)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
            )
        )

    if status == "banned":
        query = query.filter(User.is_banned.is_(True))
    elif status == "active":
        query = query.filter(User.is_banned.is_(False))

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/api/create", response_model=UserResponse, status_code=201)
async def api_create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """API: create a new user."""
    existing = db.query(User).filter(User.tg_user_id == user_data.tg_user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this Telegram ID already exists")

    user = User(**user_data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/api/{user_id}", response_model=UserResponse)
async def api_get_user(user_id: int, db: Session = Depends(get_db)):
    """API: get user by internal ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/api/{user_id}", response_model=UserResponse)
async def api_update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    """API: update user info."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/api/{user_id}/ban", response_model=UserResponse)
async def api_ban_user(user_id: int, ban_data: UserBan, db: Session = Depends(get_db)):
    """API: ban or unban a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_banned = ban_data.is_banned
    user.ban_reason = ban_data.ban_reason
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/api/{user_id}", status_code=204)
async def api_delete_user(user_id: int, db: Session = Depends(get_db)):
    """API: delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
