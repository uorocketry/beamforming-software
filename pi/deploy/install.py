#!/usr/bin/env python3
"""Install an extracted BeamControl Pi bundle atomically and restart its services."""

from __future__ import annotations

import grp
import os
import shutil
import subprocess
from pathlib import Path

from target_platform import validate_debian_trixie, validate_pi5_target


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


def repair_venv_entrypoints(venv: Path) -> None:
    """Rewrite console-script shebangs after the staged release directory is renamed."""
    bindir = venv / "bin"
    interpreter = os.fsencode(bindir / "python3.11")
    for entrypoint in bindir.iterdir():
        if entrypoint.is_symlink() or not entrypoint.is_file():
            continue
        data = entrypoint.read_bytes()
        first_line, newline, remainder = data.partition(b"\n")
        if newline and first_line.startswith(b"#!") and b"/venv/bin/python" in first_line:
            entrypoint.write_bytes(b"#!" + interpreter + b"\n" + remainder)


def bundled_python_runtime(bundle_dir: Path) -> Path:
    """Return the single bundled uv-managed CPython 3.11 runtime."""
    python_root = bundle_dir / "python"
    candidates = [
        directory
        for directory in python_root.iterdir()
        if directory.is_dir() and (directory / "bin/python3.11").is_file()
    ]
    if len(candidates) != 1:
        raise SystemExit("error: bundle must contain exactly one uv-managed Python 3.11 runtime")
    return candidates[0]


def install_python_runtime(bundle_dir: Path) -> Path:
    """Install the bundled Python runtime under /opt and return its interpreter."""
    bundled = bundled_python_runtime(bundle_dir)
    destination = Path("/opt/uorocketry/python") / bundled.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        staging = destination.with_name(f".{destination.name}.new")
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(bundled, staging, symlinks=True)
        staging.replace(destination)
    interpreter = destination / "bin/python3.11"
    if not interpreter.is_file():
        raise SystemExit(f"error: installed Python runtime is incomplete: {interpreter}")
    return interpreter


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("error: run this installer as root, for example `sudo python3 install.py`")

    try:
        model = validate_pi5_target()
        operating_system = validate_debian_trixie()
    except RuntimeError as error:
        raise SystemExit(f"error: {error}") from error

    bundle_dir = Path(__file__).resolve().parent
    uv = bundle_dir / "uv"
    if not uv.is_file() or not os.access(uv, os.X_OK):
        raise SystemExit(f"error: bundled uv binary is missing or not executable: {uv}")
    python = install_python_runtime(bundle_dir)

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

    run(
        [
            uv,
            "venv",
            "--python",
            python,
            "--no-python-downloads",
            "--offline",
            "--no-cache",
            staging / "venv",
        ]
    )
    venv_python = staging / "venv/bin/python"
    run(
        [
            uv,
            "pip",
            "install",
            "--python",
            venv_python,
            "--no-python-downloads",
            "--offline",
            "--no-cache",
            "--link-mode",
            "copy",
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
            uv,
            "pip",
            "install",
            "--python",
            venv_python,
            "--no-python-downloads",
            "--offline",
            "--no-cache",
            "--link-mode",
            "copy",
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
    repair_venv_entrypoints(release_dir / "venv")
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
    print(f"BeamControl controller installed on {model}, {operating_system}: {current} ({version})")


if __name__ == "__main__":
    main()
