"""SMS OTP router — send OTP, view logs, check quota."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database
from app.config import get_settings
from app.services import sms as sms_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


@router.get("")
def sms_dashboard(
    request: Request,
    username: str = Depends(auth.require_admin),
):
    logs = [
        dict(r) for r in database.fetchall(
            "SELECT * FROM sms_logs ORDER BY created_at DESC LIMIT 50"
        )
    ]
    total = database.fetchone("SELECT COUNT(*) AS cnt FROM sms_logs")
    failed = database.fetchone(
        "SELECT COUNT(*) AS cnt FROM sms_logs WHERE status = 'failed'"
    )
    total_cost = database.fetchone(
        "SELECT COALESCE(SUM(cost_cents), 0) AS total FROM sms_logs"
    )
    return _templates.TemplateResponse(
        "sms/dashboard.html",
        {
            "request": request,
            "username": username,
            "logs": logs,
            "stats": {
                "total": total["cnt"] if total else 0,
                "failed": failed["cnt"] if failed else 0,
                "total_cost_usd": (total_cost["total"] if total_cost else 0) / 100,
                "quota": 1000,  # Mock quota
                "remaining": 1000 - (total["cnt"] if total else 0),
            },
            "provider": get_settings().sms_provider,
        },
    )


@router.post("/send")
async def sms_send(
    phone: str = Form(...),
    template: str = Form("otp"),
    _username: str = Depends(auth.require_admin),
):
    phone = phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    otp = sms_service.generate_otp()

    if template == "otp":
        message = f"Wing Bank: Your OTP code is {otp}. Valid for 5 minutes."
    else:
        message = f"Wing Bank: {otp}"

    provider = sms_service.get_provider()
    result = await provider.send(phone, message)

    database.execute(
        "INSERT INTO sms_logs (phone, otp_code, message, provider, provider_msg_id, status, cost_cents, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            phone,
            otp,
            message,
            get_settings().sms_provider,
            result.provider_msg_id,
            "sent" if result.ok else "failed",
            result.cost_cents,
            result.error,
        ),
    )

    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMS send failed: {result.error}",
        )

    return RedirectResponse(url="/sms", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logs")
def sms_logs(
    request: Request,
    phone: str = "",
    username: str = Depends(auth.require_admin),
):
    if phone.strip():
        logs = [
            dict(r) for r in database.fetchall(
                "SELECT * FROM sms_logs WHERE phone LIKE ? ORDER BY created_at DESC LIMIT 100",
                (f"%{phone.strip()}%",),
            )
        ]
    else:
        logs = [
            dict(r) for r in database.fetchall(
                "SELECT * FROM sms_logs ORDER BY created_at DESC LIMIT 100"
            )
        ]
    return _templates.TemplateResponse(
        "sms/logs.html",
        {"request": request, "username": username, "logs": logs, "phone": phone},
    )


@router.get("/verify")
def sms_verify_check(
    phone: str = "",
    code: str = "",
    username: str = Depends(auth.require_admin),
):
    """Check if an OTP code matches a recent sent code for a phone number."""
    if not phone or not code:
        return {"verified": False, "message": "Provide phone and code parameters."}

    row = database.fetchone(
        "SELECT * FROM sms_logs "
        "WHERE phone = ? AND otp_code = ? AND status = 'sent' "
        "  AND created_at > datetime('now', '-10 minutes') "
        "ORDER BY created_at DESC LIMIT 1",
        (phone.strip(), code.strip()),
    )
    return {
        "verified": row is not None,
        "message": "OTP verified." if row else "OTP not found or expired.",
    }
