"""Notification groups router — manage groups for transaction notifications."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/groups", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _ensure_groups_table():
    """Safety net: ensure table exists even if migration hasn't run."""
    database.execute(
        "CREATE TABLE IF NOT EXISTS notification_groups ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "bot_name TEXT NOT NULL DEFAULT 'aba-bank', "
        "chat_id INTEGER NOT NULL UNIQUE, "
        "chat_title TEXT NOT NULL DEFAULT '', "
        "invite_link TEXT DEFAULT '', "
        "is_active INTEGER NOT NULL DEFAULT 1, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )


@router.get("")
def groups_list(request: Request, username: str = Depends(auth.require_admin)):
    """List all notification groups."""
    _ensure_groups_table()
    rows = database.fetchall(
        "SELECT * FROM notification_groups ORDER BY created_at DESC"
    )
    return _templates.TemplateResponse(
        "groups/list.html",
        {
            "request": request,
            "username": username,
            "active": "groups",
            "groups": [dict(r) for r in rows],
        },
    )


@router.get("/add")
def groups_add_page(request: Request, username: str = Depends(auth.require_admin)):
    """Show form to add a new group."""
    return _templates.TemplateResponse(
        "groups/add.html",
        {
            "request": request,
            "username": username,
            "active": "groups",
        },
    )


@router.post("/add")
async def groups_add(
    chat_id: str = Form(...),
    chat_title: str = Form(""),
    invite_link: str = Form(""),
    username: str = Depends(auth.require_admin),
):
    """Add a new notification group."""
    _ensure_groups_table()
    
    try:
        chat_id_int = int(chat_id)
    except ValueError:
        raise HTTPException(400, detail="Invalid chat ID (must be a number)")
    
    # Check if group already exists
    existing = database.fetchone(
        "SELECT id FROM notification_groups WHERE chat_id = ?", (chat_id_int,)
    )
    if existing:
        raise HTTPException(400, detail="Group already exists")
    
    database.execute(
        "INSERT INTO notification_groups (chat_id, chat_title, invite_link) "
        "VALUES (?, ?, ?)",
        (chat_id_int, chat_title.strip() or f"Group {chat_id_int}", invite_link.strip() or ""),
    )
    
    log.info("user %s added notification group %s (%s)",
             username, chat_id_int, chat_title)
    
    return RedirectResponse(url="/groups?added=ok", status_code=303)


@router.post("/{group_id}/toggle")
async def groups_toggle(
    group_id: int,
    username: str = Depends(auth.require_admin),
):
    """Toggle group active status."""
    _ensure_groups_table()
    
    group = database.fetchone(
        "SELECT * FROM notification_groups WHERE id = ?", (group_id,)
    )
    if not group:
        raise HTTPException(404, detail="Group not found")
    
    new_status = 0 if group["is_active"] else 1
    database.execute(
        "UPDATE notification_groups SET is_active = ? WHERE id = ?",
        (new_status, group_id),
    )
    
    log.info("user %s toggled group %s to %s",
             username, group_id, "active" if new_status else "inactive")
    
    return RedirectResponse(url="/groups", status_code=303)


@router.post("/{group_id}/delete")
async def groups_delete(
    group_id: int,
    username: str = Depends(auth.require_admin),
):
    """Delete a notification group."""
    _ensure_groups_table()
    
    database.execute("DELETE FROM notification_groups WHERE id = ?", (group_id,))
    
    log.info("user %s deleted notification group %s", username, group_id)
    
    return RedirectResponse(url="/groups?deleted=ok", status_code=303)
