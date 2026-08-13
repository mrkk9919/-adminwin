"""Pydantic schemas for User."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    is_bot: bool = False


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_banned: Optional[bool] = None
    ban_reason: Optional[str] = None


class UserBan(BaseModel):
    is_banned: bool
    ban_reason: Optional[str] = None


class UserResponse(UserBase):
    id: int
    is_banned: bool
    ban_reason: Optional[str] = None
    last_active_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    full_name: str

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
