"""Verify and explain the repository-local development setup scope."""

from __future__ import annotations

import os
from pathlib import Path

from script_support import REPO_ROOT, ToolError, main_guard


def _require_repo_local(name: str, raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ToolError(
            f"{name} must stay inside the repository, got: {path}"
        ) from error
    return path


def main() -> None:
    if (
        hasattr(os, "geteuid")
        and os.geteuid() == 0
        and os.environ.get("ALLOW_ROOT_SETUP") != "1"
    ):
        raise ToolError(
            "do not run development setup as root; rerun without sudo "
            "(set ALLOW_ROOT_SETUP=1 only for an intentional root-owned container)"
        )

    locations = {
        "downloaded tools": REPO_ROOT / ".tools",
        "libopencm3": REPO_ROOT / "stm32/.deps/libopencm3",
        "Python environment": _require_repo_local(
            "UV_PROJECT_ENVIRONMENT",
            os.environ.get("UV_PROJECT_ENVIRONMENT", str(REPO_ROOT / "pi/.venv")),
        ),
        "uv cache": _require_repo_local(
            "UV_CACHE_DIR",
            os.environ.get("UV_CACHE_DIR", str(REPO_ROOT / ".tools/uv-cache")),
        ),
        "uv-managed Python": _require_repo_local(
            "UV_PYTHON_INSTALL_DIR",
            os.environ.get(
                "UV_PYTHON_INSTALL_DIR", str(REPO_ROOT / ".tools/uv-python")
            ),
        ),
    }

    print("BeamControl development setup is repository-local:")
    for label, path in locations.items():
        print(f"  - {label}: {path.relative_to(REPO_ROOT)}")
    print("No sudo command or operating-system package manager will be run.")
    print("Use `make distclean` to remove all downloaded development state.")


if __name__ == "__main__":
    main_guard(main)
