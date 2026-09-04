"""Push notification management routes.

Provides API endpoints for:
- Registering FCM/APNs device tokens
- Toggling push notifications on/off
- Sending test notifications
- Viewing push notification history
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path

from app import auth, database
from app.services.fcm import (
    send_push,
    send_transfer_received,
    send_transfer_sent,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/push")
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


# --- API Endpoints ---


@router.post("/api/register")
def register_token(
    telegram_id: int = Form(...),
    fcm_token: str = Form(""),
    apns_token: str = Form(""),
    device_type: str = Form("android"),
    _username: str = Depends(auth.require_admin),
):
    """
    Register or update a user's push notification token.

    Args:
        telegram_id: User's Telegram ID
        fcm_token: FCM token for Android devices
        apns_token: APNs token for iOS devices
        device_type: Device type (android/ios)
    """
    now = datetime.now().isoformat()

    # Check if customer exists
    customer = database.fetchone(
        "SELECT telegram_id FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Update FCM token if provided
    if fcm_token:
        database.execute(
            """
            UPDATE customers
            SET fcm_token = ?, push_token_updated_at = ?
            WHERE telegram_id = ?
            """,
            (fcm_token, now, telegram_id),
        )
        log.info(f"FCM token registered for user {telegram_id}")

    # Update APNs token if provided
    if apns_token:
        database.execute(
            """
            UPDATE customers
            SET apns_token = ?, push_token_updated_at = ?
            WHERE telegram_id = ?
            """,
            (apns_token, now, telegram_id),
        )
        log.info(f"APNs token registered for user {telegram_id}")

    return JSONResponse(content={
        "success": True,
        "message": "Token registered successfully",
    })


@router.post("/api/toggle")
def toggle_push(
    telegram_id: int = Form(...),
    enabled: bool = Form(True),
    _username: str = Depends(auth.require_admin),
):
    """
    Toggle push notifications on/off for a user.

    Args:
        telegram_id: User's Telegram ID
        enabled: Whether to enable or disable push
    """
    customer = database.fetchone(
        "SELECT telegram_id FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    database.execute(
        "UPDATE customers SET push_enabled = ? WHERE telegram_id = ?",
        (1 if enabled else 0, telegram_id),
    )

    status_text = "enabled" if enabled else "disabled"
    log.info(f"Push notifications {status_text} for user {telegram_id}")

    return JSONResponse(content={
        "success": True,
        "message": f"Push notifications {status_text}",
    })


@router.post("/api/send-test")
def send_test_notification(
    telegram_id: int = Form(...),
    title: str = Form("测试通知"),
    body: str = Form("这是一条测试推送消息"),
    _username: str = Depends(auth.require_admin_or_push_api_key),
):
    """
    Send a test push notification to a user.

    Args:
        telegram_id: User's Telegram ID
        title: Notification title
        body: Notification body
    """
    customer = database.fetchone(
        "SELECT * FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if not customer["fcm_token"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no FCM token registered",
        )

    if not customer["push_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Push notifications disabled for this user",
        )

    result = send_push(
        token=customer["fcm_token"],
        title=title,
        body=body,
        data={"type": "test"},
    )

    return JSONResponse(content={
        "success": result.get("success", 0) > 0,
        "result": result,
    })


@router.get("/api/status")
def get_push_status(
    telegram_id: int,
    _username: str = Depends(auth.require_admin_or_push_api_key),
):
    """
    Get push notification status for a user.
    """
    customer = database.fetchone(
        """
        SELECT telegram_id, fcm_token, apns_token, push_enabled, push_token_updated_at
        FROM customers WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return JSONResponse(content={
        "success": True,
        "data": {
            "telegram_id": customer["telegram_id"],
            "has_fcm_token": bool(customer["fcm_token"]),
            "has_apns_token": bool(customer["apns_token"]),
            "push_enabled": bool(customer["push_enabled"]),
            "token_updated_at": customer["push_token_updated_at"],
        },
    })


# --- Transfer Notification APIs ---


class TransferNotificationRequest(BaseModel):
    telegram_id: int
    amount: str
    currency: str
    counterparty_name: str
    transaction_id: str
    timestamp: Optional[str] = None


@router.post("/api/transfer-sent")
def transfer_sent_notification(
    req: TransferNotificationRequest,
    _username: str = Depends(auth.require_admin_or_push_api_key),
):
    """
    Send a "transfer sent" notification to the sender.
    
    This is called by the Go bot after a successful transfer.
    """
    customer = database.fetchone(
        "SELECT * FROM customers WHERE telegram_id = ?",
        (req.telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if not customer["fcm_token"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": False, "error": "No FCM token registered"},
        )

    if not customer["push_enabled"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": False, "error": "Push notifications disabled"},
        )

    result = send_transfer_sent(
        token=customer["fcm_token"],
        amount=req.amount,
        currency=req.currency,
        receiver_name=req.counterparty_name,
        transaction_id=req.transaction_id,
        timestamp=req.timestamp,
    )

    return JSONResponse(content={
        "success": result.get("success", 0) > 0,
        "result": result,
    })


@router.post("/api/transfer-received")
def transfer_received_notification(
    req: TransferNotificationRequest,
    _username: str = Depends(auth.require_admin_or_push_api_key),
):
    """
    Send a "transfer received" notification to the recipient.
    
    This is called by the Go bot or backend after a successful transfer.
    """
    customer = database.fetchone(
        "SELECT * FROM customers WHERE telegram_id = ?",
        (req.telegram_id,),
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    if not customer["fcm_token"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": False, "error": "No FCM token registered"},
        )

    if not customer["push_enabled"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": False, "error": "Push notifications disabled"},
        )

    result = send_transfer_received(
        token=customer["fcm_token"],
        amount=req.amount,
        currency=req.currency,
        sender_name=req.counterparty_name,
        transaction_id=req.transaction_id,
        timestamp=req.timestamp,
    )

    return JSONResponse(content={
        "success": result.get("success", 0) > 0,
        "result": result,
    })


# --- Page Routes ---


@router.get("")
def push_page(request: Request, username: str = Depends(auth.require_admin)):
    """Push notification management page."""
    # Get customers with push tokens
    customers = database.fetchall(
        """
        SELECT telegram_id, username, first_name, last_name, phone,
               fcm_token, apns_token, push_enabled, push_token_updated_at
        FROM customers
        WHERE fcm_token IS NOT NULL OR apns_token IS NOT NULL
        ORDER BY push_token_updated_at DESC
        LIMIT 50
        """
    )

    return _templates.TemplateResponse(
        "push/manage.html",
        {
            "request": request,
            "username": username,
            "customers": customers,
        },
    )
