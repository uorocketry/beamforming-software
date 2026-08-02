#!/usr/bin/env python3
"""Provision the qualified Raspberry Pi OS Bookworm image for BeamControl."""

from __future__ import annotations

import grp
import os
import platform
import pwd
import subprocess
from pathlib import Path

from target_platform import validate_pi5_target

OVERLAYS = (
    "dtparam=spi=on",
    "dtoverlay=i2c0",
    "dtoverlay=spi1-3cs",
    "dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22",
    "dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13",
)


def run(command: list[str], *, check: bool = True) -> None:
    subprocess.run(command, check=check)


def ensure_directory(path: Path, *, mode: int, owner: str | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)
    if owner is not None:
        account = pwd.getpwnam(owner)
        os.chown(path, account.pw_uid, account.pw_gid)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit(
            "error: run provisioning as root, for example `sudo python3 provision_os.py`"
        )

    try:
        model = validate_pi5_target()
    except RuntimeError as error:
        raise SystemExit(f"error: {error}") from error

    os_release = platform.freedesktop_os_release()
    codename = os_release.get("VERSION_CODENAME", "unknown")
    if codename != "bookworm":
        raise SystemExit(
            "error: BeamControl requires the qualified Raspberry Pi OS Bookworm image; "
            f"found {codename}. See docs/operations/pi-provisioning.md."
        )

    run(["apt-get", "update"])
    run(
        [
            "apt-get",
            "install",
            "--yes",
            "python3",
            "python3-venv",
            "can-utils",
            "iproute2",
        ]
    )

    candidates = (Path("/boot/firmware/config.txt"), Path("/boot/config.txt"))
    config = next((path for path in candidates if path.is_file()), None)
    if config is None:
        checked = " and ".join(str(path) for path in candidates)
        raise SystemExit(f"error: Raspberry Pi boot config not found; checked {checked}")

    existing = set(config.read_text(encoding="utf-8").splitlines())
    missing = [overlay for overlay in OVERLAYS if overlay not in existing]
    if missing:
        with config.open("a", encoding="utf-8") as handle:
            if config.stat().st_size and not config.read_bytes().endswith(b"\n"):
                handle.write("\n")
            for overlay in missing:
                handle.write(f"{overlay}\n")

    try:
        grp.getgrnam("beamcontrol")
    except KeyError:
        run(["groupadd", "--system", "beamcontrol"])

    try:
        pwd.getpwnam("beamcontrol")
    except KeyError:
        run(
            [
                "useradd",
                "--system",
                "--gid",
                "beamcontrol",
                "--home",
                "/var/lib/uorocketry/beamcontrol",
                "--create-home",
                "--shell",
                "/usr/sbin/nologin",
                "beamcontrol",
            ]
        )

    ensure_directory(Path("/etc/uorocketry"), mode=0o755)
    ensure_directory(Path("/opt/uorocketry/beamcontrol/releases"), mode=0o755)
    ensure_directory(Path("/var/lib/uorocketry/beamcontrol"), mode=0o755, owner="beamcontrol")

    print(f"Provisioning complete for {model}. Reboot to apply the CAN overlays.")


if __name__ == "__main__":
    main()
