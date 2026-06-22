"""FastAPI application: lifespan boot, REST routes, WebSocket stream, static UI."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config.loader import load_dotenv

# Load .env (CLICKUP_API_TOKEN, etc.) before the routers/clients are imported.
load_dotenv(os.environ.get("SAMS_WORKSPACE", "."))

from ..platform import build_platform  # noqa: E402
from .rest import router as rest_router  # noqa: E402
from .ws import websocket_endpoint  # noqa: E402

log = logging.getLogger("sams.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    workspace = os.environ.get("SAMS_WORKSPACE", ".")
    mode = os.environ.get("SAMS_MODE")
    env = os.environ.get("SAMS_ENV", "dev")
    platform = build_platform(workspace, environment=env, mode=mode)
    await platform.boot()
    app.state.platform = platform
    log.info("SAMS API ready — %d agents online", len(platform.runtime.instances()))
    try:
        yield
    finally:
        await platform.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="SAMS — Spatial Agentic Management System", version="0.9.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rest_router, prefix="/api/v1")
    app.add_api_websocket_route("/api/v1/stream", websocket_endpoint)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # Serve the built spatial UI if present (web/dist), else a hint page.
    dist = Path(os.environ.get("SAMS_WORKSPACE", ".")) / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    else:
        @app.get("/")
        async def index() -> JSONResponse:
            return JSONResponse({
                "name": "SAMS",
                "ui": "run the spatial UI with `cd web && npm install && npm run dev`",
                "api": "/api/v1",
                "stream": "/api/v1/stream?space=main.space",
            })

    return app


app = create_app()
