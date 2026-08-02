from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from build_pi_bundle import create_bundle
from script_support import ToolError, load_lock, replace_tree, safe_extract


def test_load_lock_parses_comments_and_quotes(tmp_path: Path) -> None:
    lock = tmp_path / "example.lock"
    lock.write_text(
        "# comment\nPLAIN=value\nDOUBLE=\"two words\"\nSINGLE='three words'\n",
        encoding="utf-8",
    )

    assert load_lock(lock) == {
        "PLAIN": "value",
        "DOUBLE": "two words",
        "SINGLE": "three words",
    }


def test_safe_extract_extracts_regular_file(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar.gz"
    payload = b"hello\n"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("folder/file.txt")
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))

    destination = tmp_path / "out"
    safe_extract(archive, destination)

    assert (destination / "folder/file.txt").read_bytes() == payload


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar"
    payload = b"escape"
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))

    destination = tmp_path / "out"
    with pytest.raises(ToolError, match="unsafe archive member path"):
        safe_extract(archive, destination)

    assert not (tmp_path / "escape.txt").exists()


def test_replace_tree_replaces_existing_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "new.txt").write_text("new", encoding="utf-8")
    (destination / "old.txt").write_text("old", encoding="utf-8")

    replace_tree(source, destination)

    assert not source.exists()
    assert not (destination / "old.txt").exists()
    assert (destination / "new.txt").read_text(encoding="utf-8") == "new"


def test_create_bundle_produces_extractable_tar_gz(tmp_path: Path) -> None:
    stage = tmp_path / "beamcontrol-pi-test"
    stage.mkdir()
    (stage / "VERSION").write_text("test\n", encoding="utf-8")
    bundle = tmp_path / "beamcontrol-pi-test.tar.gz"

    create_bundle(stage, bundle)

    destination = tmp_path / "extracted"
    safe_extract(bundle, destination)
    assert (destination / stage.name / "VERSION").read_text(
        encoding="utf-8"
    ) == "test\n"
