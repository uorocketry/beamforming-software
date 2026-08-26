from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "pi/deploy"
sys.path.insert(0, str(DEPLOY_DIR))
SPEC = importlib.util.spec_from_file_location(
    "beamcontrol_install", DEPLOY_DIR / "install.py"
)
assert SPEC is not None and SPEC.loader is not None
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


def test_repair_venv_entrypoints_rewrites_staged_shebang(tmp_path: Path) -> None:
    venv = tmp_path / "release/venv"
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    entrypoint = bindir / "beamd"
    entrypoint.write_bytes(
        b"#!/opt/uorocketry/beamcontrol/releases/.staging-test/venv/bin/python3.11\n"
        b"print('ok')\n"
    )
    untouched = bindir / "activate"
    untouched.write_text("# shell activation\n", encoding="utf-8")

    INSTALL.repair_venv_entrypoints(venv)

    assert entrypoint.read_bytes() == (
        f"#!{bindir / 'python3.11'}\n".encode() + b"print('ok')\n"
    )
    assert untouched.read_text(encoding="utf-8") == "# shell activation\n"


def test_bundled_python_runtime_requires_exactly_one_runtime(tmp_path: Path) -> None:
    python_root = tmp_path / "python"
    runtime = python_root / "cpython-3.11.15-linux-aarch64-gnu"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin/python3.11").write_text("", encoding="utf-8")

    assert INSTALL.bundled_python_runtime(tmp_path) == runtime

    second = python_root / "cpython-3.11.16-linux-aarch64-gnu"
    (second / "bin").mkdir(parents=True)
    (second / "bin/python3.11").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="exactly one uv-managed Python 3.11 runtime"):
        INSTALL.bundled_python_runtime(tmp_path)
