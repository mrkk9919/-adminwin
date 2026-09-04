"""Settings router — system status and transaction limits."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings

router = APIRouter(prefix="/settings", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _service_status() -> list[dict]:
    """Check status of platform services."""
    services = []

    # Core Banking API (mock status)
    services.append({
        "name": "Core Banking API",
        "description": "Transaction processing and account management",
        "status": "operational",
    })

    # KYC Verification Service
    with database.get_conn() as conn:
        pending = conn.execute("SELECT COUNT(*) FROM kyc_records WHERE status = 'pending'").fetchone()[0]
    services.append({
        "name": "KYC Verification Service",
        "description": f"Identity verification workflow ({pending} pending)",
        "status": "operational",
    })

    # SMS Gateway
    settings = get_settings()
    services.append({
        "name": "SMS Gateway",
        "description": f"Provider: {settings.sms_provider}",
        "status": "operational" if settings.sms_provider else "degraded",
    })

    # Telegram Bot API
    services.append({
        "name": "Telegram Bot API",
        "description": f"Token: ...{settings.bot_token[-8:]}",
        "status": "operational",
    })

    return services


def _transaction_limits() -> dict:
    """Global transaction limits (read-only configuration)."""
    return {
        "khr": {
            "min": 1000,
            "max": 50000000,
            "daily_max": 200000000,
        },
        "usd": {
            "min": 100,     # stored as cents
            "max": 1000000,  # $10,000
            "daily_max": 5000000,  # $50,000
        },
    }


@router.get("")
def settings_page(request: Request, username: str = Depends(auth.require_admin)):
    settings = get_settings()
    db = database.db_info()

    return _templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "username": username,
            "active": "settings",
            "services": _service_status(),
            "limits": _transaction_limits(),
            "db": db,
        },
    )
