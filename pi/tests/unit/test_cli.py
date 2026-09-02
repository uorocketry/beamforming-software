from __future__ import annotations

import pytest

from beamcontrol import cli


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def close(self) -> None:
        pass

    def set_phase(self, node, state):
        self.calls.append(("set_phase", node, state))
        return b"\x02\x00"

    def set_vga(self, node, attenuation):
        self.calls.append(("set_vga", node, attenuation))
        return b"\x03\x00"

    def set_combined(self, node, state, attenuation):
        self.calls.append(("set_combined", node, state, attenuation))
        return b"\x01\x00"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["set-phase", "1", "--state", "128"], ("set_phase", 1, 128)),
        (["set-vga", "1", "--attenuation", "8"], ("set_vga", 1, 8)),
        (
            ["set-combined", "1", "--state", "64", "--attenuation", "12"],
            ("set_combined", 1, 64, 12),
        ),
    ],
)
def test_rf_cli_commands(monkeypatch, argv, expected):
    client = FakeClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)
    assert cli.main(argv) == 0
    assert client.calls == [expected]


@pytest.mark.parametrize(
    "argv",
    [
        ["set-phase", "1"],
        ["set-vga", "1"],
        ["set-combined", "1", "--state", "64"],
    ],
)
def test_rf_cli_requires_values(monkeypatch, argv):
    monkeypatch.setattr(cli, "_client", lambda _args: pytest.fail("client opened"))
    with pytest.raises(SystemExit):
        cli.main(argv)
