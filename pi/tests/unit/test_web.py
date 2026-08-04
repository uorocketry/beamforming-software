"""Read-only FastAPI dashboard tests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import httpx

from beamcontrol.web.server import create_app


class FakeMonitor:
    def __init__(self, health: str = "healthy") -> None:
        self.health = health
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

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
                    "protocol_version": "2.1.0",
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
            assert "Receiver boards" in response.text
            assert 'data-refresh-url="/fragments/dashboard"' in response.text

            fragment = await client.get("/fragments/dashboard")
            assert fragment.status_code == 200
            assert "NODE" in fragment.text

            stylesheet = await client.get("/static/styles.css")
            assert stylesheet.status_code == 200
            assert "--green" in stylesheet.text
            script = await client.get("/static/dashboard.js")
            assert script.status_code == 200
            assert "data-refresh-url" in script.text

            status = await client.get("/api/status")
            assert status.status_code == 200
            assert status.json()["node_summary"]["online"] == 1

            assert (await client.get("/healthz")).status_code == 200
            assert (await client.get("/readyz")).status_code == 200

        assert monitor.started
        assert monitor.stopped

    run(scenario())


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
