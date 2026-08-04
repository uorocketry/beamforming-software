"""BeamControl monitor state tests."""

from __future__ import annotations

from collections.abc import Callable

from beamcontrol.client import BeamControlError, NodeStatus
from beamcontrol.config import BeamControlConfig
from beamcontrol.monitor import BeamControlMonitor, configured_node_failure


class FakeClient:
    def discover(self, destination: int) -> NodeStatus:
        if destination == 1:
            return NodeStatus(2, 1, 0, 1, 0, 0, 0, 0)
        raise BeamControlError(f"no STATUS from node {destination}")


def fake_factory(_: BeamControlConfig) -> tuple[FakeClient, Callable[[], None]]:
    return FakeClient(), lambda: None


def test_monitor_reports_healthy_and_offline_configured_nodes() -> None:
    monitor = BeamControlMonitor(
        BeamControlConfig(nodes=[1, 2]),
        client_factory=fake_factory,
    )

    monitor.poll_once()
    snapshot = monitor.snapshot()

    assert snapshot["can"] == {
        "health": "online",
        "channel": "can0",
        "bitrate": "500 kbit/s",
        "sample_point": "87.5%",
        "error": None,
    }
    nodes = snapshot["nodes"]
    assert isinstance(nodes, list)
    assert nodes[0]["node_id"] == 1
    assert nodes[0]["health"] == "healthy"
    assert nodes[1]["node_id"] == 2
    assert nodes[1]["health"] == "offline"
    service = snapshot["service"]
    assert isinstance(service, dict)
    assert service["health"] == "degraded"


def test_monitor_keeps_dashboard_available_when_can_cannot_open() -> None:
    def unavailable(_: BeamControlConfig):
        raise OSError("can0 does not exist")

    monitor = BeamControlMonitor(BeamControlConfig(), client_factory=unavailable)
    monitor.poll_once()

    snapshot = monitor.snapshot()
    can_status = snapshot["can"]
    assert isinstance(can_status, dict)
    assert can_status["health"] == "offline"
    assert can_status["error"] == "can0 does not exist"


def test_wrong_major_rejected() -> None:
    assert configured_node_failure(3, NodeStatus(1, 9, 0, 3, 0, 0, 0, 0)) is not None


def test_newer_major_rejected() -> None:
    assert configured_node_failure(3, NodeStatus(3, 0, 0, 3, 0, 0, 0, 0)) is not None


def test_wrong_minor_rejected() -> None:
    assert configured_node_failure(3, NodeStatus(2, 0, 0, 3, 0, 0, 0, 0)) is not None


def test_exact_version_accepted() -> None:
    assert configured_node_failure(3, NodeStatus(2, 1, 0, 3, 0, 0, 0, 0)) is None
