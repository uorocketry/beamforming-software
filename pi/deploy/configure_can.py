#!/usr/bin/env python3
"""Resolve the HAT's physical CAN0 by SPI parent and configure SocketCAN."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

IP = Path("/usr/sbin/ip")
PHYSICAL_CAN0 = Path("/sys/bus/spi/devices/spi1.1/net")
INTERFACE = "beamcan0"


def run(command: list[str | os.PathLike[str]], *, check: bool = True) -> None:
    subprocess.run([os.fspath(part) for part in command], check=check)


def resolve_interface(net_dir: Path = PHYSICAL_CAN0, *, timeout_s: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_s
    while True:
        if net_dir.is_dir():
            interfaces = sorted(path.name for path in net_dir.iterdir())
            if len(interfaces) == 1:
                return interfaces[0]
            if len(interfaces) > 1:
                raise RuntimeError(
                    f"expected one CAN interface under {net_dir}, found {interfaces}"
                )
        if time.monotonic() >= deadline:
            raise RuntimeError(f"CAN controller did not appear under {net_dir}")
        time.sleep(0.1)


def setup() -> None:
    source = resolve_interface()
    if source != INTERFACE:
        run([IP, "link", "set", source, "down"], check=False)
        run([IP, "link", "set", source, "name", INTERFACE])

    run([IP, "link", "set", INTERFACE, "down"], check=False)
    run(
        [
            IP,
            "link",
            "set",
            INTERFACE,
            "type",
            "can",
            "bitrate",
            "500000",
            "sample-point",
            "0.875",
            "sjw",
            "1",
            "restart-ms",
            "100",
            "loopback",
            "off",
        ]
    )
    run([IP, "link", "set", INTERFACE, "up"])


def stop() -> None:
    run([IP, "link", "set", INTERFACE, "down"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("setup", "stop"))
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    else:
        stop()


if __name__ == "__main__":
    main()
