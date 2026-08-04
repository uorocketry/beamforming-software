"""Threaded CAN health monitor backing the BeamControl web dashboard."""

from __future__ import annotations

import logging
import platform
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

import can

from . import protocol as P
from .client import BeamControlClient, BeamControlError, BeamControlProtocolError, NodeStatus
from .config import BeamControlConfig
from .transport import SocketCanTransport

log = logging.getLogger(__name__)


class ClientLike(Protocol):
    def discover(self, destination: int) -> NodeStatus: ...


ClientFactory = Callable[[BeamControlConfig], tuple[ClientLike, Callable[[], None]]]
Clock = Callable[[], float]
WallClock = Callable[[], datetime]


@dataclass
class NodeRecord:
    node_id: int
    health: str = "offline"
    protocol_version: str | None = None
    response_ms: float | None = None
    last_seen: datetime | None = None
    error: str | None = None


@dataclass(frozen=True)
class EventRecord:
    timestamp: datetime
    level: str
    message: str


def configured_node_failure(node: int, status: NodeStatus) -> str | None:
    """Return why a receiver node fails the production protocol gate."""
    if status.version != P.PROTOCOL_VERSION:
        return (
            f"receiver node {node} has incompatible protocol version "
            f"{status.major}.{status.minor}.{status.patch}"
        )
    return None


def _default_client_factory(
    config: BeamControlConfig,
) -> tuple[ClientLike, Callable[[], None]]:
    transport = SocketCanTransport(config.channel)
    client = BeamControlClient(
        transport,
        source_node=config.source_node,
        timeout=config.can_timeout_s,
        retries=config.can_retries,
    )
    return client, transport.close


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes:d}m {seconds:02d}s"
    return f"{seconds:d}s"


def _system_info() -> dict[str, str]:
    model_path = Path("/proc/device-tree/model")
    try:
        model = model_path.read_bytes().rstrip(b"\x00").decode("utf-8")
    except (OSError, UnicodeDecodeError):
        model = platform.node() or "Development host"
    try:
        release = platform.freedesktop_os_release()
        operating_system = release.get("PRETTY_NAME", platform.system())
    except OSError:
        operating_system = platform.system()
    try:
        package_version = version("beamcontrol")
    except PackageNotFoundError:
        package_version = "development"
    return {
        "model": model,
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "operating_system": operating_system,
        "beamcontrol_version": package_version,
    }


class BeamControlMonitor:
    """Poll receiver boards and expose a thread-safe dashboard snapshot."""

    def __init__(
        self,
        config: BeamControlConfig,
        *,
        client_factory: ClientFactory = _default_client_factory,
        clock: Clock = time.monotonic,
        wall_clock: WallClock = _utc_now,
    ) -> None:
        self.config = config
        self._client_factory = client_factory
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._client: ClientLike | None = None
        self._close_client: Callable[[], None] | None = None
        self._started_monotonic = clock()
        self._started_at = wall_clock()
        self._system = _system_info()
        self._can_health = "starting"
        self._can_error: str | None = None
        self._last_cycle: datetime | None = None
        self._cycle_ms: float | None = None
        self._nodes: dict[int, NodeRecord] = {node: NodeRecord(node) for node in config.nodes}
        self._events: deque[EventRecord] = deque(maxlen=100)
        self._record_event("info", "BeamControl monitor starting")

    def start(self) -> None:
        """Start polling in a background thread. Safe to call more than once."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="beamcontrol-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and close the SocketCAN transport."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.config.poll_interval_s + 1.0))
        self._disconnect()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                cycle_started = self._clock()
                self.poll_once()
                elapsed = self._clock() - cycle_started
                self._stop_event.wait(max(0.0, self.config.poll_interval_s - elapsed))
        finally:
            self._disconnect()
            self._record_event("info", "BeamControl monitor stopped")

    def _connect(self) -> bool:
        if self._client is not None:
            return True
        try:
            self._client, self._close_client = self._client_factory(self.config)
        except Exception as error:  # Keep the web UI alive while CAN is unavailable.
            message = str(error) or error.__class__.__name__
            with self._lock:
                changed = self._can_health != "offline" or self._can_error != message
                self._can_health = "offline"
                self._can_error = message
            if changed:
                self._record_event("error", f"CAN unavailable: {message}")
            return False
        with self._lock:
            changed = self._can_health != "online"
            self._can_health = "online"
            self._can_error = None
        if changed:
            self._record_event("success", f"SocketCAN connected on {self.config.channel}")
        return True

    def _disconnect(self) -> None:
        close = self._close_client
        self._client = None
        self._close_client = None
        if close is not None:
            try:
                close()
            except Exception:  # Shutdown should not mask the original failure.
                log.exception("failed to close CAN transport")

    def poll_once(self) -> None:
        """Run one receiver scan. Exposed for deterministic unit tests."""
        cycle_started = self._clock()
        if not self._connect():
            self._finish_cycle(cycle_started)
            return

        assert self._client is not None
        targets = self.config.nodes or list(range(1, P.BROADCAST_NODE))
        for node in targets:
            if self._stop_event.is_set():
                break
            request_started = self._clock()
            try:
                status = self._client.discover(node)
            except BeamControlProtocolError as error:
                self._mark_node_failure(node, f"protocol error: {error}")
            except BeamControlError as error:
                self._mark_node_failure(node, str(error))
            except (can.CanError, OSError) as error:
                message = str(error) or error.__class__.__name__
                with self._lock:
                    self._can_health = "offline"
                    self._can_error = message
                self._record_event("error", f"CAN connection failed: {message}")
                self._disconnect()
                break
            except Exception as error:  # A bad driver must not take down the status page.
                message = str(error) or error.__class__.__name__
                self._mark_node_failure(node, f"unexpected error: {message}")
                log.exception("unexpected receiver polling failure")
            else:
                response_ms = (self._clock() - request_started) * 1000.0
                self._mark_node_success(node, status, response_ms)

        self._finish_cycle(cycle_started)

    def _mark_node_success(self, node: int, status: NodeStatus, response_ms: float) -> None:
        failure = configured_node_failure(node, status)
        health = "healthy" if failure is None else "degraded"
        protocol_version = f"{status.major}.{status.minor}.{status.patch}"
        now = self._wall_clock()
        with self._lock:
            record = self._nodes.setdefault(node, NodeRecord(node))
            previous_health = record.health
            record.health = health
            record.protocol_version = protocol_version
            record.response_ms = response_ms
            record.last_seen = now
            record.error = failure
        if previous_health != health:
            message = f"Receiver node {node} is {health}"
            if failure is not None:
                message = f"{message}: {failure}"
            self._record_event("success" if health == "healthy" else "warning", message)

    def _mark_node_failure(self, node: int, message: str) -> None:
        configured = bool(self.config.nodes)
        with self._lock:
            existing = self._nodes.get(node)
            if existing is None and not configured:
                return
            record = self._nodes.setdefault(node, NodeRecord(node))
            changed = record.health != "offline" or record.error != message
            record.health = "offline"
            record.response_ms = None
            record.error = message
        if changed:
            self._record_event("warning", f"Receiver node {node} is offline: {message}")

    def _finish_cycle(self, cycle_started: float) -> None:
        with self._lock:
            self._last_cycle = self._wall_clock()
            self._cycle_ms = (self._clock() - cycle_started) * 1000.0

    def _record_event(self, level: str, message: str) -> None:
        with self._lock:
            self._events.appendleft(EventRecord(self._wall_clock(), level, message))

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-serializable snapshot for templates and API clients."""
        now_monotonic = self._clock()
        with self._lock:
            nodes = [
                {
                    "node_id": record.node_id,
                    "health": record.health,
                    "protocol_version": record.protocol_version or "—",
                    "response_ms": (
                        None if record.response_ms is None else round(record.response_ms, 1)
                    ),
                    "last_seen": (
                        "—"
                        if record.last_seen is None
                        else record.last_seen.astimezone().strftime("%H:%M:%S")
                    ),
                    "error": record.error,
                }
                for record in sorted(self._nodes.values(), key=lambda item: item.node_id)
            ]
            events = [
                {
                    "time": event.timestamp.astimezone().strftime("%H:%M:%S"),
                    "level": event.level,
                    "message": event.message,
                }
                for event in self._events
            ]
            can_health = self._can_health
            can_error = self._can_error
            last_cycle = self._last_cycle
            cycle_ms = self._cycle_ms

        online_nodes = sum(node["health"] in {"healthy", "degraded"} for node in nodes)
        healthy_nodes = sum(node["health"] == "healthy" for node in nodes)
        configured_count = len(self.config.nodes)
        if can_health != "online":
            overall_health = "offline" if can_health == "offline" else "starting"
        elif configured_count:
            overall_health = (
                "healthy"
                if len(nodes) == configured_count and healthy_nodes == configured_count
                else "degraded"
            )
        elif healthy_nodes:
            overall_health = "healthy"
        else:
            overall_health = "degraded"

        return {
            "system": self._system,
            "service": {
                "health": overall_health,
                "uptime": _format_duration(now_monotonic - self._started_monotonic),
                "started_at": self._started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            },
            "can": {
                "health": can_health,
                "channel": self.config.channel,
                "bitrate": "500 kbit/s",
                "sample_point": "87.5%",
                "error": can_error,
            },
            "configuration": {
                "source_node": self.config.source_node,
                "poll_interval_s": self.config.poll_interval_s,
                "can_timeout_s": self.config.can_timeout_s,
                "can_retries": self.config.can_retries,
                "scan_mode": not bool(self.config.nodes),
                "target_nodes": self.config.nodes,
                "web_host": self.config.web_host,
                "web_port": self.config.web_port,
            },
            "node_summary": {
                "online": online_nodes,
                "healthy": healthy_nodes,
                "displayed": len(nodes),
                "monitored": configured_count or 30,
            },
            "last_cycle": (
                "—" if last_cycle is None else last_cycle.astimezone().strftime("%H:%M:%S")
            ),
            "cycle_ms": None if cycle_ms is None else round(cycle_ms, 1),
            "nodes": nodes,
            "events": events,
        }
