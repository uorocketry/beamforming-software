"""FastAPI application for the BeamControl status and command dashboard."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, model_validator

from ..client import BeamControlError

STATIC_DIR = Path(__file__).with_name("static")
TEMPLATE_DIR = Path(__file__).with_name("templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

Update = dict[str, object]
UpdateSpec = tuple[object, Update]


class MonitorLike(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def snapshot(self) -> dict[str, object]: ...

    def revision(self) -> int: ...

    def wait_for_update(self, revision: int, timeout: float) -> int: ...

    def command(
        self,
        node: int,
        action: str,
        *,
        phase_state: int | None = None,
        attenuation_db: int | None = None,
    ) -> bytes: ...


class NodeCommand(BaseModel):
    action: str
    phase_state: int | None = Field(default=None, ge=0, le=255)
    attenuation_db: int | None = Field(default=None, ge=0, le=23)

    @model_validator(mode="after")
    def validate_action_fields(self) -> NodeCommand:
        required = {
            "safe": (False, False),
            "phase": (True, False),
            "vga": (False, True),
            "combined": (True, True),
        }
        if self.action not in required:
            raise ValueError("action must be safe, phase, vga, or combined")
        phase_required, attenuation_required = required[self.action]
        if phase_required and self.phase_state is None:
            raise ValueError("phase_state is required")
        if attenuation_required and self.attenuation_db is None:
            raise ValueError("attenuation_db is required")
        return self


def _text(value: object, class_name: str | None = None) -> UpdateSpec:
    payload: Update = {"text": str(value)}
    if class_name is not None:
        payload["className"] = class_name
    return tuple(payload.items()), payload


def _class(class_name: str) -> UpdateSpec:
    payload: Update = {"className": class_name}
    return tuple(payload.items()), payload


def _note(text: object | None) -> UpdateSpec:
    payload: Update = {
        "text": "" if text is None else str(text),
        "hidden": text is None,
    }
    return tuple(payload.items()), payload


def _html(compare_key: object, html: str) -> UpdateSpec:
    return compare_key, {"html": html.strip()}


def _render(template_name: str, snapshot: dict[str, object]) -> str:
    return templates.env.get_template(template_name).render(**snapshot)


def _last_scan(snapshot: dict[str, object]) -> str:
    last_cycle = str(snapshot["last_cycle"])
    cycle_ms = snapshot["cycle_ms"]
    return last_cycle if cycle_ms is None else f"{last_cycle} · {cycle_ms} ms"


def _event_key(events: list[dict[str, Any]]) -> tuple[tuple[object, ...], ...]:
    return tuple((event.get("time"), event.get("level"), event.get("message")) for event in events)


def _receiver_structure_key(nodes: list[dict[str, Any]], can_status: str) -> tuple[object, ...]:
    if nodes:
        return ("nodes", *(node.get("node_id") for node in nodes))
    return ("empty", can_status)


def build_update_specs(snapshot: dict[str, object]) -> dict[str, UpdateSpec]:
    """Build independently comparable UI atoms from one monitor snapshot."""
    service = cast(dict[str, Any], snapshot["service"])
    can_state = cast(dict[str, Any], snapshot["can"])
    node_summary = cast(dict[str, Any], snapshot["node_summary"])
    nodes = cast(list[dict[str, Any]], snapshot["nodes"])
    events = cast(list[dict[str, Any]], snapshot["events"])

    service_health = str(service["health"])
    can_status = str(can_state.get("status", can_state["health"]))
    can_status_class = str(can_state.get("status_class", can_state["health"]))

    specs: dict[str, UpdateSpec] = {
        "top-can-state": _class(f"service-status {can_status_class}"),
        "top-can-status": _text(can_status),
        "top-boards-state": _class(f"service-status {service_health}"),
        "top-boards-status": _text(f"{node_summary['online']}/{node_summary['monitored']}"),
        "controller-health": _text(
            service_health,
            f"health-badge {service_health}",
        ),
        "controller-uptime": _text(service["uptime"]),
        "can-health": _text(
            can_status,
            f"health-badge {can_status_class}",
        ),
        "can-last-scan": _text(_last_scan(snapshot)),
        "can-note": _note(can_state.get("error")),
        "receiver-online": _text(f"{node_summary['online']} online"),
        "receiver-healthy": _text(
            f"{node_summary['healthy']} healthy",
            f"health-badge {service_health}",
        ),
        "receiver-monitored": _text(node_summary["monitored"]),
        "receiver-known": _text(node_summary["displayed"]),
        "receiver-board-list": _html(
            _receiver_structure_key(nodes, can_status),
            _render("fragments/receiver_board_list.html", snapshot),
        ),
        "recent-events-list": _html(
            _event_key(events),
            _render("fragments/recent_event_list.html", snapshot),
        ),
    }

    for node in nodes:
        node_id = node["node_id"]
        health = str(node["health"])
        response_ms = node.get("response_ms")
        specs.update(
            {
                f"node-{node_id}-card": _class(f"node-card {health}"),
                f"node-{node_id}-health": _text(
                    health,
                    f"health-badge {health}",
                ),
                f"node-{node_id}-protocol": _text(node["protocol_version"]),
                f"node-{node_id}-response": _text(
                    "—" if response_ms is None else f"{response_ms} ms"
                ),
                f"node-{node_id}-last-seen": _text(node["last_seen"]),
                f"node-{node_id}-error": _note(node.get("error")),
            }
        )

    return specs


def render_changed_updates(
    snapshot: dict[str, object], previous: dict[str, object]
) -> tuple[list[Update], dict[str, object]]:
    """Return only atoms whose value or state changed since the prior snapshot."""
    current: dict[str, object] = {}
    changed: list[Update] = []
    for element_id, (compare_key, payload) in build_update_specs(snapshot).items():
        current[element_id] = compare_key
        if previous.get(element_id) != compare_key:
            changed.append({"id": element_id, **payload})
    return changed, current


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
        description="Raspberry Pi receiver status and node-scoped controls",
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

    @app.get("/events", include_in_schema=False, response_model=None)
    async def event_stream() -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            previous: dict[str, object] = {}
            revision = monitor.revision()
            while True:
                changed, previous = render_changed_updates(monitor.snapshot(), previous)
                for update in changed:
                    payload = json.dumps(update, separators=(",", ":"))
                    yield f"event: update\ndata: {payload}\n\n"

                next_revision = await asyncio.to_thread(
                    monitor.wait_for_update,
                    revision,
                    15.0,
                )
                if next_revision == revision:
                    yield ": keep-alive\n\n"
                revision = next_revision

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/status")
    def api_status() -> dict[str, object]:
        return monitor.snapshot()

    @app.post("/api/nodes/{node_id}/commands", response_model=None)
    async def node_command(node_id: int, command: NodeCommand) -> Response:
        if not 1 <= node_id <= 30:
            return JSONResponse({"error": "node must be 1..30"}, status_code=422)
        try:
            ack = await asyncio.to_thread(
                monitor.command,
                node_id,
                command.action,
                phase_state=command.phase_state,
                attenuation_db=command.attenuation_db,
            )
        except (BeamControlError, OSError, ValueError) as error:
            return JSONResponse({"error": str(error)}, status_code=502)
        return JSONResponse({"status": "acknowledged", "ack": ack.hex()})

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
