"""Dashboard router — landing page with banking stats.

Shows at-a-glance metrics, transaction volume chart (30 days),
currency distribution, and recent transactions.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app import auth, database

router = APIRouter(prefix="/dashboard",
                   dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


def _overview() -> dict:
    with database.get_conn() as conn:
        total_users = conn.execute(
            "SELECT COUNT(*) FROM customers").fetchone()[0]
        active_users = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE is_active = 1 AND role != 'banned'"
        ).fetchone()[0]
        total_accounts = conn.execute(
            "SELECT COUNT(*) FROM accounts").fetchone()[0]
        active_accounts = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE status = 'active'"
        ).fetchone()[0]
        pending_kyc = conn.execute(
            "SELECT COUNT(*) FROM kyc_records WHERE status = 'pending'"
        ).fetchone()[0]
        pending_tx = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE status = 'pending'"
        ).fetchone()[0]

        # Today's transaction volume by currency
        today_vol = conn.execute(
            "SELECT currency, COALESCE(SUM(amount), 0) as vol "
            "FROM transactions WHERE date(created_at) = date('now') AND status = 'completed' "
            "GROUP BY currency"
        ).fetchall()
        today_khr = 0
        today_usd = 0
        for r in today_vol:
            if r["currency"] == "KHR":
                today_khr = r["vol"]
            else:
                today_usd = r["vol"]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "pending_kyc": pending_kyc,
            "pending_tx": pending_tx,
            "today_khr": today_khr,
            "today_usd": today_usd,
        }


def _transactions_chart(days: int = 30) -> list[dict]:
    """30-day daily transaction volume grouped by currency."""
    rows = database.fetchall(
        "SELECT date(created_at) as day, currency, COALESCE(SUM(amount), 0) as vol "
        "FROM transactions "
        "WHERE created_at >= date('now', ? || ' days') AND status = 'completed' "
        "GROUP BY day, currency ORDER BY day",
        (f"-{days}",),
    )
    # Merge KHR/USD into per-day records
    day_map: dict[str, dict] = {}
    for r in rows:
        d = r["day"]
        if d not in day_map:
            day_map[d] = {"day": d, "khr": 0, "usd": 0}
        if r["currency"] == "KHR":
            day_map[d]["khr"] = r["vol"]
        else:
            day_map[d]["usd"] = r["vol"]
    return list(day_map.values())


def _currency_breakdown() -> dict:
    """KHR vs USD volume and count comparison."""
    rows = database.fetchall(
        "SELECT currency, COUNT(*) as cnt, COALESCE(SUM(amount), 0) as vol "
        "FROM transactions WHERE status = 'completed' GROUP BY currency"
    )
    result = {"khr": {"count": 0, "volume": 0},
              "usd": {"count": 0, "volume": 0}}
    for r in rows:
        key = "khr" if r["currency"] == "KHR" else "usd"
        result[key] = {"count": r["cnt"], "volume": r["vol"]}
    return result


def _recent_transactions(limit: int = 10) -> list[dict]:
    rows = database.fetchall(
        "SELECT t.*, "
        "  (SELECT c.first_name || ' ' || c.last_name FROM customers c "
        "   JOIN accounts a ON a.customer_id = c.telegram_id WHERE a.id = t.from_account_id) as from_name, "
        "  (SELECT c.first_name || ' ' || c.last_name FROM customers c "
        "   JOIN accounts a ON a.customer_id = c.telegram_id WHERE a.id = t.to_account_id) as to_name "
        "FROM transactions t ORDER BY t.created_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def _bot_health() -> list[dict]:
    rows = database.fetchall(
        "SELECT bot_name, last_heartbeat, version, uptime_seconds, meta "
        "FROM bot_heartbeats ORDER BY bot_name"
    )
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    out = []
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
            s = "unknown"
        elif age < 60:
            s = "alive"
        elif age < 300:
            s = "degraded"
        else:
            s = "dead"
        out.append({
            "bot_name": r["bot_name"],
            "version": r["version"],
            "status": s,
            "age_seconds": int(age) if age is not None else None,
        })
    return out


@router.get("")
def dashboard(request: Request, username: str = Depends(auth.require_admin)):
    return _templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": username,
            "active": "dashboard",
            "overview": _overview(),
            "chart_data": _transactions_chart(),
            "currency_breakdown": _currency_breakdown(),
            "recent_tx": _recent_transactions(),
            "bots": _bot_health(),
        },
    )


@router.get("/api/summary")
def api_summary():
    return {
        "overview": _overview(),
        "chart_data": _transactions_chart(),
        "currency_breakdown": _currency_breakdown(),
        "recent_tx": _recent_transactions(),
        "bots": _bot_health(),
    }
