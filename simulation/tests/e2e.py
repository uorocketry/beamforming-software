"""Containerized BeamControl end-to-end simulation assertions."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypeVar

from beamcontrol import protocol as P
from beamcontrol.client import BeamControlClient
from beamcontrol.transport import SocketCanTransport

T = TypeVar("T")
BASE_URL = "http://127.0.0.1:8080"
RENODE_LOG = Path("/results/renode.log")


def wait_http(path: str, expected_status: int, timeout_s: float = 60.0) -> bytes:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=2.0) as response:
                if response.status == expected_status:
                    return response.read()
                last_error = RuntimeError(f"{path} returned HTTP {response.status}")
        except urllib.error.HTTPError as error:
            if error.code == expected_status:
                return error.read()
            last_error = error
        except (OSError, TimeoutError) as error:
            last_error = error
        time.sleep(0.25)
    raise AssertionError(f"{path} did not reach HTTP {expected_status}: {last_error}")


def wait_for_log(pattern: str, timeout_s: float = 30.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        text = (
            RENODE_LOG.read_text(encoding="utf-8", errors="replace")
            if RENODE_LOG.exists()
            else ""
        )
        if pattern in text:
            return text
        time.sleep(0.1)
    raise AssertionError(f"Renode log never contained {pattern!r}")


def values(text: str, device: str, offset: int) -> list[int]:
    pattern = re.compile(
        rf"SIM_{re.escape(device)} offset=0x{offset:X} value=0x([0-9A-Fa-f]+)"
    )
    return [int(match.group(1), 16) for match in pattern.finditer(text)]


def assert_subsequence(actual: list[T], expected: list[T], label: str) -> None:
    cursor = 0
    for item in actual:
        if cursor < len(expected) and item == expected[cursor]:
            cursor += 1
    if cursor != len(expected):
        raise AssertionError(
            f"{label}: expected subsequence {expected!r}, got {actual!r}"
        )


def main() -> int:
    health = json.loads(wait_http("/healthz", 200))
    assert health == {"status": "ok"}
    ready = json.loads(wait_http("/readyz", 200))
    assert ready == {"status": "healthy"}

    transport = SocketCanTransport("vcan0")
    try:
        client = BeamControlClient(transport, timeout=0.5, retries=2)
        legacy, info = client.discover(1)
        assert legacy[0] == 1 and legacy[1] == 1
        assert info is not None
        assert (info.major, info.minor, info.patch) == (1, 1, 0)
        assert info.node_id == 1
        assert info.feature_flags == P.FEATURE_FLAGS

        assert client.set_phase(1, 128, 2) == bytes([P.SET_PHASE, P.RES_OK])
        assert client.set_vga(1, 8) == bytes([P.SET_VGA, P.RES_OK])
        assert client.set_combined(1, 64, 1, 12) == bytes([P.SET_COMBINED, P.RES_OK])
        assert client.enter_safe(1, 1) == bytes([P.ENTER_SAFE, P.RES_OK])
    finally:
        transport.close()

    snapshot = json.loads(wait_http("/api/status", 200))
    assert snapshot["service"]["health"] == "healthy"
    assert snapshot["can"]["channel"] == "vcan0"
    assert snapshot["configuration"]["target_nodes"] == [1]
    assert snapshot["nodes"][0]["node_id"] == 1
    assert snapshot["nodes"][0]["health"] == "healthy"
    assert snapshot["nodes"][0]["protocol_version"] == "1.1.0"

    text = wait_for_log("SIM_SPI2 offset=0xC value=0x8")

    # Actual STM32 data-register writes. These include startup, a direct phase
    # change, a combined safe transition, and ENTER_SAFE.
    assert_subsequence(
        values(text, "SPI1", 0xC),
        [0x5C, 0x20, 0x5C, 0x30, 0x5C],
        "VGA SPI writes",
    )
    assert_subsequence(
        values(text, "SPI2", 0xC),
        [
            0x162C,  # startup: calibrated state 146, address 3
            0x17C4,  # SET_PHASE: calibrated state 128, address 2
            0x0058,  # SET_COMBINED: calibrated state 64, address 1
            0x0008,  # ENTER_SAFE: calibrated state 0, address 1
        ],
        "phase-shifter SPI writes",
    )

    # GPIO BSRR writes prove idle-high setup and low/high latch sequences.
    gpio_a = values(text, "GPIOA", 0x18)
    gpio_b = values(text, "GPIOB", 0x18)
    gpio_c = values(text, "GPIOC", 0x18)
    assert_subsequence(gpio_a, [0x10, 0x100000, 0x10], "VGA chip-select GPIO")
    assert_subsequence(gpio_b, [0x1000, 0x10000000, 0x1000], "phase latch GPIO")
    assert 0x400 in gpio_c, f"phase serial-select was not driven high: {gpio_c!r}"

    print("BeamControl virtual end-to-end test passed")
    print("  real Python controller and FastAPI dashboard: healthy")
    print("  real STM32F072 ELF in Renode: protocol v1.1 node 1")
    print("  SocketCAN round trips: discover, phase, VGA, combined, safe")
    print("  SPI/GPIO transaction sequence: verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"virtual E2E failed: {error}", file=sys.stderr)
        raise
