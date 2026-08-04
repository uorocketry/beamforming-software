"""End-to-end client <-> fake node over python-can's virtual bus.

This exercises real message serialization and the client state machine without
any SocketCAN hardware or kernel modules. Requires python-can.
"""

from __future__ import annotations

import threading

import can
import pytest

from beamcontrol import protocol as P
from beamcontrol.client import BeamControlClient

from .fake_beamcontrol_node import FakeBeamControlNode


class VirtualTransport:
    def __init__(self, bus: can.BusABC) -> None:
        self._bus = bus

    def send(self, message: can.Message) -> None:
        self._bus.send(message)

    def recv(self, timeout: float | None = None) -> can.Message | None:
        return self._bus.recv(timeout=timeout)

    def close(self) -> None:
        self._bus.shutdown()


class NodeDriver:
    """Runs a FakeBeamControlNode's service loop on a background thread."""

    def __init__(self, node: FakeBeamControlNode) -> None:
        self._node = node
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._node.service(count=10)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


@pytest.fixture
def buses():
    channel = "beamcontrol-test"
    ctrl = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    node = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)
    yield ctrl, node
    ctrl.shutdown()
    node.shutdown()


def test_set_phase_round_trip(buses):
    ctrl, node = buses
    fake = FakeBeamControlNode(node, 3)
    driver = NodeDriver(fake)
    driver.start()
    try:
        client = BeamControlClient(VirtualTransport(ctrl), timeout=0.5, retries=1)
        phases = [128, 64, 32, 16]
        out = client.set_phase(3, phases)
        assert out == bytes([P.SET_PHASE, P.RES_OK])
        f = P.parse_id(fake.seen[0].arbitration_id)
        assert f["type"] == P.SET_PHASE
        assert f["dest"] == 3 and f["source"] == 0
        assert bytes(fake.seen[0].data) == bytes(phases)
    finally:
        driver.stop()


def test_individual_round_trips(buses):
    ctrl, node = buses
    fake = FakeBeamControlNode(node, 3)
    driver = NodeDriver(fake)
    driver.start()
    try:
        client = BeamControlClient(VirtualTransport(ctrl), timeout=0.5, retries=0)
        assert client.set_phase_channel(3, 2, 128) == bytes([P.SET_PHASE, P.RES_OK])
        assert client.set_vga_channel(3, 1, 8) == bytes([P.SET_VGA, P.RES_OK])
        assert client.set_combined_channel(3, 3, 64, 12) == bytes([P.SET_COMBINED, P.RES_OK])
        assert [bytes(message.data) for message in fake.seen[:3]] == [
            bytes([128, 2]),
            bytes([8, 1]),
            bytes([64, 3, 12]),
        ]
    finally:
        driver.stop()


def test_invalid_bulk_payload_rejected_client_side(buses):
    """Invalid bulk lengths are rejected before any CAN traffic."""
    ctrl, node = buses
    driver = NodeDriver(FakeBeamControlNode(node, 3))
    driver.start()
    try:
        client = BeamControlClient(VirtualTransport(ctrl), timeout=0.5, retries=0)
        with pytest.raises(ValueError):
            client.set_phase(3, [128, 64, 32])
    finally:
        driver.stop()


def test_discover_returns_status(buses):
    ctrl, node = buses
    driver = NodeDriver(FakeBeamControlNode(node, 3))
    driver.start()
    try:
        client = BeamControlClient(VirtualTransport(ctrl), timeout=0.5, retries=0)
        status = client.discover(3)
        assert status.version == P.PROTOCOL_VERSION
        assert status.node_id == 3
    finally:
        driver.stop()
