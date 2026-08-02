#!/usr/bin/env python3
"""Run extended host, static-analysis, and firmware verification."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SANITIZER_FLAGS = (
    "-std=c17 -Wall -Wextra -Werror -pedantic -O1 -g "
    "-fsanitize=address,undefined -fno-omit-frame-pointer"
)


def run(command: list[str | os.PathLike[str]], *, cwd: Path = REPO_ROOT) -> None:
    subprocess.run([os.fspath(part) for part in command], cwd=cwd, check=True)


def output(command: list[str], *, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def main() -> None:
    revision = output(["git", "rev-parse", "HEAD"])
    node_id = os.environ.get("CAN_NODE_ID", "1")
    opencm3 = REPO_ROOT / "stm32/.deps/libopencm3"
    compiler_prefix = REPO_ROOT / ".tools/arm-gnu-toolchain/bin"

    run(["make", "-C", "stm32/tests", "clean", "test"])
    run(["make", "-C", "stm32/tests", "clean", "test", f"CFLAGS={SANITIZER_FLAGS}"])
    run(["python3", "stm32/tests/test_can_smoke_tool.py"])
    run(
        [
            "cppcheck",
            "--enable=warning,style,performance,portability",
            "--error-exitcode=1",
            "--std=c17",
            "--suppress=missingIncludeSystem",
            "--suppress=unusedFunction",
            "-DSTM32F0",
            "-DSTM32F072R8T6",
            f"-DBEAMFORMER_NODE_ID={node_id}",
            "-Istm32/app/include",
            f"-I{opencm3 / 'include'}",
            "stm32/app/src",
        ]
    )
    run(["make", "libopencm3-build"])
    run(["make", "-C", "stm32/app", "clean"])
    run(
        [
            "make",
            "-C",
            "stm32/app",
            "all",
            "-j2",
            f"OPENCM3_DIR={opencm3}",
            f"GIT_REVISION={revision}",
            f"CAN_NODE_ID={node_id}",
        ]
    )
    run([compiler_prefix / "arm-none-eabi-size", "stm32/app/build/beamcontrol.elf"])
    run(["git", "diff", "--check"])


if __name__ == "__main__":
    main()
