"""Wing Bank Telegram Bot — Admin Panel entry point.

Run with:
    cd admin && uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app import auth
from app.config import get_settings
from app.routers import (
    dashboard, messages, customers, orders, bots, sms,
    accounts, transactions, kyc, reports, settings, bridge, push, groups,
    client_api, client_bridge,
)

_BASE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE / "templates"))
_TEMPLATES.env.cache_size = 0

log = logging.getLogger(__name__)

# Paths that bypass IP check (health probes, static assets).
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For for reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip check for public paths and static assets.
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        settings = get_settings()
        allowed_raw = settings.allowed_ips.strip()

        # Empty config = allow all (open mode).
        if not allowed_raw:
            return await call_next(request)

        allowed = {ip.strip() for ip in allowed_raw.split(",") if ip.strip()}
        client_ip = _get_client_ip(request)

        if client_ip not in allowed:
            log.warning(
                "IP blocked: %s tried to access %s", client_ip, path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "detail": f"IP {client_ip} is not allowed",
                },
            )

        return await call_next(request)


def _build_app() -> FastAPI:
    application = FastAPI(
        title="Wing Bank Admin",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        debug=True,
    )

    # Security check: warn if default credentials are used
    app_settings = get_settings()
    if app_settings.admin_password == "admin123":
        log.warning("⚠️  SECURITY WARNING: Using default admin password 'admin123'! "
                    "Change ADMIN_PASSWORD in .env immediately!")
    if app_settings.jwt_secret == "please-change-me-to-something-random":
        log.warning("⚠️  SECURITY WARNING: Using default JWT secret! "
                    "Change JWT_SECRET in .env to a long random string immediately!")

    # CORS — allow frontend origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                       "http://192.168.1.243:3000", "http://192.168.1.243:8080",
                       "https://wingdigi.store", "http://wingdigi.store"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # IP whitelist middleware — runs before any route handler.
    application.add_middleware(IPWhitelistMiddleware)

    # Static assets (CSS + client-side JS).
    application.mount(
        "/static",
        StaticFiles(directory=str(_BASE / "static")),
        name="static",
    )

    # Routers: auth (login/logout) is public; everything else enforces JWT.
    application.include_router(auth.router)
    application.include_router(dashboard.router)
    application.include_router(messages.router)
    application.include_router(customers.router)
    # Payment-callback API must be registered before orders.router so
    # /orders/api/payment-confirm is not captured by /orders/{order_hash}.
    application.include_router(orders.api_router)
    application.include_router(orders.router)
    application.include_router(bots.router)
    application.include_router(sms.router)
    application.include_router(accounts.router)
    application.include_router(transactions.router)
    application.include_router(kyc.router)
    application.include_router(reports.router)
    application.include_router(settings.router)
    application.include_router(bridge.router)
    application.include_router(push.router)
    application.include_router(groups.router)

    # Client-facing API (register/login/accounts/transfer/transactions)
    application.include_router(client_api.router)
    application.include_router(client_bridge.router)

    # Bridge command polling API (auth required)
    @application.get("/bridge/api/commands", include_in_schema=False)
    def bridge_poll_commands(
        since_id: int = 0,
        _username: str = Depends(auth.require_admin),
    ):
        from app.routers.bridge import _command_queue
        new_cmds = [c for c in _command_queue if c["id"] > since_id]
        return {"ok": True, "commands": new_cmds}

    @application.get("/", include_in_schema=False)
    def root(request: Request) -> RedirectResponse:
        token = request.cookies.get(
            auth.COOKIE_NAME) or request.headers.get("Authorization", "")
        if token:
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = _build_app()
