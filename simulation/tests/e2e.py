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
        status = client.discover(1)
        assert status.version == P.PROTOCOL_VERSION
        assert status.node_id == 1

        assert client.set_phase(1, [128, 64, 32, 16]) == bytes([P.SET_PHASE, P.RES_OK])
        assert client.set_vga(1, [8, 9, 10, 11]) == bytes([P.SET_VGA, P.RES_OK])
        assert client.set_combined(
            1,
            [64, 65, 66, 67],
            [12, 13, 14, 15],
        ) == bytes([P.SET_COMBINED, P.RES_OK])
        assert client.set_phase_channel(1, 2, 146) == bytes([P.SET_PHASE, P.RES_OK])
        assert client.set_vga_channel(1, 1, 7) == bytes([P.SET_VGA, P.RES_OK])
        assert client.set_combined_channel(1, 0, 32, 6) == bytes(
            [P.SET_COMBINED, P.RES_OK]
        )
        assert client.enter_safe(1, 1) == bytes([P.ENTER_SAFE, P.RES_OK])
    finally:
        transport.close()

    snapshot = json.loads(wait_http("/api/status", 200))
    assert snapshot["service"]["health"] == "healthy"
    assert snapshot["can"]["channel"] == "vcan0"
    assert snapshot["configuration"]["target_nodes"] == [1]
    assert snapshot["nodes"][0]["node_id"] == 1
    assert snapshot["nodes"][0]["health"] == "healthy"
    assert snapshot["nodes"][0]["protocol_version"] == "2.1.0"

    text = wait_for_log("SIM_SPI2 offset=0xC value=0x1628")

    # Actual STM32 data-register writes. The expected order mirrors the
    # control planner comments: startup, bulk phase, bulk VGA, combined safe
    # transition, and finally one-channel ENTER_SAFE.
    assert_subsequence(
        values(text, "SPI1", 0xC),
        [
            0x5C,
            0x5C,
            0x5C,
            0x5C,  # startup: 23 dB requested for channels 1..4
            0x20,
            0x24,
            0x28,
            0x2C,  # SET_VGA: 8, 9, 10, 11 dB
            0x5C,
            0x5C,
            0x5C,
            0x5C,  # SET_COMBINED stage 1: maximum attenuation
            0x30,
            0x34,
            0x38,
            0x3C,  # bulk combined stage 3: 12, 13, 14, 15 dB
            0x5C,
            0x38,  # individual phase: protect and restore channel 3
            0x1C,  # individual VGA: 7 dB on channel 2
            0x5C,
            0x18,  # individual combined: protect then apply 6 dB on channel 1
            0x5C,  # ENTER_SAFE channel 2
        ],
        "VGA SPI writes",
    )
    assert_subsequence(
        values(text, "SPI2", 0xC),
        [
            0x1628,
            0x1624,
            0x162C,
            0x1622,  # startup: calibrated state 146, addresses 1..4
            0x17C8,
            0x0054,
            0x008C,
            0x0102,  # SET_PHASE: states 128, 64, 32, 16
            0x0058,
            0x0F94,
            0x085C,
            0x1852,  # bulk combined: states 64, 65, 66, 67
            0x162C,  # individual phase: state 146, address 3
            0x0088,  # individual combined: state 32, address 1
            0x0004,  # ENTER_SAFE: state 0, address 2
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
    print("  real STM32F072 ELF in Renode: protocol v2.1 node 1")
    print("  SocketCAN round trips: discovery, individual/bulk RF updates, safe")
    print("  SPI/GPIO transaction sequence: verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"virtual E2E failed: {error}", file=sys.stderr)
        raise
