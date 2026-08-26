from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "pi/deploy"
SPEC = importlib.util.spec_from_file_location(
    "configure_can", DEPLOY_DIR / "configure_can.py"
)
assert SPEC is not None and SPEC.loader is not None
CONFIGURE_CAN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONFIGURE_CAN
SPEC.loader.exec_module(CONFIGURE_CAN)


def test_resolve_interface_returns_single_netdev(tmp_path: Path) -> None:
    net_dir = tmp_path / "spi1.1/net"
    (net_dir / "can7").mkdir(parents=True)

    assert CONFIGURE_CAN.resolve_interface(net_dir, timeout_s=0) == "can7"


def test_resolve_interface_rejects_multiple_netdevs(tmp_path: Path) -> None:
    net_dir = tmp_path / "spi1.1/net"
    (net_dir / "can0").mkdir(parents=True)
    (net_dir / "can1").mkdir()

    with pytest.raises(RuntimeError, match="expected one CAN interface"):
        CONFIGURE_CAN.resolve_interface(net_dir, timeout_s=0)


def test_setup_renames_physical_can0_and_configures_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[list[object], bool]] = []
    monkeypatch.setattr(CONFIGURE_CAN, "resolve_interface", lambda: "can1")
    monkeypatch.setattr(
        CONFIGURE_CAN,
        "run",
        lambda command, check=True: commands.append((command, check)),
    )

    CONFIGURE_CAN.setup()

    assert commands[0] == ([CONFIGURE_CAN.IP, "link", "set", "can1", "down"], False)
    assert commands[1] == (
        [CONFIGURE_CAN.IP, "link", "set", "can1", "name", "beamcan0"],
        True,
    )
    assert commands[-1] == (
        [CONFIGURE_CAN.IP, "link", "set", "beamcan0", "up"],
        True,
    )
    configure = commands[-2][0]
    assert configure[:6] == [CONFIGURE_CAN.IP, "link", "set", "beamcan0", "type", "can"]
    assert "500000" in configure
    assert "0.875" in configure
