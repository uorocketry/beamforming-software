"""A scripted fake CanTransport for pure unit tests (no hardware, no python-can bus).

When `recv` returns None it means "no reply within the window"; the fake must
advance the injected clock by `timeout` so the client's deadline fires and the
retry/timeout path is exercised deterministically.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class FakeTransport:
    def __init__(
        self,
        replies: list[Any | None] | None = None,
        *,
        clock: Callable[[], float] | None = None,
        advance: Callable[[float], None] | None = None,
    ) -> None:
        self.sent: list[Any] = []
        self.replies = iter(replies or [])
        self._clock = clock or time.monotonic
        self._advance = advance

    def send(self, message: Any) -> None:
        self.sent.append(message)

    def recv(self, timeout: float | None = None) -> Any | None:
        reply = next(self.replies, None)
        if reply is None and self._advance is not None and timeout is not None:
            self._advance(timeout)  # simulate the empty window elapsing
        return reply

    def close(self) -> None:
        pass
