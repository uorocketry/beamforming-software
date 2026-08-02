#!/usr/bin/env python3
"""Fetch the pinned libopencm3 source archive into stm32/.deps."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from script_support import (
    REPO_ROOT,
    ToolError,
    download,
    load_lock,
    main_guard,
    replace_tree,
    safe_extract,
    verify_sha256,
)


def main() -> None:
    lock = load_lock(REPO_ROOT / "stm32/third_party/libopencm3.lock")
    commit = lock["LIBOPENCM3_COMMIT"]
    destination = REPO_ROOT / "stm32/.deps/libopencm3"
    marker = destination / ".uorocketry-commit"
    required_file = destination / "Makefile"

    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == commit:
        if required_file.is_file():
            print(f"libopencm3 {commit} already present at {destination}")
            return
        print("Refetching incomplete repository-local libopencm3 directory")

    url = f"https://github.com/libopencm3/libopencm3/archive/{commit}.tar.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".beamcontrol-libopencm3-", dir=destination.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        archive = temporary / "libopencm3.tar.gz"
        extracted = temporary / "extracted"
        print(f"Downloading libopencm3 @ {commit} ...")
        download(url, archive)
        verify_sha256(archive, lock["LIBOPENCM3_SHA256"])
        safe_extract(archive, extracted)

        roots = [path for path in extracted.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ToolError(
                f"unexpected libopencm3 archive layout: found {len(roots)} top-level directories"
            )
        staged = destination.with_name(f".{destination.name}.new")
        if staged.exists():
            shutil.rmtree(staged)
        roots[0].replace(staged)
        if not (staged / "Makefile").is_file():
            raise ToolError("downloaded libopencm3 source is missing its Makefile")
        (staged / ".uorocketry-commit").write_text(f"{commit}\n", encoding="utf-8")
        replace_tree(staged, destination)

    print(f"libopencm3 fetched to {destination}")


if __name__ == "__main__":
    main_guard(main)
