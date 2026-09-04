"""Client Bridge — public API endpoints for the frontend app to poll commands.

Unlike the admin /bridge endpoints (which require auth), these are public
so the mobile/web frontend can connect without admin credentials.
Commands are pushed from the admin panel and picked up by connected clients.
"""
from __future__ import annotations

import json
import logging
import time
from collections import deque

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client/bridge")

# Per-device command queues: {device_id: deque[dict]}
_device_queues: dict[str, deque[dict]] = {}
_last_cmd_id: int = 0

# Global broadcast queue — commands sent to all devices
_broadcast_queue: deque[dict] = deque(maxlen=100)

MAX_QUEUE_SIZE = 100


def _next_id() -> int:
    global _last_cmd_id
    _last_cmd_id += 1
    return _last_cmd_id


def push_broadcast_command(action: str, payload: dict | str = ""):
    """Push a command to all connected devices (called from admin bridge)."""
    cmd = {
        "id": _next_id(),
        "type": "command",
        "action": action,
        "payload": payload if isinstance(payload, str) else json.dumps(payload),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _broadcast_queue.append(cmd)
    log.info("Client bridge: broadcast command %s", action)


def push_broadcast_message(message: str, msg_type: str = "info"):
    """Push a notification message to all connected devices."""
    cmd = {
        "id": _next_id(),
        "type": "message",
        "msg_type": msg_type,
        "message": message,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _broadcast_queue.append(cmd)
    log.info("Client bridge: broadcast message: %s", message[:50])


@router.get("/poll")
def poll_commands(
    device_id: str = Query("default"),
    since_id: int = Query(0),
):
    """
    Poll for new commands.
    
    Args:
        device_id: Unique device identifier
        since_id: Last command ID received (only return newer commands)
    """
    # Get device-specific queue
    device_queue = _device_queues.get(device_id, deque())
    
    # Collect new commands from both broadcast and device-specific queues
    new_cmds = []
    
    # From broadcast queue
    for cmd in _broadcast_queue:
        if cmd["id"] > since_id:
            new_cmds.append(cmd)
    
    # From device-specific queue
    for cmd in device_queue:
        if cmd["id"] > since_id:
            new_cmds.append(cmd)
    
    # Sort by ID
    new_cmds.sort(key=lambda c: c["id"])
    
    return JSONResponse(content={
        "ok": True,
        "commands": new_cmds,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


@router.post("/ack")
def ack_command(
    device_id: str = Query("default"),
    cmd_id: int = Query(0),
):
    """Acknowledge that a command has been processed."""
    # For now, we just log it. Commands stay in the queue (max 100 items).
    log.debug("Client %s acked command %d", device_id, cmd_id)
    return JSONResponse(content={"ok": True})


@router.post("/register")
def register_device(
    device_id: str = Query("default"),
    device_info: str = Query(""),
):
    """Register a device / keep-alive."""
    if device_id not in _device_queues:
        _device_queues[device_id] = deque(maxlen=MAX_QUEUE_SIZE)
        log.info("Client bridge: device registered — %s", device_id)
    return JSONResponse(content={
        "ok": True,
        "registered": True,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


@router.get("/status")
def bridge_status():
    """Get bridge status (for debugging)."""
    return JSONResponse(content={
        "ok": True,
        "connected_devices": len(_device_queues),
        "broadcast_queue_size": len(_broadcast_queue),
        "last_cmd_id": _last_cmd_id,
    })
