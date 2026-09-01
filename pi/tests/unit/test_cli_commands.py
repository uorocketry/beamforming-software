"""Command-level coverage for every beamctl operation."""

from __future__ import annotations

import pytest

from beamcontrol import cli
from beamcontrol.client import BeamControlError, NodeStatus


class RecordingClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.closed = False
        self.fail = fail

    def close(self) -> None:
        self.closed = True

    def discover(self, node: int) -> NodeStatus:
        self.calls.append(("discover", node))
        if self.fail:
            raise BeamControlError("receiver unavailable")
        return NodeStatus(2, 1, 0, node, 0, 0, 0, 0)

    def enter_safe(self, node: int, channel: int) -> bytes:
        self.calls.append(("enter_safe", node, channel))
        if self.fail:
            raise BeamControlError("receiver unavailable")
        return b"\x04\x00"


def test_discover_scans_every_node_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["discover"]) == 0

    assert client.calls == [("discover", node) for node in range(1, 31)]
    assert client.closed
    assert "node  1: v2.1.0" in capsys.readouterr().out


def test_ping_dispatches_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["ping", "7"]) == 0

    assert client.calls == [("discover", 7)]
    assert client.closed
    assert "STATUS:" in capsys.readouterr().out


def test_enter_safe_dispatches_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["enter-safe", "4", "--channel", "2"]) == 0

    assert client.calls == [("enter_safe", 4, 2)]
    assert client.closed
    assert capsys.readouterr().out.strip() == "ACK 0400"


def test_command_error_returns_one_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient(fail=True)
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["ping", "7"]) == 1

    assert client.closed
    assert "error: receiver unavailable" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["discover"],
        ["ping", "1"],
        ["set-phase", "1", "--state", "128", "--channel", "2"],
        ["set-phase", "1", "--states", "1", "2", "3", "4"],
        ["set-vga", "1", "--attenuation", "8", "--channel", "2"],
        ["set-vga", "1", "--attenuations", "8", "9", "10", "11"],
        [
            "set-combined",
            "1",
            "--state",
            "128",
            "--attenuation",
            "8",
            "--channel",
            "2",
        ],
        [
            "set-combined",
            "1",
            "--states",
            "1",
            "2",
            "3",
            "4",
            "--attenuations",
            "8",
            "9",
            "10",
            "11",
        ],
        ["enter-safe", "1", "--channel", "2"],
    ],
)
def test_every_command_supports_hardware_free_dry_run(monkeypatch, capsys, argv) -> None:
    monkeypatch.setattr(
        cli,
        "_client",
        lambda _args: pytest.fail("dry run opened SocketCAN"),
    )

    assert cli.main([*argv, "--dry-run"]) == 0

    assert capsys.readouterr().out.startswith(f"DRY RUN {argv[0]}:")
