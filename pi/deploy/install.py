#!/usr/bin/env python3
"""Install an extracted BeamControl Pi bundle atomically and restart its services."""

from __future__ import annotations

import grp
import os
import shutil
import subprocess
import sys
from pathlib import Path

from target_platform import validate_pi5_target


def run(command: list[str | os.PathLike[str]], *, check: bool = True) -> None:
    subprocess.run([os.fspath(part) for part in command], check=check)


def install_file(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination.chmod(mode)


def switch_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.new")
    temporary.unlink(missing_ok=True)
    os.symlink(target, temporary)
    os.replace(temporary, link)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("error: run this installer as root, for example `sudo python3 install.py`")

    try:
        model = validate_pi5_target()
    except RuntimeError as error:
        raise SystemExit(f"error: {error}") from error
    python_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if python_minor != "3.11":
        raise SystemExit(f"error: BeamControl wheels target Python 3.11, found {python_minor}")

    bundle_dir = Path(__file__).resolve().parent
    version_file = bundle_dir / "VERSION"
    if not version_file.is_file():
        raise SystemExit(f"error: bundle VERSION file is missing: {version_file}")
    version = version_file.read_text(encoding="utf-8").strip()
    if not version or "/" in version:
        raise SystemExit(f"error: invalid bundle version: {version!r}")

    release_root = Path("/opt/uorocketry/beamcontrol/releases")
    staging = release_root / f".staging-{version}"
    release_dir = release_root / version
    current = Path("/opt/uorocketry/beamcontrol/current")
    release_root.mkdir(parents=True, exist_ok=True)

    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(mode=0o755)
    shutil.copytree(bundle_dir / "wheelhouse", staging / "wheelhouse")
    shutil.copy2(bundle_dir / "requirements.lock", staging / "requirements.lock")

    run([sys.executable, "-m", "venv", staging / "venv"])
    pip = staging / "venv/bin/pip"
    run(
        [
            pip,
            "install",
            "--no-index",
            "--require-hashes",
            "--find-links",
            staging / "wheelhouse",
            "--requirement",
            staging / "requirements.lock",
        ]
    )
    run(
        [
            pip,
            "install",
            "--no-index",
            "--find-links",
            staging / "wheelhouse",
            "beamcontrol",
        ]
    )

    if release_dir.is_dir():
        print(f"release {version} already installed; keeping existing directory")
        shutil.rmtree(staging)
    else:
        staging.replace(release_dir)
    switch_symlink(release_dir, current)

    install_file(
        bundle_dir / "systemd/beamcontrol-can.service",
        Path("/etc/systemd/system/beamcontrol-can.service"),
        0o644,
    )
    install_file(
        bundle_dir / "systemd/beamcontrol.service",
        Path("/etc/systemd/system/beamcontrol.service"),
        0o644,
    )

    config = Path("/etc/uorocketry/beamcontrol.toml")
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        install_file(bundle_dir / "config/beamcontrol.toml.example", config, 0o640)
        beamcontrol_group = grp.getgrnam("beamcontrol")
        os.chown(config, 0, beamcontrol_group.gr_gid)

    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "beamcontrol-can.service", "beamcontrol.service"])
    run(["systemctl", "stop", "beamcontrol.service"], check=False)
    run(["systemctl", "restart", "beamcontrol-can.service"], check=False)
    run(["systemctl", "start", "beamcontrol.service"])
    print(f"BeamControl controller installed on {model}: {current} ({version})")


if __name__ == "__main__":
    main()
