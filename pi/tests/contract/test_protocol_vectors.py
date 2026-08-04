"""Contract test: Python and C must agree with protocol/v2.1-vectors.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from beamcontrol import protocol as P

VECTORS = Path(__file__).resolve().parents[3] / "protocol" / "v2.1-vectors.toml"
DATA = tomllib.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", DATA["id_vectors"], ids=lambda v: v["name"])
def test_id_vector_encodes(v):
    can_id = P.build_id(v["type"], v["destination"], v["source"], v["sequence"])
    assert can_id == v["extended_id"]


@pytest.mark.parametrize("v", DATA["id_vectors"], ids=lambda v: v["name"])
def test_id_vector_decodes(v):
    f = P.parse_id(v["extended_id"])
    assert f["type"] == v["type"]
    assert f["dest"] == v["destination"]
    assert f["source"] == v["source"]
    assert f["sequence"] == v["sequence"]


def _validate_command(msg_type: int, payload: list[int]) -> None:
    if msg_type == P.SET_PHASE:
        if len(payload) == 2:
            P.validate_phase_state(payload[0])
            P.validate_channel(payload[1])
        elif len(payload) == 4:
            P.validate_phase_states(payload)
        else:
            raise ValueError("SET_PHASE requires DLC 2 or 4")
    elif msg_type == P.SET_VGA:
        if len(payload) == 2:
            P.validate_attenuation(payload[0])
            P.validate_channel(payload[1])
        elif len(payload) == 4:
            P.validate_attenuations(payload)
        else:
            raise ValueError("SET_VGA requires DLC 2 or 4")
    elif msg_type == P.SET_COMBINED:
        if len(payload) == 3:
            P.validate_phase_state(payload[0])
            P.validate_channel(payload[1])
            P.validate_attenuation(payload[2])
        elif len(payload) == 8:
            P.validate_phase_states(payload[:4])
            P.validate_attenuations(payload[4:])
        else:
            raise ValueError("SET_COMBINED requires DLC 3 or 8")
    elif msg_type == P.ENTER_SAFE:
        if len(payload) != 1:
            raise ValueError("ENTER_SAFE requires DLC 1")
        P.validate_channel(payload[0])


@pytest.mark.parametrize("v", DATA["commands"], ids=lambda v: v["name"])
def test_command_validation(v):
    payload = list(v["data"])
    if v["valid"]:
        _validate_command(v["type"], payload)
        return

    with pytest.raises(ValueError):
        _validate_command(v["type"], payload)
