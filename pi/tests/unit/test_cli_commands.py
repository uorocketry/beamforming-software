"""Command-level coverage for every beamctl operation."""

from __future__ import annotations

import can
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
        return NodeStatus(3, 0, 0, node, 0, 0, 0, 0)

    def enter_safe(self, node: int) -> bytes:
        self.calls.append(("enter_safe", node))
        if self.fail:
            raise BeamControlError("receiver unavailable")
        return b"\x04\x00"


def test_discover_scans_every_node_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["discover"]) == 0

    assert client.calls == [("discover", node) for node in range(1, 31)]
    assert client.closed
    assert "node  1: v3.0.0" in capsys.readouterr().out


def test_discover_returns_one_when_no_nodes_answer(monkeypatch, capsys) -> None:
    client = RecordingClient(fail=True)
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["discover"]) == 1

    assert client.calls == [("discover", node) for node in range(1, 31)]
    assert client.closed
    assert "error: no receiver boards discovered" in capsys.readouterr().err


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

    assert cli.main(["enter-safe", "4"]) == 0

    assert client.calls == [("enter_safe", 4)]
    assert client.closed
    assert capsys.readouterr().out.strip() == "ACK 0400"


def test_command_error_returns_one_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient(fail=True)
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["ping", "7"]) == 1

    assert client.closed
    assert "error: receiver unavailable" in capsys.readouterr().err


def test_socketcan_error_returns_one_and_closes_client(monkeypatch, capsys) -> None:
    client = RecordingClient()

    def fail_discover(node: int) -> NodeStatus:
        raise can.CanOperationError("No buffer space available")

    client.discover = fail_discover  # type: ignore[method-assign]
    monkeypatch.setattr(cli, "_client", lambda _args: client)

    assert cli.main(["ping", "7"]) == 1

    assert client.closed
    assert "error: No buffer space available" in capsys.readouterr().err


def test_socketcan_open_error_returns_one(monkeypatch, capsys) -> None:
    def fail_client(_args):
        raise can.CanInterfaceNotImplementedError("SocketCAN unavailable")

    monkeypatch.setattr(cli, "_client", fail_client)

    assert cli.main(["ping", "7"]) == 1
    assert "error: SocketCAN unavailable" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["discover"],
        ["ping", "1"],
        ["set-phase", "1", "--state", "128"],
        ["set-vga", "1", "--attenuation", "8"],
        [
            "set-combined",
            "1",
            "--state",
            "128",
            "--attenuation",
            "8",
        ],
        ["enter-safe", "1"],
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


@pytest.mark.parametrize(
    "argv, message",
    [
        (["ping", "0", "--dry-run"], "node must be a receiver node 1..30"),
        (["ping", "31", "--dry-run"], "node must be a receiver node 1..30"),
        (
            ["set-phase", "1", "--state", "256", "--dry-run"],
            "phase_state must be 0..255",
        ),
        (
            ["set-vga", "1", "--attenuation", "24", "--dry-run"],
            "attenuation_db must be 0..23",
        ),
        (["discover", "--source", "1", "--dry-run"], "--source must be controller node 0"),
        (["discover", "--timeout", "0", "--dry-run"], "--timeout must be positive"),
        (["discover", "--retries", "-1", "--dry-run"], "--retries must be non-negative"),
    ],
)
def test_dry_run_rejects_invalid_arguments(capsys, argv, message) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(argv)

    assert error.value.code == 2
    assert message in capsys.readouterr().err
