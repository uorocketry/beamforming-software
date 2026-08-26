"""CAN transport abstraction.

BeamControlClient talks to a `CanTransport`, not to python-can directly, so protocol
logic is unit-testable with a fake and integration-testable on a virtual bus
without real SocketCAN hardware.
"""

from __future__ import annotations

from typing import Protocol

import can


class CanTransport(Protocol):
    def send(self, message: can.Message) -> None: ...

    def recv(self, timeout: float | None = None) -> can.Message | None: ...

    def close(self) -> None: ...


class SocketCanTransport:
    """Real SocketCAN transport via python-can."""

    def __init__(self, channel: str = "beamcan0") -> None:
        self._bus = can.Bus(interface="socketcan", channel=channel)

    def send(self, message: can.Message) -> None:
        self._bus.send(message)

    def recv(self, timeout: float | None = None) -> can.Message | None:
        return self._bus.recv(timeout=timeout)

    def close(self) -> None:
        self._bus.shutdown()
