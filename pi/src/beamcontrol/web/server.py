"""FastAPI application for the read-only BeamControl status dashboard."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).with_name("static")
TEMPLATE_DIR = Path(__file__).with_name("templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


class MonitorLike(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def snapshot(self) -> dict[str, object]: ...


def create_app(monitor: MonitorLike) -> FastAPI:
    """Create the dashboard app around one CAN monitor instance."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        monitor.start()
        try:
            yield
        finally:
            monitor.stop()

    app = FastAPI(
        title="BeamControl",
        description="Read-only Raspberry Pi receiver status",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def context(request: Request) -> dict[str, object]:
        return {"request": request, **monitor.snapshot()}

    @app.get("/", include_in_schema=False, response_model=None)
    def index(request: Request) -> Response:
        return templates.TemplateResponse(request, "index.html", context(request))

    @app.get("/fragments/topbar", include_in_schema=False, response_model=None)
    def topbar(request: Request) -> Response:
        return templates.TemplateResponse(
            request,
            "fragments/topbar_status.html",
            context(request),
        )

    @app.get("/fragments/dashboard", include_in_schema=False, response_model=None)
    def dashboard(request: Request) -> Response:
        return templates.TemplateResponse(
            request,
            "fragments/dashboard.html",
            context(request),
        )

    @app.get("/api/status")
    def api_status() -> dict[str, object]:
        return monitor.snapshot()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", response_model=None)
    def readyz() -> Response:
        snapshot = monitor.snapshot()
        service = snapshot.get("service")
        health = service.get("health") if isinstance(service, dict) else "offline"
        status_code = 200 if health == "healthy" else 503
        return JSONResponse({"status": health}, status_code=status_code)

    return app
