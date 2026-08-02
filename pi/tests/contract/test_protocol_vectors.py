"""Contract test: the Python protocol implementation must agree with the
shared protocol vectors (protocol/v1.1-vectors.toml). The C firmware consumes
the same vectors via the generated header, so this catches Python<->C drift.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from beamcontrol import protocol as P

VECTORS = Path(__file__).resolve().parents[3] / "protocol" / "v1.1-vectors.toml"
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


@pytest.mark.parametrize("v", DATA["commands"], ids=lambda v: v["name"])
def test_command_validation(v):
    payload = list(v["data"])
    if v["valid"]:
        # Valid command: payload-specific validation must accept it.
        if v["type"] == P.SET_PHASE:
            P.validate_payload(payload[1], phase_state=payload[0])
        elif v["type"] == P.SET_VGA:
            P.validate_payload(0, atten_db=payload[0])
        elif v["type"] == P.ENTER_SAFE:
            P.validate_payload(payload[0])
    else:
        # Invalid command: expect validation to reject channel/attenuation.
        # Reserved-byte rejection (result 6) is a decode-layer check, not
        # covered by validate_payload here.
        if v["result"] in (2,):  # INVALID_PAYLOAD
            if v["type"] == P.SET_PHASE:
                with pytest.raises(ValueError):
                    P.validate_payload(payload[1], phase_state=payload[0])
            elif v["type"] == P.SET_VGA:
                with pytest.raises(ValueError):
                    P.validate_payload(0, atten_db=payload[0])
