#!/usr/bin/env python3
"""Install the pinned uv binary into the repository-local .tools directory."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import tarfile
from pathlib import Path

from script_support import (
    REPO_ROOT,
    ToolError,
    command_output,
    download,
    load_lock,
    main_guard,
    safe_extract,
    temporary_directory,
    verify_sha256,
)


def main() -> None:
    lock = load_lock(REPO_ROOT / "tools/uv.lock")
    version = lock["UV_VERSION"]
    architecture = platform.machine().lower()
    architecture_keys = {
        "x86_64": "UV_SHA256_X86_64",
        "amd64": "UV_SHA256_X86_64",
        "aarch64": "UV_SHA256_AARCH64",
        "arm64": "UV_SHA256_AARCH64",
    }
    try:
        sha_key = architecture_keys[architecture]
    except KeyError as error:
        raise ToolError(f"unsupported architecture: {architecture}") from error

    archive_arch = "x86_64" if sha_key.endswith("X86_64") else "aarch64"
    uv_binary = REPO_ROOT / ".tools/bin/uv"
    if uv_binary.is_file() and os.access(uv_binary, os.X_OK):
        installed = command_output([uv_binary, "--version"])
        if version in installed:
            print(f"uv already installed: {installed}")
            return
        print(f"Replacing unexpected repository-local uv: {installed}")

    tarball_name = f"uv-{archive_arch}-unknown-linux-gnu.tar.gz"
    url = f"https://github.com/astral-sh/uv/releases/download/{version}/{tarball_name}"

    with temporary_directory(prefix="beamcontrol-uv-") as temporary_name:
        temporary = Path(temporary_name)
        archive = temporary / tarball_name
        extracted = temporary / "extracted"
        print(f"Downloading uv {version} ({archive_arch}) ...")
        download(url, archive)
        verify_sha256(archive, lock[sha_key])

        member_name = f"uv-{archive_arch}-unknown-linux-gnu/uv"
        with tarfile.open(archive) as tar:
            try:
                member = tar.getmember(member_name)
            except KeyError as error:
                raise ToolError(f"uv archive does not contain {member_name}") from error
            safe_extract(archive, extracted, members=[member])

        source = extracted / member_name
        uv_binary.parent.mkdir(parents=True, exist_ok=True)
        staged = uv_binary.with_name(".uv.new")
        shutil.copy2(source, staged)
        staged.chmod(staged.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        staged.replace(uv_binary)

    print(f"uv installed: {command_output([uv_binary, '--version'])}")


if __name__ == "__main__":
    main_guard(main)
