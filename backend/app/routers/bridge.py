"""Admin Bridge — push commands and messages to the frontend app."""
from __future__ import annotations

import json
import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app import auth, database

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/bridge", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))

# In-memory command queue (max 100 items)
_command_queue: deque[dict] = deque(maxlen=100)
_last_poll_id: int = 0


def _next_id() -> int:
    global _last_poll_id
    _last_poll_id += 1
    return _last_poll_id


@router.get("")
def bridge_page(request: Request, username: str = Depends(auth.require_admin)):
    """Frontend Control Panel page."""
    return _templates.TemplateResponse(
        "bridge/control.html",
        {
            "request": request,
            "username": username,
            "commands": list(_command_queue),
        },
    )


@router.post("/push-message")
def push_message(
    message: str = Form(""),
    msg_type: str = Form("info"),
    _username: str = Depends(auth.require_admin),
):
    """Push a notification message to the frontend."""
    if not message.strip():
        return RedirectResponse(url="/bridge", status_code=303)

    cmd = {
        "id": _next_id(),
        "type": "message",
        "msg_type": msg_type,  # info | success | warning | error
        "message": message.strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _command_queue.append(cmd)
    log.info("Bridge: pushed message to frontend: %s", message.strip())
    return RedirectResponse(url="/bridge", status_code=303)


@router.post("/push-command")
def push_command(
    action: str = Form(""),
    payload: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Push a command to the frontend (e.g. refresh, navigate, update-balance)."""
    if not action.strip():
        return RedirectResponse(url="/bridge", status_code=303)

    cmd = {
        "id": _next_id(),
        "type": "command",
        "action": action.strip(),
        "payload": payload.strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _command_queue.append(cmd)
    log.info("Bridge: pushed command: %s", action.strip())
    return RedirectResponse(url="/bridge", status_code=303)


@router.post("/api/clear")
def clear_commands(_username: str = Depends(auth.require_admin)):
    """Clear all commands from the queue."""
    _command_queue.clear()
    return RedirectResponse(url="/bridge", status_code=303)


# ---- Balance & Permissions & Transactions ----

@router.post("/update-balance")
def update_balance(
    account_id: str = Form("1"),
    balance_usd: str = Form(""),
    balance_khr: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Push updated balances to the frontend."""
    payload = {}
    if balance_usd.strip():
        payload["2"] = float(balance_usd)
    if balance_khr.strip():
        payload["1"] = float(balance_khr)
    if not payload:
        return RedirectResponse(url="/bridge", status_code=303)

    cmd = {
        "id": _next_id(),
        "type": "command",
        "action": "update-balance",
        "payload": json.dumps(payload),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _command_queue.append(cmd)
    log.info("Bridge: update-balance pushed: %s", payload)
    return RedirectResponse(url="/bridge", status_code=303)


@router.post("/set-permissions")
def set_permissions(
    allow_transfer: str = Form("on"),
    allow_scan: str = Form("on"),
    allow_topup: str = Form("on"),
    allow_withdraw: str = Form("on"),
    lock_screen: str = Form("off"),
    _username: str = Depends(auth.require_admin),
):
    """Push permission changes to the frontend."""
    perms = {
        "allow_transfer": allow_transfer == "on",
        "allow_scan": allow_scan == "on",
        "allow_topup": allow_topup == "on",
        "allow_withdraw": allow_withdraw == "on",
        "lock_screen": lock_screen == "on",
    }
    cmd = {
        "id": _next_id(),
        "type": "command",
        "action": "set-permissions",
        "payload": json.dumps(perms),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _command_queue.append(cmd)
    log.info("Bridge: permissions updated: %s", perms)
    return RedirectResponse(url="/bridge", status_code=303)


@router.get("/api/transactions")
def api_transactions(
    limit: int = 20,
    q: str = "",
    _username: str = Depends(auth.require_admin),
):
    """Query transfer records from orders table."""
    if q.strip():
        like = f"%{q.strip()}%"
        rows = database.fetchall(
            "SELECT o.*, c.username, c.first_name, c.last_name "
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
            "WHERE o.hash LIKE ? OR o.receiver LIKE ? OR o.bank LIKE ? "
            "  OR CAST(o.customer_id AS TEXT) LIKE ? "
            "ORDER BY o.updated_at DESC LIMIT ?",
            (like, like, like, like, limit),
        )
    else:
        rows = database.fetchall(
            "SELECT o.*, c.username, c.first_name, c.last_name "
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.telegram_id "
            "ORDER BY o.updated_at DESC LIMIT ?",
            (limit,),
        )
    return JSONResponse(content={"ok": True, "transactions": [dict(r) for r in rows]})
