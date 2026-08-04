"""BeamControlClient unit tests using a scripted fake transport (no hardware)."""

from __future__ import annotations

import pytest

from beamcontrol import protocol as P
from beamcontrol.client import BeamControlClient, BeamControlError, BeamControlProtocolError

from .fake_transport import FakeTransport

PHASES = [128, 64, 32, 16]
ATTENUATIONS = [0, 8, 12, 23]


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


def _status(
    node: int,
    seq: int = 1,
    *,
    version: tuple[int, int, int] = P.PROTOCOL_VERSION,
    health: int = 0,
    rx_dropped: int = 0,
    tx_dropped: int = 0,
    invalid: int = 0,
) -> _Reply:
    major, minor, patch = version
    return _Reply(
        P.build_id(P.STATUS, 0, node, seq),
        bytes([major, minor, patch, node, health, rx_dropped, tx_dropped, invalid]),
    )


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
        client.set_phase(3, PHASES)
    sent = transport.sent
    assert len(sent) == 3  # 1 initial + 2 retries
    ids = {m.arbitration_id for m in sent}
    datas = {bytes(m.data) for m in sent}
    assert len(ids) == 1 and len(datas) == 1  # byte-for-byte identical retries


def test_ack_matching():
    client, _, _ = _make([_ack(3, 42, P.SET_PHASE)])
    client._seq = 41  # force next seq to 42
    out = client.set_phase(3, PHASES)
    assert out == bytes([P.SET_PHASE, P.RES_OK])


def test_wrong_node_rejected():
    """A reply from the wrong node is ignored and the client keeps waiting."""
    wrong = _ack(9, 0, P.SET_PHASE)  # wrong node
    right = _ack(3, 42, P.SET_PHASE)
    client, _, _ = _make([wrong, right])
    client._seq = 41
    assert client.set_phase(3, PHASES) == bytes([P.SET_PHASE, P.RES_OK])


def test_error_raises():
    client, _, _ = _make([_error(3, 42, P.SET_PHASE, P.RES_BAD_VALUE)])
    client._seq = 41
    with pytest.raises(BeamControlError) as exc:
        client.set_phase(3, PHASES)
    assert exc.value.result == P.RES_BAD_VALUE


def test_timeout_is_unknown_state():
    client, _, _ = _make([None], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.set_vga(3, ATTENUATIONS)
    assert "final state unknown" in str(exc.value)


def test_sequence_ffff_is_normal():
    client, _, transport = _make([_ack(3, 0xFFFF, P.ENTER_SAFE)], retries=0)
    client._seq = 0xFFFE
    client.enter_safe(3, 0)
    assert P.parse_id(transport.sent[0].arbitration_id)["sequence"] == 0xFFFF


def test_bulk_payload_validation():
    client, _, _ = _make([None], retries=0)
    with pytest.raises(ValueError):
        client.set_phase(3, [1, 2, 3])
    with pytest.raises(ValueError):
        client.set_phase(3, [1, 2, 3, 256])
    with pytest.raises(ValueError):
        client.set_vga(3, [0, 8, 24, 23])
    with pytest.raises(ValueError):
        client.set_combined(3, PHASES, [0, 1, 2])


@pytest.mark.parametrize(
    ("method", "args", "command_type", "payload"),
    [
        ("set_phase_channel", (2, 128), P.SET_PHASE, bytes([128, 2])),
        ("set_vga_channel", (1, 8), P.SET_VGA, bytes([8, 1])),
        ("set_combined_channel", (3, 64, 12), P.SET_COMBINED, bytes([64, 3, 12])),
    ],
)
def test_individual_methods_send_exact_payload(method, args, command_type, payload):
    client, _, transport = _make([_ack(3, 1, command_type)], retries=0)
    result = getattr(client, method)(3, *args)
    assert result == bytes([command_type, P.RES_OK])
    assert bytes(transport.sent[0].data) == payload


def test_individual_method_validation():
    client, _, _ = _make([], retries=0)
    with pytest.raises(ValueError):
        client.set_phase_channel(3, 4, 128)
    with pytest.raises(ValueError):
        client.set_phase_channel(3, 2, 256)
    with pytest.raises(ValueError):
        client.set_vga_channel(3, 2, 24)
    with pytest.raises(ValueError):
        client.set_combined_channel(3, 2, 64, 24)


def test_discovery_returns_current_status():
    client, _, _ = _make([_status(3, health=0x12, rx_dropped=2, tx_dropped=3, invalid=7)])
    status = client.discover(3)
    assert status.version == P.PROTOCOL_VERSION
    assert status.node_id == 3
    assert status.health_flags == 0x12
    assert status.rx_dropped == 2
    assert status.tx_dropped == 3
    assert status.invalid_commands == 7


def test_discovery_sends_ping():
    client, _, transport = _make([_status(3)])
    client.discover(3)
    assert len(transport.sent) == 1
    f = P.parse_id(transport.sent[0].arbitration_id)
    assert f["type"] == P.PING
    assert f["sequence"] == 1
    assert f["dest"] == 3
    assert bytes(transport.sent[0].data) == b""


# --- malformed / mismatched response handling ------------------------------


def test_ack_wrong_command_type_raises():
    # byte0 must equal the requested command type
    wrong = _Reply(P.build_id(P.ACK, 0, 3, 42), bytes([P.SET_VGA, P.RES_OK]))
    client, _, _ = _make([wrong])
    client._seq = 41
    with pytest.raises(BeamControlProtocolError):
        client.set_phase(3, PHASES)


def test_ack_bad_dlc_raises():
    for data in (bytes([P.SET_PHASE]), bytes([P.SET_PHASE, P.RES_OK, 0x00])):
        wrong = _Reply(P.build_id(P.ACK, 0, 3, 42), data)
        client, _, _ = _make([wrong])
        client._seq = 41
        with pytest.raises(BeamControlProtocolError):
            client.set_phase(3, PHASES)


def test_error_wrong_command_type_raises():
    wrong = _Reply(P.build_id(P.ERROR, 0, 3, 42), bytes([P.SET_VGA, P.RES_BAD_VALUE]))
    client, _, _ = _make([wrong])
    client._seq = 41
    with pytest.raises(BeamControlProtocolError):
        client.set_phase(3, PHASES)


def test_discovery_wrong_sequence_ignored():
    client, _, _ = _make([_status(3, seq=7)], retries=0)
    with pytest.raises(BeamControlError) as exc:
        client.discover(3)
    assert "no STATUS" in str(exc.value)


def test_discovery_short_status_raises():
    short = _Reply(P.build_id(P.STATUS, 0, 3, 1), bytes([2, 1, 0]))
    client, _, _ = _make([short], retries=0)
    with pytest.raises(BeamControlProtocolError):
        client.discover(3)


def test_discovery_mismatched_node_id_ignored():
    bad = _Reply(
        P.build_id(P.STATUS, 0, 3, 1),
        bytes([2, 1, 0, 7, 0, 0, 0, 0]),
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
            client.set_phase(bad, PHASES)
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
    out = client.set_phase(3, PHASES)
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
        client.set_phase(3, PHASES)
    assert exc.value.result == P.RES_SEQUENCE_REUSE
