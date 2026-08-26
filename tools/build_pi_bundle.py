#!/usr/bin/env python3
"""Build the offline Raspberry Pi deployment bundle on an aarch64 host."""

from __future__ import annotations

import platform
import shutil
import stat
import tarfile
from pathlib import Path

from script_support import (
    REPO_ROOT,
    ToolError,
    command_output,
    main_guard,
    run,
)


def create_bundle(stage: Path, bundle: Path) -> None:
    """Create a gzip-compressed deployment archive using only the stdlib."""
    bundle.unlink(missing_ok=True)
    with tarfile.open(bundle, "w:gz") as archive:
        archive.add(stage, arcname=stage.name)


def managed_python_runtime(uv: Path, version: str) -> Path:
    """Return the resolved uv-managed Python runtime root for a version."""
    interpreter = Path(
        command_output([uv, "python", "find", "--managed-python", version])
    ).resolve()
    runtime = interpreter.parents[1]
    if not (runtime / "bin/python3.11").is_file():
        raise ToolError(f"uv-managed Python runtime is incomplete: {runtime}")
    return runtime


def main() -> None:
    machine = platform.machine().lower()
    if machine not in {"aarch64", "arm64"}:
        raise ToolError(
            f"Pi deployment bundles must be built on aarch64, found {machine}"
        )

    uv = REPO_ROOT / ".tools/bin/uv"
    if not uv.is_file():
        raise ToolError("repository-local uv is missing; run `make setup` first")

    version = command_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
    build = REPO_ROOT / "build"
    stage = build / f"beamcontrol-pi-{version}"
    bundle = build / f"beamcontrol-pi-{version}.tar.gz"
    wheel_venv = build / ".wheel-venv"
    target_python = "3.11"

    shutil.rmtree(stage, ignore_errors=True)
    for directory in (
        stage / "wheelhouse",
        stage / "systemd",
        stage / "config",
        stage / "python",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    run(
        [
            uv,
            "build",
            "--project",
            REPO_ROOT / "pi",
            "--wheel",
            "--out-dir",
            stage / "wheelhouse",
        ]
    )
    run(
        [
            uv,
            "export",
            "--project",
            REPO_ROOT / "pi",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements.txt",
            "--output-file",
            stage / "requirements.lock",
        ]
    )

    run([uv, "python", "install", target_python])
    runtime = managed_python_runtime(uv, target_python)
    shutil.copytree(runtime, stage / "python" / runtime.name, symlinks=True)
    shutil.copy2(uv, stage / "uv")
    (stage / "uv").chmod(
        (stage / "uv").stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    shutil.rmtree(wheel_venv, ignore_errors=True)
    run([uv, "venv", "--python", target_python, "--seed", wheel_venv])
    run(
        [
            wheel_venv / "bin/python",
            "-m",
            "pip",
            "download",
            "--require-hashes",
            "--only-binary=:all:",
            "--requirement",
            stage / "requirements.lock",
            "--dest",
            stage / "wheelhouse",
        ]
    )

    installer = stage / "install.py"
    shutil.copy2(REPO_ROOT / "pi/deploy/install.py", installer)
    installer.chmod(
        installer.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    shutil.copy2(REPO_ROOT / "pi/deploy/target_platform.py", stage)
    shutil.copy2(REPO_ROOT / "pi/deploy/beamcontrol-can.service", stage / "systemd")
    shutil.copy2(REPO_ROOT / "pi/deploy/beamcontrol.service", stage / "systemd")
    shutil.copy2(REPO_ROOT / "pi/deploy/beamcontrol.toml.example", stage / "config")
    (stage / "VERSION").write_text(f"{version}\n", encoding="utf-8")

    create_bundle(stage, bundle)
    print(f"bundle: {bundle}")


if __name__ == "__main__":
    main_guard(main)
