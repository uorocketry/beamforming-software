#!/usr/bin/env python3
"""Fetch the pinned ARM GNU toolchain into the repository-local .tools directory."""

from __future__ import annotations

import os
import platform
import shutil
import tempfile
from pathlib import Path

from script_support import (
    REPO_ROOT,
    ToolError,
    command_output,
    download,
    load_lock,
    main_guard,
    replace_tree,
    safe_extract,
    verify_sha256,
)


def compiler_version(compiler: Path) -> str:
    return command_output([compiler, "--version"]).splitlines()[0]


def main() -> None:
    lock = load_lock(REPO_ROOT / "stm32/third_party/arm-toolchain.lock")
    version = lock["ARM_VERSION"]
    destination = REPO_ROOT / ".tools/arm-gnu-toolchain"
    compiler = destination / "bin/arm-none-eabi-gcc"

    if compiler.is_file() and os.access(compiler, os.X_OK):
        installed = compiler_version(compiler)
        if version.lower() in installed.lower():
            print(f"ARM toolchain already present: {installed}")
            return
        print(f"Replacing unexpected repository-local ARM toolchain: {installed}")

    if os.environ.get("USE_SYSTEM_ARM_TOOLCHAIN", "0") == "1":
        resolved = shutil.which("arm-none-eabi-gcc")
        if resolved is None:
            raise ToolError(
                "USE_SYSTEM_ARM_TOOLCHAIN=1 but arm-none-eabi-gcc is not in PATH"
            )
        print(f"Using system arm-none-eabi-gcc: {compiler_version(Path(resolved))}")
        return

    machine = platform.machine().lower()
    architecture_keys = {
        "x86_64": ("x86_64", "ARM_SHA256_X86_64"),
        "amd64": ("x86_64", "ARM_SHA256_X86_64"),
        "aarch64": ("aarch64", "ARM_SHA256_AARCH64"),
        "arm64": ("aarch64", "ARM_SHA256_AARCH64"),
    }
    try:
        archive_arch, sha_key = architecture_keys[machine]
    except KeyError as error:
        raise ToolError(f"unsupported architecture: {machine}") from error

    tarball_name = f"arm-gnu-toolchain-{version}-{archive_arch}-arm-none-eabi.tar.xz"
    url = f"{lock['ARM_URL']}/{version}/binrel/{tarball_name}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".beamcontrol-arm-", dir=destination.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        archive = temporary / tarball_name
        extracted = temporary / "extracted"
        print(f"Downloading ARM GNU toolchain {version} ({archive_arch}) ...")
        download(url, archive)
        verify_sha256(archive, lock[sha_key])
        safe_extract(archive, extracted)

        roots = [path for path in extracted.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ToolError(
                f"unexpected ARM archive layout: found {len(roots)} top-level directories"
            )
        staged = destination.with_name(f".{destination.name}.new")
        if staged.exists():
            shutil.rmtree(staged)
        roots[0].replace(staged)
        staged_compiler = staged / "bin/arm-none-eabi-gcc"
        if not staged_compiler.is_file():
            raise ToolError("downloaded ARM toolchain is missing bin/arm-none-eabi-gcc")
        installed = compiler_version(staged_compiler)
        if version.lower() not in installed.lower():
            raise ToolError(f"downloaded ARM toolchain version mismatch: {installed}")
        replace_tree(staged, destination)

    print(f"ARM toolchain installed at {destination}")
    print(compiler_version(compiler))


if __name__ == "__main__":
    main_guard(main)
