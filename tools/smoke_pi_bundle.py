"""Smoke-test an extracted BeamControl offline Pi bundle without system changes."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from script_support import safe_extract


def run(command: list[str | Path]) -> None:
    subprocess.run([os.fspath(part) for part in command], check=True)


def find_bundle_root(extracted: Path) -> Path:
    roots = [path for path in extracted.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"expected one bundle root, found {len(roots)}")
    return roots[0]


def bundled_python(root: Path) -> Path:
    candidates = [
        directory / "bin/python3.11"
        for directory in (root / "python").iterdir()
        if directory.is_dir() and (directory / "bin/python3.11").is_file()
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one bundled Python 3.11 runtime, found {len(candidates)}"
        )
    return candidates[0]


def smoke_test(bundle: Path) -> None:
    with tempfile.TemporaryDirectory(
        prefix="beamcontrol-bundle-smoke-"
    ) as temporary_name:
        temporary = Path(temporary_name)
        extracted = temporary / "extracted"
        extracted.mkdir()
        safe_extract(bundle, extracted)

        root = find_bundle_root(extracted)
        required = (
            root / "VERSION",
            root / "install.py",
            root / "target_platform.py",
            root / "requirements.lock",
            root / "wheelhouse",
            root / "uv",
            root / "python",
            root / "systemd/beamcontrol.service",
            root / "systemd/beamcontrol-can.service",
            root / "config/beamcontrol.toml.example",
        )
        missing = [
            str(path.relative_to(root)) for path in required if not path.exists()
        ]
        if missing:
            raise RuntimeError(
                f"bundle is missing required files: {', '.join(missing)}"
            )

        uv = root / "uv"
        python = bundled_python(root)
        environment = temporary / "venv"
        run(
            [
                uv,
                "venv",
                "--python",
                python,
                "--no-python-downloads",
                "--offline",
                "--no-cache",
                environment,
            ]
        )
        environment_python = environment / "bin/python"
        run(
            [
                uv,
                "pip",
                "install",
                "--python",
                environment_python,
                "--no-python-downloads",
                "--offline",
                "--no-cache",
                "--link-mode",
                "copy",
                "--no-index",
                "--require-hashes",
                "--find-links",
                root / "wheelhouse",
                "--requirement",
                root / "requirements.lock",
            ]
        )
        run(
            [
                uv,
                "pip",
                "install",
                "--python",
                environment_python,
                "--no-python-downloads",
                "--offline",
                "--no-cache",
                "--link-mode",
                "copy",
                "--no-index",
                "--find-links",
                root / "wheelhouse",
                "beamcontrol",
            ]
        )

        run([environment_python, "-c", "import beamcontrol"])
        run(
            [
                environment_python,
                "-c",
                (
                    "from beamcontrol.config import BeamControlConfig; "
                    "from beamcontrol.monitor import BeamControlMonitor; "
                    "from beamcontrol.web.server import STATIC_DIR, TEMPLATE_DIR, create_app; "
                    "assert (STATIC_DIR / 'styles.css').is_file(); "
                    "assert (STATIC_DIR / 'dashboard.js').is_file(); "
                    "assert (TEMPLATE_DIR / 'index.html').is_file(); "
                    "assert create_app(BeamControlMonitor(BeamControlConfig())).title "
                    "== 'BeamControl'"
                ),
            ]
        )
        run([environment / "bin/beamctl", "--help"])
        run([environment / "bin/beamd", "--help"])

        wheels = sorted((root / "wheelhouse").glob("*.whl"))
        if not wheels:
            raise RuntimeError("bundle wheelhouse contains no wheels")

    print(f"deployment bundle smoke test passed: {bundle}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    smoke_test(arguments.bundle.resolve())


if __name__ == "__main__":
    main()
