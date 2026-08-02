#!/usr/bin/env python3
"""Diagnose the BeamControl development environment without modifying it."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from script_support import REPO_ROOT, ToolError, load_lock


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def ok(self, message: str) -> None:
        print(f"[OK]   {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"[FAIL] {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def skip(self, message: str) -> None:
        print(f"[SKIP] {message}")


def first_line(command: list[str | os.PathLike[str]]) -> str:
    completed = subprocess.run(
        [os.fspath(part) for part in command],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip().splitlines()[0]


def check_command(report: Report, name: str, *, required: bool = True) -> Path | None:
    resolved = shutil.which(name)
    if resolved is not None:
        report.ok(f"{name}: {resolved}")
        return Path(resolved)
    if required:
        report.fail(f"required command missing: {name}")
    else:
        report.warn(f"optional command missing: {name}")
    return None


def check_platform(report: Report) -> None:
    system = platform.system()
    machine = platform.machine().lower()
    if system != "Linux":
        report.fail(
            f"unsupported platform: {system}; use Linux or Windows through WSL2"
        )
    elif machine not in {"x86_64", "amd64", "aarch64", "arm64"}:
        report.fail(f"unsupported Linux architecture: {machine}")
    else:
        os_release = Path("/proc/sys/kernel/osrelease")
        release = (
            os_release.read_text(encoding="utf-8").strip()
            if os_release.exists()
            else ""
        )
        environment = "WSL" if "microsoft" in release.lower() else "Linux"
        report.ok(f"platform: {environment} {machine}")
        if environment == "WSL" and str(REPO_ROOT).startswith("/mnt/"):
            report.warn(
                "repository is on a Windows-mounted WSL path; use the WSL filesystem"
            )


def check_python(report: Report) -> None:
    version = platform.python_version()
    current_version = sys.version_info[:2]
    if current_version >= (3, 10):
        report.ok(f"bootstrap Python: {version}")
    else:
        report.fail(
            f"Python 3.10 or newer is required for repository tooling; found {version}"
        )

    venv_python = REPO_ROOT / "pi/.venv/bin/python"
    if not venv_python.is_file():
        report.fail("Pi virtual environment missing; run `make setup`")
        return
    try:
        venv_version = first_line(
            [venv_python, "-c", "import platform; print(platform.python_version())"]
        )
        subprocess.run(
            [
                venv_python,
                "-c",
                "import beamcontrol; from beamcontrol.web.server import create_app",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        report.fail("Pi virtual environment is incomplete; rerun `make setup`")
        return
    if venv_version.startswith("3.11."):
        report.ok(
            f"Pi environment: Python {venv_version}, BeamControl dashboard importable"
        )
    else:
        report.fail(f"Pi environment must use Python 3.11; found {venv_version}")


def check_uv(report: Report) -> None:
    lock = load_lock(REPO_ROOT / "tools/uv.lock")
    expected = lock["UV_VERSION"]
    uv = REPO_ROOT / ".tools/bin/uv"
    if not uv.is_file():
        report.fail("pinned uv missing; run `make setup`")
        return
    try:
        installed = first_line([uv, "--version"])
    except (OSError, subprocess.CalledProcessError):
        report.fail(f"repository-local uv is not executable: {uv}")
        return
    if expected in installed:
        report.ok(installed)
    else:
        report.fail(f"uv version mismatch: expected {expected}, found {installed}")


def check_arm_toolchain(report: Report) -> None:
    lock = load_lock(REPO_ROOT / "stm32/third_party/arm-toolchain.lock")
    expected = lock["ARM_VERSION"]
    local = REPO_ROOT / ".tools/arm-gnu-toolchain/bin/arm-none-eabi-gcc"
    compiler: Path | None = local if local.is_file() else None
    source = "repository-local"
    if compiler is None and os.environ.get("USE_SYSTEM_ARM_TOOLCHAIN") == "1":
        resolved = shutil.which("arm-none-eabi-gcc")
        compiler = Path(resolved) if resolved else None
        source = "system"
    if compiler is None:
        report.fail("ARM GNU toolchain missing; run `make setup`")
        return
    try:
        installed = first_line([compiler, "--version"])
    except (OSError, subprocess.CalledProcessError):
        report.fail(f"ARM compiler is not executable: {compiler}")
        return
    if source == "repository-local" and expected.lower() not in installed.lower():
        report.fail(
            f"ARM toolchain version mismatch: expected {expected}, found {installed}"
        )
    else:
        report.ok(f"ARM toolchain ({source}): {installed}")


def check_libopencm3(report: Report) -> None:
    lock = load_lock(REPO_ROOT / "stm32/third_party/libopencm3.lock")
    expected = lock["LIBOPENCM3_COMMIT"]
    destination = REPO_ROOT / "stm32/.deps/libopencm3"
    marker = destination / ".uorocketry-commit"
    if not marker.is_file() or not (destination / "Makefile").is_file():
        report.fail("libopencm3 is missing or incomplete; run `make setup`")
        return
    actual = marker.read_text(encoding="utf-8").strip()
    if actual == expected:
        report.ok(f"libopencm3 pinned revision: {actual}")
    else:
        report.fail(
            f"libopencm3 revision mismatch: expected {expected}, found {actual}"
        )


def check_protocol(report: Report) -> None:
    project_python = REPO_ROOT / "pi/.venv/bin/python"
    if not project_python.is_file():
        report.skip(
            "protocol vector check requires the Pi environment from `make setup`"
        )
        return
    completed = subprocess.run(
        [project_python, REPO_ROOT / "tools/generate-protocol-vectors.py", "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        report.ok("generated protocol vectors are current")
    else:
        detail = completed.stderr.strip() or completed.stdout.strip()
        report.fail(f"generated protocol vectors are stale: {detail}")


def check_optional_capabilities(report: Report) -> None:
    check_command(report, "cppcheck", required=False)
    ip = check_command(report, "ip", required=False)
    check_command(report, "candump", required=False)
    if ip is None:
        report.skip("SocketCAN interface check unavailable")
        return
    can0 = subprocess.run(
        [ip, "link", "show", "can0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if can0.returncode == 0:
        report.ok("SocketCAN interface can0 is present")
    else:
        report.skip("can0 is not present; physical CAN tests are unavailable")


def main() -> None:
    report = Report()
    print("BeamControl development environment\n")

    check_platform(report)
    if REPO_ROOT.joinpath("Makefile").is_file() and REPO_ROOT.joinpath(".git").exists():
        report.ok(f"repository root: {REPO_ROOT}")
    else:
        report.fail(f"repository root is incomplete: {REPO_ROOT}")

    check_python(report)
    check_command(report, "make")
    check_command(report, "git")
    check_command(report, "cc")
    check_uv(report)
    check_arm_toolchain(report)
    check_libopencm3(report)
    check_protocol(report)
    check_optional_capabilities(report)

    print()
    if report.failures:
        print(
            f"Environment incomplete: {len(report.failures)} required check(s) failed."
        )
        raise SystemExit(1)
    if report.warnings:
        print(f"Environment ready with {len(report.warnings)} optional warning(s).")
    else:
        print("Environment ready.")


if __name__ == "__main__":
    try:
        main()
    except ToolError as error:
        raise SystemExit(f"error: {error}") from error
