"""Deployment-target validation shared by BeamControl Pi installers."""

from __future__ import annotations

import platform
from collections.abc import Mapping
from pathlib import Path

PI_MODEL_PATH = Path("/proc/device-tree/model")
SUPPORTED_MODEL_PREFIX = "Raspberry Pi 5 Model"
SUPPORTED_OS_ID = "debian"
SUPPORTED_OS_VERSION = "13"
SUPPORTED_OS_CODENAME = "trixie"


def read_device_model(path: Path = PI_MODEL_PATH) -> str:
    """Return the device-tree model string, stripping its trailing NUL."""
    try:
        return path.read_bytes().rstrip(b"\x00").decode("utf-8", errors="replace").strip()
    except FileNotFoundError:
        return ""


def validate_pi5_target(*, machine: str | None = None, model_path: Path = PI_MODEL_PATH) -> str:
    """Validate that the current host is an ARM64 Raspberry Pi 5."""
    architecture = (machine or platform.machine()).lower()
    if architecture not in {"aarch64", "arm64"}:
        raise RuntimeError(
            f"BeamControl deployment requires Raspberry Pi 5 ARM64; found {architecture}"
        )

    model = read_device_model(model_path)
    if not model.startswith(SUPPORTED_MODEL_PREFIX):
        displayed = model or "no Raspberry Pi device-tree model"
        raise RuntimeError(f"BeamControl deployment requires a Raspberry Pi 5; found {displayed}")
    return model


def validate_debian_trixie(*, release: Mapping[str, str] | None = None) -> str:
    """Validate the canonical Debian GNU/Linux 13 (trixie) deployment OS."""
    details = dict(platform.freedesktop_os_release() if release is None else release)
    os_id = details.get("ID", "unknown").lower()
    version = details.get("VERSION_ID", "unknown")
    codename = details.get("VERSION_CODENAME", "unknown").lower()
    if (
        os_id != SUPPORTED_OS_ID
        or version != SUPPORTED_OS_VERSION
        or codename != SUPPORTED_OS_CODENAME
    ):
        pretty = details.get("PRETTY_NAME", f"{os_id} {version} ({codename})")
        raise RuntimeError(
            f"BeamControl deployment requires Debian GNU/Linux 13 (trixie); found {pretty}"
        )
    return details.get("PRETTY_NAME", "Debian GNU/Linux 13 (trixie)")
