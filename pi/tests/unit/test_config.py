"""BeamControlConfig validation tests."""

from __future__ import annotations

import pytest

from beamcontrol.config import BeamControlConfig


def test_valid_config():
    c = BeamControlConfig(
        channel="can0",
        source_node=0,
        poll_interval_s=0.5,
        can_timeout_s=0.1,
        can_retries=4,
        nodes=[1, 2, 3],
        web_host="127.0.0.1",
        web_port=9000,
    )
    assert c.channel == "can0"
    assert c.can_timeout_s == 0.1
    assert c.can_retries == 4
    assert c.web_host == "127.0.0.1"
    assert c.web_port == 9000


def test_rejects_nonzero_source_node():
    with pytest.raises(ValueError):
        BeamControlConfig(source_node=5)


def test_rejects_nonpositive_poll_interval():
    with pytest.raises(ValueError):
        BeamControlConfig(poll_interval_s=0)
    with pytest.raises(ValueError):
        BeamControlConfig(poll_interval_s=-1)


def test_rejects_invalid_can_transaction_settings():
    with pytest.raises(ValueError):
        BeamControlConfig(can_timeout_s=0)
    with pytest.raises(ValueError):
        BeamControlConfig(can_retries=-1)


def test_rejects_out_of_range_node():
    with pytest.raises(ValueError):
        BeamControlConfig(nodes=[0])  # controller is not a receiver
    with pytest.raises(ValueError):
        BeamControlConfig(nodes=[31])  # broadcast is not a receiver
    with pytest.raises(ValueError):
        BeamControlConfig(nodes=[32])


def test_rejects_duplicate_nodes():
    with pytest.raises(ValueError):
        BeamControlConfig(nodes=[1, 1, 2])


def test_rejects_empty_channel():
    with pytest.raises(ValueError):
        BeamControlConfig(channel="   ")


def test_rejects_invalid_web_endpoint():
    with pytest.raises(ValueError):
        BeamControlConfig(web_host="   ")
    with pytest.raises(ValueError):
        BeamControlConfig(web_port=0)
    with pytest.raises(ValueError):
        BeamControlConfig(web_port=65536)
