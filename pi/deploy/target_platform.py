"""Deployment-target validation shared by BeamControl Pi installers."""

from __future__ import annotations

import platform
from pathlib import Path

PI_MODEL_PATH = Path("/proc/device-tree/model")
SUPPORTED_MODEL_PREFIX = "Raspberry Pi 5 Model"


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
