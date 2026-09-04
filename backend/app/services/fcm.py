"""FCM (Firebase Cloud Messaging) push notification service.

Provides functions to send push notifications to Android devices via Firebase.
Used for transfer notifications, balance updates, and other banking alerts.

This module now supports two modes:
- HTTP v1 using a Google service account JSON placed at admin/service-account.json
  (preferred when the file exists). This uses a JWT assertion to obtain an
  OAuth2 access token and calls the v1 endpoint:
    https://fcm.googleapis.com/v1/projects/{project_id}/messages:send

- Legacy server key fallback using FCM_SERVER_KEY in .env and the legacy
  endpoint https://fcm.googleapis.com/fcm/send
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import jwt  # PyJWT

from app.config import get_settings

log = logging.getLogger(__name__)

LEGACY_FCM_URL = "https://fcm.googleapis.com/fcm/send"
# Path to service account (relative to admin/)
SERVICE_ACCOUNT_PATH = Path(__file__).resolve().parent.parent / "service-account.json"

# Simple token cache
_token_cache: dict[str, Any] = {"access_token": None, "expiry": 0}


def _load_service_account() -> Optional[dict[str, Any]]:
    if not SERVICE_ACCOUNT_PATH.exists():
        return None
    try:
        with open(SERVICE_ACCOUNT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load service account: {e}")
        return None


def _get_access_token(sa: dict[str, Any]) -> Optional[str]:
    """Return a cached access_token or obtain a new one using JWT assertion.

    Uses the OAuth2 JWT Bearer flow:
    POST {token_uri} grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<jwt>
    """
    now = int(time.time())
    if _token_cache.get("access_token") and _token_cache.get("expiry", 0) > now + 30:
        return _token_cache["access_token"]

    token_uri = sa.get("token_uri")
    client_email = sa.get("client_email")
    private_key = sa.get("private_key")
    # Use firebase.messaging scope; cloud-platform is also acceptable
    scope = "https://www.googleapis.com/auth/firebase.messaging"

    if not (token_uri and client_email and private_key):
        log.error("Service account JSON missing required fields")
        return None

    # Construct JWT assertion
    payload = {
        "iss": client_email,
        "scope": scope,
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }

    try:
        signed_jwt = jwt.encode(payload, private_key, algorithm="RS256")
    except Exception as e:
        log.error(f"Failed to sign JWT: {e}")
        return None

    try:
        resp = httpx.post(
            token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": signed_jwt,
            },
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        access_token = body.get("access_token")
        expires_in = int(body.get("expires_in", 3600))
        if access_token:
            _token_cache["access_token"] = access_token
            _token_cache["expiry"] = int(time.time()) + expires_in
            return access_token
        log.error(f"No access_token in token response: {body}")
        return None
    except Exception as e:
        log.error(f"Error obtaining access token: {e}")
        try:
            log.debug(f"token response text: {resp.text}")
        except Exception:
            pass
        return None


def _send_push_v1(
    sa: dict[str, Any],
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    project_id = sa.get("project_id")
    if not project_id:
        log.error("service account missing project_id")
        return {"success": False, "error": "Missing project_id"}

    access_token = _get_access_token(sa)
    if not access_token:
        return {"success": False, "error": "Failed to obtain access token"}

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    message: dict[str, Any] = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
        }
    }
    if data:
        # v1 expects string values for data
        message["message"]["data"] = {k: str(v) for k, v in data.items()}

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        resp = httpx.post(url, json=message, headers=headers, timeout=10)
        # v1 returns 200 with message name on success
        if resp.status_code == 200:
            try:
                return {"success": True, "response": resp.json()}
            except Exception:
                return {"success": True, "response_text": resp.text}
        else:
            # return details for debugging
            try:
                return {"success": False, "status": resp.status_code, "response": resp.json()}
            except Exception:
                return {"success": False, "status": resp.status_code, "response_text": resp.text}
    except httpx.TimeoutException:
        log.error("FCM v1 push request timed out")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        log.error(f"FCM v1 push error: {e}")
        return {"success": False, "error": str(e)}


def _send_push_legacy(
    server_key: str,
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    sound: str = "default",
    priority: str = "high",
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "to": token,
        "notification": {"title": title, "body": body, "sound": sound},
        "priority": priority,
    }
    if data:
        message["data"] = {k: str(v) for k, v in data.items()}

    headers = {"Authorization": f"key={server_key}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(LEGACY_FCM_URL, json=message, headers=headers, timeout=10)
        try:
            return resp.json()
        except Exception:
            return {"success": False, "response_text": resp.text}
    except httpx.TimeoutException:
        log.error("Legacy FCM push request timed out")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        log.error(f"Legacy FCM push error: {e}")
        return {"success": False, "error": str(e)}


def send_push(
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    sound: str = "default",
    priority: str = "high",
) -> dict[str, Any]:
    """
    Send an FCM push notification to a single device.

    Prefers HTTP v1 when a service account JSON is present at
    admin/service-account.json; otherwise falls back to legacy server key.
    """
    settings = get_settings()

    if not token:
        log.warning("Empty FCM token, skipping push notification")
        return {"success": False, "error": "Empty token"}

    sa = _load_service_account()
    if sa is not None:
        log.debug("Using FCM HTTP v1 with service account")
        return _send_push_v1(sa, token, title, body, data)

    # Fallback to legacy server key
    if not settings.fcm_server_key:
        log.warning("FCM not configured (no service account and no server key)")
        return {"success": False, "error": "FCM not configured"}

    return _send_push_legacy(settings.fcm_server_key, token, title, body, data, sound, priority)


def send_multicast_push(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Send push notifications to multiple devices.

    Args:
        tokens: List of FCM device tokens
        title: Notification title
        body: Notification body
        data: Optional data payload

    Returns:
        Summary of results
    """
    success = 0
    failed = 0
    errors: list[str] = []

    for token in tokens:
        result = send_push(token, title, body, data)
        if result.get("success", 0) or result.get("success") is True:
            success += 1
        else:
            failed += 1
            errors.append(str(result))

    return {
        "success": success,
        "failed": failed,
        "errors": errors,
    }


# --- Notification templates for common use cases ---


def send_transfer_received(
    token: str,
    amount: str,
    currency: str,
    sender_name: str,
    transaction_id: str,
    timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send a "transfer received" notification to the recipient.

    Args:
        token: FCM device token
        amount: Transfer amount
        currency: Currency code (USD/KHR)
        sender_name: Name of the sender
        transaction_id: Transaction ID for deep linking
    """
    title = "✅ 收到转账"
    body = f"您收到 {currency} {amount} 转账，付款人：{sender_name}"

    data = {
        "type": "transfer_received",
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "sender_name": sender_name,
    }
    if timestamp:
        data["timestamp"] = timestamp

    return send_push(token, title, body, data)


def send_transfer_sent(
    token: str,
    amount: str,
    currency: str,
    receiver_name: str,
    transaction_id: str,
    timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send a "transfer successful" notification to the sender.

    Args:
        token: FCM device token
        amount: Transfer amount
        currency: Currency code
        receiver_name: Name of the recipient
        transaction_id: Transaction ID for deep linking
    """
    title = "💸 转账成功"
    body = f"您已成功向 {receiver_name} 转账 {currency} {amount}"

    data = {
        "type": "transfer_sent",
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "receiver_name": receiver_name,
    }
    if timestamp:
        data["timestamp"] = timestamp

    return send_push(token, title, body, data)


def send_balance_update(
    token: str,
    balance_usd: str,
    balance_khr: str,
) -> dict[str, Any]:
    """
    Send a balance update notification.

    Args:
        token: FCM device token
        balance_usd: USD balance
        balance_khr: KHR balance
    """
    title = "💰 余额更新"
    body = f"USD: {balance_usd} | KHR: {balance_khr}"

    data = {
        "type": "balance_update",
        "balance_usd": balance_usd,
        "balance_khr": balance_khr,
    }

    return send_push(token, title, body, data)


def send_security_alert(
    token: str,
    alert_type: str,
    message: str,
) -> dict[str, Any]:
    """
    Send a security alert notification.

    Args:
        token: FCM device token
        alert_type: Type of security alert
        message: Alert message
    """
    title = "🔒 安全提醒"
    body = message

    data = {
        "type": "security_alert",
        "alert_type": alert_type,
    }

    return send_push(token, title, body, data)
