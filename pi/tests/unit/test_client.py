"""BeamControlClient unit tests using a scripted fake transport (no hardware)."""

from __future__ import annotations

import pytest

from beamcontrol import protocol as P
from beamcontrol.client import BeamControlClient, BeamControlError, BeamControlProtocolError

from .fake_transport import FakeTransport


class FakeClock:
    def __init__(self) -> None:
        self._t = 100.0

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


class _Reply:
    """Lightweight can.Message stand-in with the fields the client reads."""

    def __init__(self, arbitration_id: int, data: bytes, extended: bool = True):
        self.arbitration_id = arbitration_id
        self.is_extended_id = extended
        self.is_remote_frame = False
        self.data = bytearray(data)


def _ack(node: int, seq: int, cmd_type: int) -> _Reply:
    return _Reply(P.build_id(P.ACK, 0, node, seq), bytes([cmd_type, P.RES_OK]))


def _error(node: int, seq: int, cmd_type: int, result: int) -> _Reply:
    return _Reply(P.build_id(P.ERROR, 0, node, seq), bytes([cmd_type, result]))


def _make(replies, retries=2, timeout=0.02):
    clock = FakeClock()
    transport = FakeTransport(replies, clock=clock, advance=clock.advance)
    client = BeamControlClient(
        transport,
        source_node=0,
        timeout=timeout,
        retries=retries,
        clock=clock,
    )
    return client, clock, transport


def test_exact_retry_reuses_same_message():
    """On timeout, the retry resends the identical arbitration ID + bytes."""
    client, _, transport = _make([None], retries=2)
    with pytest.raises(BeamControlError):
        client.set_phase(3, 128, 2)
    sent = transport.sent
    assert len(sent) == 3  # 1 initial + 2 retries
    ids = {m.arbitration_id for m in sent}
    datas = {bytes(m.data) for m in sent}
    assert len(ids) == 1 and len(datas) == 1  # byte-for-byte identical retries


def test_ack_matching():
    client, _, _ = _make([_ack(3, 42, P.SET_PHASE)])
    client._seq = 41  # force next seq to 42
    out = client.set_phase(3, 128, 2)
    assert out == bytes([P.SET_PHASE, P.RES_OK])


def test_wrong_node_rejected():
    """A reply from the wrong node is ignored and the client keeps waiting."""
    wrong = _ack(9, 0, P.SET_PHASE)  # wrong node
    right = _ack(3, 42, P.SET_PHASE)
    client, _, _ = _make([wrong, right])
    client._seq = 41
    assert client.set_phase(3, 128, 2) == bytes([P.SET_PHASE, P.RES_OK])


def test_error_raises():
    client, _, _ = _make([_error(3, 42, P.SET_PHASE, P.RES_BAD_VALUE)])
    client._seq = 41
    with pytest.raises(BeamControlError) as exc:
        client.set_phase(3, 128, 2)
    assert exc.value.result == P.RES_BAD_VALUE


def test_timeout_is_unknown_state():
    client, _, _ = _make([None], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.set_vga(3, 23)
    assert "final state unknown" in str(exc.value)


def test_sequence_ffff_reserved():
    """The discovery seq 0xFFFF is never used for a config transaction."""
    client, _, transport = _make([None], retries=0)
    with pytest.raises(BeamControlError):
        client.enter_safe(3, 0)
    sent = transport.sent
    assert all(P.parse_id(m.arbitration_id)["sequence"] != P.SEQ_CAPABILITIES for m in sent)


def test_strict_channel_validation():
    client, _, _ = _make([None], retries=0)
    with pytest.raises(ValueError):
        client.set_phase(3, 128, 4)  # channel out of 0..3
    with pytest.raises(ValueError):
        client.set_vga(3, 24)  # attenuation out of 0..23


def test_discovery_legacy_only():
    legacy = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES), bytes([0x01, 3, 0, 0, 23, 0, 0, 0])
    )
    client, _, _ = _make([legacy])
    legacy_data, info = client.discover(3)
    assert info is None
    assert legacy_data[0] == 0x01


def test_discovery_with_protocol_info():
    legacy = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES), bytes([0x01, 3, 0, 0, 23, 0, 0, 0])
    )
    info = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES),
        bytes([P.STATUS_SUBTYPE_PROTOCOL_INFO, 1, 1, 0, 0xFF, 0x00, 3, 0]),
    )
    client, _, _ = _make([legacy, info])
    _, pi = client.discover(3)
    assert pi is not None
    assert pi.major == 1 and pi.minor == 1
    assert pi.node_id == 3
    assert pi.feature_flags == 0xFF


def test_discovery_sends_ping():
    """discover() must transmit the PING@0xFFFF request, not just listen."""
    legacy = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES), bytes([0x01, 3, 0, 0, 23, 0, 0, 0])
    )
    client, _, transport = _make([legacy])
    client.discover(3)
    assert len(transport.sent) == 1
    f = P.parse_id(transport.sent[0].arbitration_id)
    assert f["type"] == P.PING
    assert f["sequence"] == P.SEQ_CAPABILITIES
    assert f["dest"] == 3


# --- malformed / mismatched response handling ------------------------------


def test_ack_wrong_command_type_raises():
    # byte0 must equal the requested command type
    wrong = _Reply(P.build_id(P.ACK, 0, 3, 42), bytes([P.SET_VGA, P.RES_OK]))
    client, _, _ = _make([wrong])
    client._seq = 41
    with pytest.raises(BeamControlProtocolError):
        client.set_phase(3, 128, 2)


def test_ack_bad_dlc_raises():
    for data in (bytes([P.SET_PHASE]), bytes([P.SET_PHASE, P.RES_OK, 0x00])):
        wrong = _Reply(P.build_id(P.ACK, 0, 3, 42), data)
        client, _, _ = _make([wrong])
        client._seq = 41
        with pytest.raises(BeamControlProtocolError):
            client.set_phase(3, 128, 2)


def test_error_wrong_command_type_raises():
    wrong = _Reply(P.build_id(P.ERROR, 0, 3, 42), bytes([P.SET_VGA, P.RES_BAD_VALUE]))
    client, _, _ = _make([wrong])
    client._seq = 41
    with pytest.raises(BeamControlProtocolError):
        client.set_phase(3, 128, 2)


def test_discovery_wrong_sequence_ignored():
    wrong = _Reply(P.build_id(P.STATUS, 0, 3, 7), bytes([0x01, 3, 0, 0, 23, 0, 0, 0]))
    client, _, _ = _make([wrong], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.discover(3)
    assert "no STATUS" in str(exc.value)


def test_discovery_short_protocol_info_raises():
    short = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES),
        bytes([P.STATUS_SUBTYPE_PROTOCOL_INFO, 1, 1]),
    )
    client, _, _ = _make([short], retries=0)
    with pytest.raises(BeamControlProtocolError):
        client.discover(3)


def test_discovery_mismatched_node_id_ignored():
    bad = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES),
        bytes([P.STATUS_SUBTYPE_PROTOCOL_INFO, 1, 1, 0, 0xFF, 0x00, 7, 0]),  # node 7 != 3
    )
    client, _, _ = _make([bad], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.discover(3)
    assert "no STATUS" in str(exc.value)


def test_discovery_nonzero_reserved_ignored():
    bad = _Reply(
        P.build_id(P.STATUS, 0, 3, P.SEQ_CAPABILITIES),
        bytes([P.STATUS_SUBTYPE_PROTOCOL_INFO, 1, 1, 0, 0xFF, 0x00, 3, 1]),  # byte7 != 0
    )
    client, _, _ = _make([bad], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.discover(3)
    assert "no STATUS" in str(exc.value)


# --- production-API safeguards --------------------------------------------------


def test_unicast_destination_enforced():
    client, _, _ = _make([None], retries=0)
    for bad in (0, 31, 32, -1):
        with pytest.raises(ValueError):
            client.enter_safe(bad, 0)
        with pytest.raises(ValueError):
            client.set_phase(bad, 128, 2)
        with pytest.raises(ValueError):
            client.discover(bad)


def test_broadcast_enter_safe_sends_and_does_not_wait():
    client, _, transport = _make([], retries=0)
    client.broadcast_enter_safe(2)
    assert len(transport.sent) == 1
    f = P.parse_id(transport.sent[0].arbitration_id)
    assert f["type"] == P.ENTER_SAFE
    assert f["dest"] == P.BROADCAST_NODE
    assert bytes(transport.sent[0].data) == bytes([2])


def test_broadcast_enter_safe_validates_channel():
    client, _, _ = _make([], retries=0)
    with pytest.raises(ValueError):
        client.broadcast_enter_safe(4)


def test_constructor_validation():
    t = FakeTransport([], clock=lambda: 0.0, advance=lambda s: None)
    with pytest.raises(ValueError):
        BeamControlClient(t, source_node=5)
    with pytest.raises(ValueError):
        BeamControlClient(t, timeout=0)
    with pytest.raises(ValueError):
        BeamControlClient(t, retries=-1)


def test_sequence_reuse_recovers_with_fresh_sequence():
    """A Pi restart can collide seq 1 with the firmware replay cache. The client
    must resequence once (fresh seq) on RES_SEQUENCE_REUSE, not surface the error."""
    reuse = _error(3, 1, P.SET_PHASE, P.RES_SEQUENCE_REUSE)  # seq 1 -> rejected
    ack = _ack(3, 2, P.SET_PHASE)  # seq 2 -> accepted
    client, _, transport = _make([reuse, ack], retries=0)
    client._seq = 0
    out = client.set_phase(3, 128, 2)
    assert out == bytes([P.SET_PHASE, P.RES_OK])
    seqs = [P.parse_id(m.arbitration_id)["sequence"] for m in transport.sent]
    assert seqs == [1, 2]


def test_sequence_reuse_persisting_raises():
    """If a node keeps answering RES_SEQUENCE_REUSE, fail loudly after one resequence."""
    reuse1 = _error(3, 1, P.SET_PHASE, P.RES_SEQUENCE_REUSE)
    reuse2 = _error(3, 2, P.SET_PHASE, P.RES_SEQUENCE_REUSE)
    client, _, _ = _make([reuse1, reuse2], retries=0)
    client._seq = 0
    with pytest.raises(BeamControlError) as exc:
        client.set_phase(3, 128, 2)
    assert exc.value.result == P.RES_SEQUENCE_REUSE
