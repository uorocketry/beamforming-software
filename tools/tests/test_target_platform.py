from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "pi/deploy/target_platform.py"
SPEC = importlib.util.spec_from_file_location(
    "beamcontrol_target_platform", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
TARGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TARGET)


def write_model(path: Path, model: str) -> None:
    path.write_bytes(model.encode("utf-8") + b"\x00")


def test_accepts_raspberry_pi_5_arm64(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    write_model(model_path, "Raspberry Pi 5 Model B Rev 1.0")

    assert (
        TARGET.validate_pi5_target(machine="aarch64", model_path=model_path)
        == "Raspberry Pi 5 Model B Rev 1.0"
    )


def test_rejects_non_arm64(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    write_model(model_path, "Raspberry Pi 5 Model B Rev 1.0")

    with pytest.raises(RuntimeError, match="requires Raspberry Pi 5 ARM64"):
        TARGET.validate_pi5_target(machine="x86_64", model_path=model_path)


def test_rejects_other_arm64_machine(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    write_model(model_path, "Generic ARM64 Server")

    with pytest.raises(RuntimeError, match="requires a Raspberry Pi 5"):
        TARGET.validate_pi5_target(machine="aarch64", model_path=model_path)


def test_rejects_missing_device_tree_model(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no Raspberry Pi device-tree model"):
        TARGET.validate_pi5_target(machine="arm64", model_path=tmp_path / "missing")
