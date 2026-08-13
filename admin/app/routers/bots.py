"""Bots router — health monitoring via Telegram Bot API + heartbeat DB.

Bot tokens come from two sources:
* .env — BOT_TOKEN (main), ABA_BOT_TOKEN, EXTRA_BOT_TOKENS
* the `bots` table — tokens bound through the admin panel UI
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings

router = APIRouter(prefix="/bots", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))

_TELEGRAM_API = "https://api.telegram.org"


# ── Telegram API helpers ─────────────────────────────────────────────


async def _call_bot_api(token: str, method: str, **kwargs) -> dict | None:
    """Call a Telegram Bot API method. Returns result dict or None on error."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_TELEGRAM_API}/bot{token}/{method}",
                json=kwargs if kwargs else None,
            )
            data = resp.json()
            if data.get("ok"):
                return data["result"]
            return {"_error": data.get("description", "Unknown API error")}
    except Exception as e:
        return {"_error": str(e)}


async def _probe_bot(token: str) -> dict:
    """Probe a single bot via Telegram API. Returns comprehensive info."""
    info = {"token_tail": f"...{token[-8:]}", "api_reachable": False}

    # getMe — basic bot identity
    me = await _call_bot_api(token, "getMe")
    if me and "_error" not in me:
        info["api_reachable"] = True
        info["id"] = me.get("id")
        info["first_name"] = me.get("first_name")
        info["username"] = me.get("username")
        info["can_join_groups"] = me.get("can_join_groups")
        info["can_read_all_messages"] = me.get("can_read_all_group_messages")
        info["supports_inline"] = me.get("supports_inline_queries")
    else:
        info["error"] = (me or {}).get("_error", "Unreachable")
        return info

    # getWebhookInfo — webhook / long-polling status
    wh = await _call_bot_api(token, "getWebhookInfo")
    if wh and "_error" not in wh:
        info["webhook_url"] = wh.get("url") or "(long polling)"
        info["pending_update_count"] = wh.get("pending_update_count", 0)
        info["last_error_date"] = wh.get("last_error_date")
        info["last_error_message"] = wh.get("last_error_message")
        info["max_connections"] = wh.get("max_connections")
        info["allowed_updates"] = wh.get("allowed_updates", [])

    # getMyCommands — registered commands
    cmds = await _call_bot_api(token, "getMyCommands")
    if cmds and not isinstance(cmds, dict):
        info["commands"] = [{"command": c["command"],
                             "description": c["description"]} for c in cmds]
        info["command_count"] = len(cmds)
    else:
        info["commands"] = []
        info["command_count"] = 0

    return info


# ── Bot registry (env + bound tokens) ────────────────────────────────


def _ensure_bots_table() -> None:
    """Create the bots table if tgbot migrations haven't run yet."""
    database.execute(
        "CREATE TABLE IF NOT EXISTS bots ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL DEFAULT '', "
        "token TEXT NOT NULL UNIQUE, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")


def _bound_bots() -> list[dict]:
    _ensure_bots_table()
    rows = database.fetchall(
        "SELECT id, name, token, created_at FROM bots ORDER BY id")
    return [dict(r) for r in rows]


def _all_token_entries() -> list[dict]:
    """All known tokens: {token, source, name, bot_id}.

    source is 'env' for .env-configured bots and 'bound' for tokens
    added through the admin panel.
    """
    settings = get_settings()
    entries: list[dict] = []
    seen: set[str] = set()

    def add(token: str, source: str, name: str, bot_id: int | None = None):
        if not token or token in seen:
            return
        seen.add(token)
        e = {"token": token, "source": source, "name": name}
        if bot_id:
            e["bot_id"] = bot_id
        entries.append(e)

    add(settings.bot_token, "env", "Main Bot")
    add(settings.aba_bot_token, "env", settings.aba_bot_name)
    if settings.extra_bot_tokens:
        for i, tok in enumerate(
                t.strip() for t in settings.extra_bot_tokens.split(",")):
            add(tok, "env", f"Extra #{i + 1}")
    for b in _bound_bots():
        add(b["token"], "bound", b["name"] or "Bound Bot", b["id"])
    return entries


# ── Heartbeat / activity helpers ─────────────────────────────────────


def _heartbeat_data() -> dict[str, dict]:
    """Read heartbeat data from DB, keyed by bot_name."""
    rows = database.fetchall(
        "SELECT bot_name, last_heartbeat, status, version, uptime_seconds, meta "
        "FROM bot_heartbeats ORDER BY bot_name"
    )
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    result = {}
    for r in rows:
        hb = r["last_heartbeat"]
        if isinstance(hb, str):
            try:
                hb = _dt.datetime.fromisoformat(hb.replace("Z", "+00:00"))
            except ValueError:
                hb = None
        if hb and hb.tzinfo is None:
            hb = hb.replace(tzinfo=_dt.timezone.utc)
        age = (now - hb).total_seconds() if hb else None
        if age is None:
            derived = "unknown"
        elif age < 60:
            derived = "alive"
        elif age < 300:
            derived = "degraded"
        else:
            derived = "dead"
        result[r["bot_name"]] = {
            "version": r["version"],
            "uptime_seconds": r["uptime_seconds"],
            "last_heartbeat": hb.isoformat() if hb else None,
            "age_seconds": int(age) if age is not None else None,
            "heartbeat_status": derived,
            "meta": r["meta"],
        }
    return result


def _active_customers_5m() -> int:
    row = database.fetchone(
        "SELECT COUNT(DISTINCT customer_id) AS cnt FROM messages "
        "WHERE created_at > datetime('now', '-5 minutes')"
    )
    return row["cnt"] if row else 0


# ── Pages ────────────────────────────────────────────────────────────


@router.get("")
def bots_page(
    request: Request,
    msg: str = "",
    username: str = Depends(auth.require_admin),
):
    """Render the bot health page (initial load without API calls)."""
    return _templates.TemplateResponse(
        "bots/health.html",
        {
            "request": request,
            "username": username,
            "active": "bots",
            "heartbeats": _heartbeat_data(),
            "active_customers": _active_customers_5m(),
            "bound_bots": _bound_bots(),
            "bot_count": len(_all_token_entries()),
            "msg": msg,
        },
    )


# ── Bind / unbind tokens ─────────────────────────────────────────────


@router.post("/bind")
async def bind_bot(
    token: str = Form(...),
    name: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    """Validate a bot token via getMe and store it in the bots table."""
    token = token.strip()
    if not token:
        return RedirectResponse(url="/bots?msg=empty", status_code=303)

    # Don't bind a token that's already configured in .env.
    known = {e["token"] for e in _all_token_entries()}
    if token in known:
        return RedirectResponse(url="/bots?msg=dup", status_code=303)

    me = await _call_bot_api(token, "getMe")
    if not me or "_error" in me:
        err = quote((me or {}).get("_error", "Unreachable")[:80])
        return RedirectResponse(
            url=f"/bots?msg=invalid:{err}", status_code=303)

    try:
        database.execute(
            "INSERT INTO bots (name, token) VALUES (?, ?)",
            (name.strip() or me.get("first_name", ""), token),
        )
    except Exception:
        return RedirectResponse(url="/bots?msg=dup", status_code=303)
    return RedirectResponse(url="/bots?msg=bound", status_code=303)


@router.post("/{bot_id}/unbind")
async def unbind_bot(bot_id: int, _username: str = Depends(auth.require_admin)):
    """Remove a bound bot token from the bots table."""
    _ensure_bots_table()
    database.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    return RedirectResponse(url="/bots?msg=unbound", status_code=303)


# ── Probe APIs ───────────────────────────────────────────────────────


@router.get("/api/probe")
async def api_probe(_username: str = Depends(auth.require_admin)):
    """Probe all known bots (env + bound) via Telegram Bot API."""
    entries = _all_token_entries()
    if not entries:
        return {"error": "No bot tokens configured"}

    bots = []
    for e in entries:
        info = await _probe_bot(e["token"])
        info["source"] = e["source"]
        info["label"] = e["name"]
        if e.get("bot_id"):
            info["bot_id"] = e["bot_id"]
        bots.append(info)

    return {
        "bots": bots,
        "heartbeats": _heartbeat_data(),
        "active_customers_5m": _active_customers_5m(),
    }


@router.get("/api/probe/{bot_token}")
async def api_probe_token(bot_token: str, _username: str = Depends(auth.require_admin)):
    """Probe any bot by token (for monitoring multiple bots)."""
    info = await _probe_bot(bot_token)
    return {"bot": info}


@router.post("/refresh")
async def refresh(request: Request, _username: str = Depends(auth.require_admin)):
    """Refresh bot info from Telegram API and redirect back."""
    for e in _all_token_entries():
        await _probe_bot(e["token"])
    return RedirectResponse(url="/bots", status_code=status.HTTP_303_SEE_OTHER)
