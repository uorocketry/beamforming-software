"""Smoke-test an extracted BeamControl offline Pi bundle without system changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from script_support import safe_extract


def run(command: list[str | Path]) -> None:
    subprocess.run([str(part) for part in command], check=True)


def find_bundle_root(extracted: Path) -> Path:
    roots = [path for path in extracted.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"expected one bundle root, found {len(roots)}")
    return roots[0]


def smoke_test(bundle: Path) -> None:
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(
            f"bundle smoke test requires Python 3.11, found {sys.version_info.major}.{sys.version_info.minor}"
        )

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

        environment = temporary / "venv"
        run([sys.executable, "-m", "venv", environment])
        pip = environment / "bin/pip"
        run(
            [
                pip,
                "install",
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
                pip,
                "install",
                "--no-index",
                "--find-links",
                root / "wheelhouse",
                "beamcontrol",
            ]
        )

        run([environment / "bin/python", "-c", "import beamcontrol"])
        run(
            [
                environment / "bin/python",
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
