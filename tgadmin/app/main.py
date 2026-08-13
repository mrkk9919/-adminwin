"""TGAdmin - Telegram Bot Admin Panel."""

import mimetypes
import uvicorn
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import api as dashboard_api
from app.routers import users_api
from app.routers import bots_api

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Telegram Bot Admin Panel",
        version="0.1.0",
    )

    # CORS - allow frontend dev server and Cloudflare Pages
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files (for legacy template-based pages)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # API routers (for SPA frontend)
    app.include_router(dashboard_api.router)
    app.include_router(users_api.router)
    app.include_router(bots_api.router)

    # Frontend static assets at root
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/telegram.svg", response_class=FileResponse)
        def serve_favicon() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "telegram.svg")

        @app.get("/", response_class=FileResponse)
        def serve_admin_index() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/{full_path:path}", response_class=FileResponse)
        def serve_admin_frontend(full_path: str) -> FileResponse:
            requested = FRONTEND_DIST / full_path
            if requested.exists() and requested.is_file():
                media_type, _ = mimetypes.guess_type(str(requested))
                return FileResponse(requested, media_type=media_type)
            return FileResponse(FRONTEND_DIST / "index.html")

    @app.on_event("startup")
    def on_startup():
        init_db()

    return app


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    run()
