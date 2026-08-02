#!/usr/bin/env python3
"""Shared standard-library helpers for repository tooling."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ToolError(RuntimeError):
    """A user-facing tooling failure."""


def load_lock(path: Path) -> dict[str, str]:
    """Load the simple KEY=VALUE lock-file format used by this repository."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ToolError(f"invalid lock entry at {path}:{line_number}: {raw_line}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            raise ToolError(f"invalid lock entry at {path}:{line_number}: {raw_line}")
        values[key] = value
    return values


def run(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command with consistent text-mode behavior."""
    argv = [os.fspath(item) for item in command]
    return subprocess.run(
        argv,
        cwd=cwd,
        env=None if env is None else dict(env),
        check=check,
        text=True,
        capture_output=capture_output,
    )


def command_output(
    command: Sequence[str | os.PathLike[str]], *, cwd: Path | None = None
) -> str:
    """Return stripped stdout for a successful command."""
    return run(command, cwd=cwd, capture_output=True).stdout.strip()


def require_command(name: str) -> Path:
    """Return an executable path or raise a user-facing error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise ToolError(f"required command not found: {name}")
    return Path(resolved)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ToolError(
            f"SHA256 mismatch for {path.name}: expected {expected}, got {actual}"
        )


def download(url: str, destination: Path, *, attempts: int = 3) -> None:
    """Download a URL with bounded retries and an atomic final rename."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.part")
    partial.unlink(missing_ok=True)

    headers = {"User-Agent": "uorocketry-beamcontrol-tooling/1"}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                partial.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            partial.replace(destination)
            return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(attempt)
    raise ToolError(f"download failed after {attempts} attempts: {url}: {last_error}")


def safe_extract(
    archive: Path,
    destination: Path,
    *,
    members: Iterable[tarfile.TarInfo] | None = None,
) -> None:
    """Extract a tar archive while rejecting traversal and special-file entries."""
    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    with tarfile.open(archive) as tar:
        selected = list(tar.getmembers() if members is None else members)
        for member in selected:
            if member.isdev() or member.isfifo():
                raise ToolError(f"unsafe archive member type: {member.name}")
            target = (destination / member.name).resolve()
            if (
                target != destination_resolved
                and destination_resolved not in target.parents
            ):
                raise ToolError(f"unsafe archive member path: {member.name}")
            if member.issym():
                link_target = (target.parent / member.linkname).resolve()
                if (
                    link_target != destination_resolved
                    and destination_resolved not in link_target.parents
                ):
                    raise ToolError(
                        f"unsafe archive link target: {member.name} -> {member.linkname}"
                    )
            if member.islnk():
                link_target = (destination / member.linkname).resolve()
                if (
                    link_target != destination_resolved
                    and destination_resolved not in link_target.parents
                ):
                    raise ToolError(
                        f"unsafe archive link target: {member.name} -> {member.linkname}"
                    )
        tar.extractall(destination, members=selected)


def replace_tree(source: Path, destination: Path) -> None:
    """Replace a repository-local directory after a complete staged extraction."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f".{destination.name}.old")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.replace(backup)
    try:
        source.replace(destination)
    except Exception:
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def temporary_directory(*, prefix: str) -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix=prefix)


def main_guard(function: Callable[[], None]) -> None:
    """Run a script entry point with concise, predictable error reporting."""
    try:
        function()
    except ToolError as error:
        raise SystemExit(f"error: {error}") from error
    except subprocess.CalledProcessError as error:
        command = " ".join(str(part) for part in error.cmd)
        raise SystemExit(
            f"error: command failed ({error.returncode}): {command}"
        ) from error
