"""JWT-based authentication for the admin panel.

The MVP ships a single admin account whose credentials live in .env. The
login handler issues a JWT (HTTP-only cookie + Authorization header both
accepted). All other routes use `require_admin` to enforce the cookie.

No role granularity in the MVP — every authenticated user has full access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import jwt as pyjwt

from app.config import get_settings

router = APIRouter()
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent / "templates"))
_templates.env.cache_size = 0

COOKIE_NAME = "wing_admin_token"


def _verify_password(plain: str) -> bool:
    """Compare against the ADMIN_PASSWORD from .env.

    We accept both plain-text and bcrypt-hashed passwords in .env so operators
    can either keep things simple in dev (plain) or harden production (hash
    the password with `passlib.hash.bcrypt.hash(plain)` and paste the result).
    """
    settings = get_settings()
    if settings.admin_password.startswith("$2b$"):
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.verify(plain, settings.admin_password)
    return plain == settings.admin_password


def create_token(username: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + \
        timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": username, "exp": expire}
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    """Return the username encoded in the JWT, or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(token, settings.jwt_secret,
                               algorithms=[settings.jwt_algorithm])
        username: str | None = payload.get("sub")
        return username
    except pyjwt.PyJWTError:
        return None


def _extract_token(request: Request) -> str | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


def require_admin(request: Request) -> str:
    """FastAPI dependency. Returns the authenticated username or 401."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    username = decode_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return username


def require_admin_or_push_api_key(request: Request) -> str:
    """Allow either an admin session / JWT or a configured push API key."""
    api_key = request.headers.get("X-API-Key")
    if api_key is not None:
        settings = get_settings()
        if settings.push_api_token and api_key == settings.push_api_token:
            return "push-api-key"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return require_admin(request)


# --- Login routes ----------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return _templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username != get_settings().admin_username or not _verify_password(password):
        return _templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = create_token(username)
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=get_settings().jwt_expire_hours * 3600,
    )
    return redirect


@router.get("/logout")
def logout() -> Response:
    resp = RedirectResponse(
        url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(COOKIE_NAME)
    return resp
