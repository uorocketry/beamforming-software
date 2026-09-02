#!/usr/bin/env python3
"""Dry smoke every supported beamctl command without opening SocketCAN."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

COMMANDS = (
    ("discover",),
    ("ping", "1"),
    ("set-phase", "1", "--state", "128"),
    ("set-vga", "1", "--attenuation", "8"),
    (
        "set-combined",
        "1",
        "--state",
        "128",
        "--attenuation",
        "8",
    ),
    ("enter-safe", "1"),
)


def main() -> None:
    environment = os.environ.copy()
    source_root = Path(__file__).resolve().parents[1] / "pi" / "src"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(source_root)
    )
    for command in COMMANDS:
        completed = subprocess.run(
            [sys.executable, "-m", "beamcontrol.cli", *command, "--dry-run"],
            check=True,
            env=environment,
            text=True,
            capture_output=True,
        )
        print(f"[OK] {' '.join(command)}")
        print(f"     {completed.stdout.strip()}")
    print(f"Dry command smoke passed: {len(COMMANDS)} command forms.")


if __name__ == "__main__":
    main()
