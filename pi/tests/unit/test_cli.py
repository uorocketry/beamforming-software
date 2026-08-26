from __future__ import annotations

import pytest

from beamcontrol import cli


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def close(self) -> None:
        pass

    def set_phase(self, node, states):
        self.calls.append(("set_phase", node, states))
        return b"\x02\x00"

    def set_phase_channel(self, node, channel, state):
        self.calls.append(("set_phase_channel", node, channel, state))
        return b"\x02\x00"

    def set_vga(self, node, attenuations):
        self.calls.append(("set_vga", node, attenuations))
        return b"\x03\x00"

    def set_vga_channel(self, node, channel, attenuation):
        self.calls.append(("set_vga_channel", node, channel, attenuation))
        return b"\x03\x00"

    def set_combined(self, node, states, attenuations):
        self.calls.append(("set_combined", node, states, attenuations))
        return b"\x01\x00"

    def set_combined_channel(self, node, channel, state, attenuation):
        self.calls.append(("set_combined_channel", node, channel, state, attenuation))
        return b"\x01\x00"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["set-phase", "1", "--state", "128", "--channel", "2"], ("set_phase_channel", 1, 2, 128)),
        (["set-phase", "1", "--states", "1", "2", "3", "4"], ("set_phase", 1, [1, 2, 3, 4])),
        (["set-vga", "1", "--attenuation", "8", "--channel", "1"], ("set_vga_channel", 1, 1, 8)),
        (["set-vga", "1", "--attenuations", "1", "2", "3", "4"], ("set_vga", 1, [1, 2, 3, 4])),
        (
            ["set-combined", "1", "--state", "64", "--attenuation", "12", "--channel", "3"],
            ("set_combined_channel", 1, 3, 64, 12),
        ),
        (
            [
                "set-combined",
                "1",
                "--states",
                "1",
                "2",
                "3",
                "4",
                "--attenuations",
                "5",
                "6",
                "7",
                "8",
            ],
            ("set_combined", 1, [1, 2, 3, 4], [5, 6, 7, 8]),
        ),
    ],
)
def test_rf_cli_modes(monkeypatch, argv, expected):
    client = FakeClient()
    monkeypatch.setattr(cli, "_client", lambda _args: client)
    assert cli.main(argv) == 0
    assert client.calls == [expected]


@pytest.mark.parametrize(
    "argv",
    [
        ["set-phase", "1", "--state", "128"],
        ["set-phase", "1", "--states", "1", "2", "3", "4", "--channel", "1"],
        ["set-combined", "1", "--state", "64", "--attenuations", "1", "2", "3", "4"],
    ],
)
def test_rf_cli_rejects_mixed_or_incomplete_modes(monkeypatch, argv):
    monkeypatch.setattr(
        cli, "_client", lambda _args: pytest.fail("client opened before validation")
    )
    with pytest.raises(SystemExit):
        cli.main(argv)
