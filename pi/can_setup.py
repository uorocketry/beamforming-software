#!/usr/bin/env python3
"""Bring up a SocketCAN interface for BeamControl protocol v1.1."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections.abc import Sequence


def run_ip(arguments: Sequence[str], *, check: bool = True) -> None:
    prefix: list[str] = []
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo is None:
            raise SystemExit("error: root privileges are required and sudo was not found")
        prefix.append(sudo)
    subprocess.run([*prefix, "ip", *arguments], check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("interface", nargs="?", default="can0")
    args = parser.parse_args()

    run_ip(["link", "set", args.interface, "down"], check=False)
    run_ip(
        [
            "link",
            "set",
            args.interface,
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
        ]
    )
    run_ip(["link", "set", args.interface, "up"])
    print(f"--- {args.interface} ---")
    subprocess.run(
        ["ip", "-details", "-statistics", "link", "show", args.interface],
        check=True,
    )


if __name__ == "__main__":
    main()
