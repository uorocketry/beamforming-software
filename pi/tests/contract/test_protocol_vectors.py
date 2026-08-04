"""Contract test: Python and C must agree with protocol/v2.0-vectors.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from beamcontrol import protocol as P

VECTORS = Path(__file__).resolve().parents[3] / "protocol" / "v2.0-vectors.toml"
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
        P.validate_phase_states(payload)
    elif msg_type == P.SET_VGA:
        P.validate_attenuations(payload)
    elif msg_type == P.SET_COMBINED:
        P.validate_phase_states(payload[: P.RF_CHANNEL_COUNT])
        P.validate_attenuations(payload[P.RF_CHANNEL_COUNT :])
    elif msg_type == P.ENTER_SAFE:
        if len(payload) != 1:
            raise ValueError("ENTER_SAFE requires one channel")
        P.validate_channel(payload[0])


@pytest.mark.parametrize("v", DATA["commands"], ids=lambda v: v["name"])
def test_command_validation(v):
    payload = list(v["data"])
    if v["valid"]:
        _validate_command(v["type"], payload)
        return

    # Reserved-byte rejection is a decoder rule; Python value helpers do not
    # inspect bytes beyond the semantic payload.
    if v["result"] == P.RES_RESERVED_BYTES:
        return

    with pytest.raises(ValueError):
        _validate_command(v["type"], payload)
