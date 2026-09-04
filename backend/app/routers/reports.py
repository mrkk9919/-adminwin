"""Reports router — analytics and charts."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app import auth, database

router = APIRouter(prefix="/reports",
                   dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


def _daily_volume(days: int = 30) -> list[dict]:
    rows = database.fetchall(
        "SELECT date(created_at) as day, currency, COUNT(*) as cnt, SUM(amount) as vol "
        "FROM transactions "
        "WHERE created_at >= date('now', ? || ' days') AND status = 'completed' "
        "GROUP BY day, currency ORDER BY day",
        (f"-{days}",),
    )
    day_map: dict[str, dict] = {}
    for r in rows:
        d = r["day"]
        if d not in day_map:
            day_map[d] = {"day": d, "khr_count": 0,
                          "khr_vol": 0, "usd_count": 0, "usd_vol": 0}
        if r["currency"] == "KHR":
            day_map[d]["khr_count"] = r["cnt"]
            day_map[d]["khr_vol"] = r["vol"]
        else:
            day_map[d]["usd_count"] = r["cnt"]
            day_map[d]["usd_vol"] = r["vol"]
    return list(day_map.values())


def _currency_summary() -> dict:
    rows = database.fetchall(
        "SELECT currency, COUNT(*) as cnt, SUM(amount) as vol "
        "FROM transactions WHERE status = 'completed' GROUP BY currency"
    )
    result = {"khr": {"count": 0, "volume": 0},
              "usd": {"count": 0, "volume": 0}}
    for r in rows:
        key = "khr" if r["currency"] == "KHR" else "usd"
        result[key] = {"count": r["cnt"], "volume": r["vol"]}
    return result


def _account_stats() -> dict:
    with database.get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE status = 'active'").fetchone()[0]
        frozen = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE status = 'frozen'").fetchone()[0]
    return {"total": total, "active": active, "frozen": frozen}


@router.get("")
def reports_page(request: Request, username: str = Depends(auth.require_admin)):
    daily = _daily_volume()
    currency = _currency_summary()
    accounts = _account_stats()
    total_vol_khr = currency["khr"]["volume"]
    total_vol_usd = currency["usd"]["volume"]

    return _templates.TemplateResponse(
        "reports/index.html",
        {
            "request": request,
            "username": username,
            "active": "reports",
            "daily_data": daily,
            "currency": currency,
            "accounts": accounts,
            "total_vol_khr": total_vol_khr,
            "total_vol_usd": total_vol_usd,
        },
    )
