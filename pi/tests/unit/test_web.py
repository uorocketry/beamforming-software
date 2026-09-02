"""FastAPI dashboard tests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import httpx

from beamcontrol import protocol as P
from beamcontrol.client import BeamControlError
from beamcontrol.web.server import create_app, render_changed_updates


class FakeMonitor:
    def __init__(self, health: str = "healthy") -> None:
        self.health = health
        self.started = False
        self.stopped = False
        self.commands: list[tuple[int, str, int | None, int | None]] = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def command(
        self,
        node: int,
        action: str,
        *,
        phase_state: int | None = None,
        attenuation_db: int | None = None,
    ) -> bytes:
        self.commands.append((node, action, phase_state, attenuation_db))
        return b"\x01\x00"

    def snapshot(self) -> dict[str, object]:
        return {
            "system": {
                "model": "Raspberry Pi 5 Model B Rev 1.0",
                "architecture": "aarch64",
                "python": "3.11.15",
                "operating_system": "Raspberry Pi OS",
                "beamcontrol_version": "0.1.0",
            },
            "service": {
                "health": self.health,
                "uptime": "12s",
                "started_at": "2026-08-02 03:00:00 EDT",
            },
            "can": {
                "health": "online",
                "status": "online",
                "status_class": "online",
                "channel": "can0",
                "bitrate": "500 kbit/s",
                "sample_point": "87.5%",
                "error": None,
            },
            "configuration": {
                "source_node": 0,
                "poll_interval_s": 1.0,
                "scan_mode": False,
                "target_nodes": [1],
                "web_host": "0.0.0.0",
                "web_port": 8080,
            },
            "node_summary": {
                "online": 1,
                "healthy": 1,
                "displayed": 1,
                "monitored": 1,
            },
            "last_cycle": "03:00:12",
            "cycle_ms": 4.2,
            "nodes": [
                {
                    "node_id": 1,
                    "health": "healthy",
                    "protocol_version": "3.0.0",
                    "response_ms": 3.1,
                    "last_seen": "03:00:12",
                    "error": None,
                }
            ],
            "events": [
                {
                    "time": "03:00:12",
                    "level": "success",
                    "message": "Receiver node 1 is healthy",
                }
            ],
        }


def run(coroutine: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coroutine)


def test_dashboard_routes_and_lifespan() -> None:
    async def scenario() -> None:
        monitor = FakeMonitor()
        app = create_app(monitor)
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            response = await client.get("/")
            assert response.status_code == 200
            assert "BeamControl" in response.text
            assert "Raspberry Pi receiver control" not in response.text
            assert "Receiver network" not in response.text
            assert "Live system detail" not in response.text
            assert "Live telemetry" not in response.text
            assert "Receiver boards" in response.text
            assert "SN01" in response.text
            assert 'name="phase_state" type="range" min="0" max="255"' in response.text
            assert "Phase at 2.4 GHz" in response.text
            assert 'name="attenuation_db" type="range" min="0" max="23"' in response.text
            assert "One receiver board · one RF chain" in response.text
            assert "updates every 2 seconds" not in response.text
            assert "Live updates" not in response.text
            assert "data-refresh-url" not in response.text
            assert "/events" in {route.path for route in app.routes}

            command = await client.post(
                "/api/nodes/1/commands",
                json={"action": "combined", "phase_state": 128, "attenuation_db": 8},
            )
            assert command.status_code == 200
            assert command.json() == {"status": "acknowledged", "ack": "0100"}
            assert monitor.commands == [(1, "combined", 128, 8)]

            invalid = await client.post(
                "/api/nodes/1/commands",
                json={"action": "combined", "phase_state": 256, "attenuation_db": 8},
            )
            assert invalid.status_code == 422

            stylesheet = await client.get("/static/styles.css")
            assert stylesheet.status_code == 200
            assert "--green" in stylesheet.text
            script = await client.get("/static/dashboard.js")
            assert script.status_code == 200
            assert 'EventSource("/events")' in script.text
            assert "setInterval" not in script.text
            assert "phase_lookup_2_4ghz.csv" in script.text
            assert "phaseDescription" in script.text
            assert "updateSliderValue" in script.text

            phase_lookup = await client.get("/static/phase_lookup_2_4ghz.csv")
            assert phase_lookup.status_code == 200
            assert "146,10010010,205.3125,209.73,141,010001101,205" in phase_lookup.text

            status = await client.get("/api/status")
            assert status.status_code == 200
            assert status.json()["node_summary"]["online"] == 1

            assert (await client.get("/healthz")).status_code == 200
            assert (await client.get("/readyz")).status_code == 200

        assert monitor.started
        assert monitor.stopped

    run(scenario())


def test_command_errors_are_actionable() -> None:
    class ErrorMonitor(FakeMonitor):
        error: Exception = BeamControlError("node 1 error", result=P.RES_BUSY)

        def command(self, *args: object, **kwargs: object) -> bytes:
            raise self.error

    async def scenario() -> None:
        monitor = ErrorMonitor()
        app = create_app(monitor)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            rejected = await client.post("/api/nodes/1/commands", json={"action": "safe"})
            assert rejected.status_code == 409
            assert rejected.json()["code"] == "node_rejected"
            assert "safe-state lockout" in rejected.json()["error"]

            monitor.error = BeamControlError("timeout node 1; final state unknown")
            timeout = await client.post("/api/nodes/1/commands", json={"action": "safe"})
            assert timeout.status_code == 504
            assert timeout.json()["code"] == "timeout"
            assert timeout.json()["error"] == "No acknowledgement from SN01."

    run(scenario())


def test_sse_rendering_only_returns_changed_atoms() -> None:
    monitor = FakeMonitor()
    first, rendered = render_changed_updates(monitor.snapshot(), {})
    first_ids = {str(update["id"]) for update in first}
    assert "controller-uptime" in first_ids
    assert "controller-health" in first_ids
    assert "can-last-scan" in first_ids
    assert "receiver-online" in first_ids
    assert "node-1-health" in first_ids
    assert "receiver-board-list" in first_ids
    assert "recent-events-list" in first_ids
    assert "controller-summary" not in first_ids
    assert "can-summary" not in first_ids

    unchanged, rendered = render_changed_updates(monitor.snapshot(), rendered)
    assert unchanged == []

    monitor.health = "degraded"
    changed, _ = render_changed_updates(monitor.snapshot(), rendered)
    assert {str(update["id"]) for update in changed} == {
        "top-boards-state",
        "controller-health",
        "receiver-healthy",
    }


def test_readiness_fails_when_monitor_is_offline() -> None:
    async def scenario() -> None:
        app = create_app(FakeMonitor("offline"))
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            response = await client.get("/readyz")
            assert response.status_code == 503
            assert response.json() == {"status": "offline"}

    run(scenario())
