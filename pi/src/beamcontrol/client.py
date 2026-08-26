"""BeamControlClient: drive BeamControl receiver boards over CAN per protocol v2.1.

Contract (must hold for the firmware's single-entry replay cache to be safe):
- At most one state-changing transaction outstanding per receiver node.
- A retry reuses the exact serialized message.
- A sequence is never reused for a different command while still in flight.
- Responses are matched by destination, source, sequence, and the ACK/ERROR
  payload's command type.
- A timeout means "final state unknown", not "failed".

The transport is injected so tests can use a fake or a virtual bus.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import can

from . import protocol as P
from .transport import CanTransport, SocketCanTransport


class BeamControlError(Exception):
    def __init__(self, message, result=None, command_type=None):
        super().__init__(message)
        self.result = result
        self.command_type = command_type


class BeamControlProtocolError(BeamControlError):
    """A response from the addressed node violated the wire protocol."""


@dataclass(frozen=True, slots=True)
class NodeStatus:
    major: int
    minor: int
    patch: int
    node_id: int
    health_flags: int
    rx_dropped: int
    tx_dropped: int
    invalid_commands: int

    @property
    def version(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch


class BeamControlClient:
    def __init__(
        self,
        transport: CanTransport,
        *,
        source_node: int = P.CONTROLLER_NODE,
        timeout: float = 0.020,
        retries: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if source_node != P.CONTROLLER_NODE:
            raise ValueError(
                f"source_node must be {P.CONTROLLER_NODE} (controller), got {source_node}"
            )
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        if retries < 0:
            raise ValueError(f"retries must be non-negative, got {retries}")
        self._transport = transport
        self._source = source_node
        self._timeout = timeout
        self._retries = retries
        self._clock = clock
        self._seq = 0
        # All send()+recv() pairs share one receive socket, so the whole
        # client is serialized. A global lock is simpler and safer than
        # per-node locks: two callers cannot steal each other's responses.
        self._io_lock = threading.Lock()

    @classmethod
    def socketcan(cls, channel: str = "beamcan0", **kwargs: Any) -> BeamControlClient:
        return cls(SocketCanTransport(channel), **kwargs)

    def close(self) -> None:
        self._transport.close()

    # -- helpers ---------------------------------------------------------------
    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & P.SEQ_MASK
        return self._seq

    def _make_msg(self, msg_type: int, destination: int, payload) -> tuple[can.Message, int]:
        sequence = self._next_seq()
        arbitration_id = P.build_id(msg_type, destination, self._source, sequence)
        return can.Message(
            arbitration_id=arbitration_id,
            is_extended_id=True,
            is_remote_frame=False,
            data=bytes(payload),
        ), sequence

    # -- state-changing transactions -------------------------------------------
    @staticmethod
    def _validate_unicast_destination(destination: int) -> None:
        if not 1 <= destination <= 30:
            raise ValueError("destination must be a receiver node 1..30")

    def _transact(self, destination: int, msg_type: int, payload) -> bytes:
        self._validate_unicast_destination(destination)
        with self._io_lock:
            return self._transact_locked(destination, msg_type, payload)

    def _transact_locked(self, destination: int, msg_type: int, payload) -> bytes:
        # A fresh client starts at seq 0 and sends seq 1 first. If the Pi
        # process restarts but the STM32 replay cache does not, that seq may
        # collide with an already-cached transaction -> RES_SEQUENCE_REUSE.
        # On that explicit result we retry once with a fresh sequence. The seq
        # is never changed during ordinary timeout retries (exact-message rule).
        for resequence_attempt in range(2):
            msg, sequence = self._make_msg(msg_type, destination, payload)
            sequence_reused = False
            for _ in range(self._retries + 1):
                self._transport.send(msg)  # resend the exact same object
                deadline = self._clock() + self._timeout
                while True:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    reply = self._transport.recv(timeout=remaining)
                    if reply is None or not reply.is_extended_id or reply.is_remote_frame:
                        continue
                    f = P.parse_id(reply.arbitration_id)
                    if (
                        f["dest"] != self._source
                        or f["source"] != destination
                        or f["sequence"] != sequence
                    ):
                        continue
                    if f["type"] == P.ACK:
                        data = bytes(reply.data)
                        if len(data) != 2 or data[0] != msg_type or data[1] != P.RES_OK:
                            raise BeamControlProtocolError("malformed or mismatched ACK")
                        return data
                    if f["type"] == P.ERROR:
                        data = bytes(reply.data)
                        if len(data) != 2 or data[0] != msg_type:
                            raise BeamControlProtocolError("malformed or mismatched ERROR")
                        if data[1] == P.RES_SEQUENCE_REUSE and resequence_attempt == 0:
                            # The command was rejected, not applied; retry with
                            # a fresh sequence.
                            sequence_reused = True
                            break
                        raise BeamControlError(
                            f"node {destination} error", result=data[1], command_type=data[0]
                        )
                    # STATUS / other: ignore for a config transaction
                if sequence_reused:
                    break
            if sequence_reused:
                continue
            raise BeamControlError(f"timeout node {destination}; final state unknown")
        raise BeamControlError(f"timeout node {destination}; final state unknown")

    def enter_safe(self, destination: int, channel: int) -> bytes:
        P.validate_channel(channel)
        return self._transact(destination, P.ENTER_SAFE, [channel])

    def set_phase(self, destination: int, phase_states: Sequence[int]) -> bytes:
        return self._transact(destination, P.SET_PHASE, P.validate_phase_states(phase_states))

    def set_phase_channel(self, destination: int, channel: int, phase_state: int) -> bytes:
        P.validate_channel(channel)
        P.validate_phase_state(phase_state)
        return self._transact(destination, P.SET_PHASE, [phase_state, channel])

    def set_vga(self, destination: int, attenuation_db: Sequence[int]) -> bytes:
        return self._transact(destination, P.SET_VGA, P.validate_attenuations(attenuation_db))

    def set_vga_channel(self, destination: int, channel: int, attenuation_db: int) -> bytes:
        P.validate_channel(channel)
        P.validate_attenuation(attenuation_db)
        return self._transact(destination, P.SET_VGA, [attenuation_db, channel])

    def set_combined(
        self, destination: int, phase_states: Sequence[int], attenuation_db: Sequence[int]
    ) -> bytes:
        phase_payload = P.validate_phase_states(phase_states)
        vga_payload = P.validate_attenuations(attenuation_db)
        return self._transact(destination, P.SET_COMBINED, phase_payload + vga_payload)

    def set_combined_channel(
        self,
        destination: int,
        channel: int,
        phase_state: int,
        attenuation_db: int,
    ) -> bytes:
        P.validate_channel(channel)
        P.validate_phase_state(phase_state)
        P.validate_attenuation(attenuation_db)
        return self._transact(
            destination,
            P.SET_COMBINED,
            [phase_state, channel, attenuation_db],
        )

    def broadcast_enter_safe(self, channel: int) -> None:
        """Broadcast ENTER_SAFE to all nodes (dest 31). No response is sent."""
        P.validate_channel(channel)
        with self._io_lock:
            message = can.Message(
                arbitration_id=P.build_id(
                    P.ENTER_SAFE, P.BROADCAST_NODE, self._source, self._next_seq()
                ),
                is_extended_id=True,
                is_remote_frame=False,
                data=bytes([channel]),
            )
            self._transport.send(message)

    # -- discovery / status -----------------------------------------------------
    def discover(self, destination: int) -> NodeStatus:
        self._validate_unicast_destination(destination)
        with self._io_lock:
            return self._discover_locked(destination)

    def _discover_locked(self, destination: int) -> NodeStatus:
        sequence = self._next_seq()
        msg = can.Message(
            arbitration_id=P.build_id(P.PING, destination, self._source, sequence),
            is_extended_id=True,
            is_remote_frame=False,
            data=bytearray(),
        )
        self._transport.send(msg)
        deadline = self._clock() + self._timeout
        while self._clock() < deadline:
            reply = self._transport.recv(timeout=max(0.0, deadline - self._clock()))
            if reply is None or not reply.is_extended_id or reply.is_remote_frame:
                continue
            f = P.parse_id(reply.arbitration_id)
            if (
                f["source"] != destination
                or f["dest"] != self._source
                or f["type"] != P.STATUS
                or f["sequence"] != sequence
            ):
                continue
            d = bytes(reply.data)
            if len(d) != 8:
                raise BeamControlProtocolError("STATUS must have DLC 8")
            if d[3] != destination:
                continue
            return NodeStatus(
                d[0],
                d[1],
                d[2],
                d[3],
                d[4],
                d[5],
                d[6],
                d[7],
            )
        raise BeamControlError(f"no STATUS from node {destination}")
