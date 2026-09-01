#!/usr/bin/env python3
"""Dry smoke every supported beamctl command without opening SocketCAN."""

from __future__ import annotations

import subprocess
import sys

COMMANDS = (
    ("discover",),
    ("ping", "1"),
    ("set-phase", "1", "--state", "128", "--channel", "2"),
    ("set-phase", "1", "--states", "1", "2", "3", "4"),
    ("set-vga", "1", "--attenuation", "8", "--channel", "2"),
    ("set-vga", "1", "--attenuations", "8", "9", "10", "11"),
    (
        "set-combined",
        "1",
        "--state",
        "128",
        "--attenuation",
        "8",
        "--channel",
        "2",
    ),
    (
        "set-combined",
        "1",
        "--states",
        "1",
        "2",
        "3",
        "4",
        "--attenuations",
        "8",
        "9",
        "10",
        "11",
    ),
    ("enter-safe", "1", "--channel", "2"),
)


def main() -> None:
    for command in COMMANDS:
        completed = subprocess.run(
            [sys.executable, "-m", "beamcontrol.cli", *command, "--dry-run"],
            check=True,
            text=True,
            capture_output=True,
        )
        print(f"[OK] {' '.join(command)}")
        print(f"     {completed.stdout.strip()}")
    print(f"Dry command smoke passed: {len(COMMANDS)} command forms.")


if __name__ == "__main__":
    main()
