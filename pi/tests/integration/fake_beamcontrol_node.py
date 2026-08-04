"""A fake BeamControl node that listens on a CAN bus and replies per protocol v2.1.

Used for virtual-bus integration tests (python-can `virtual` interface). It
implements just enough of the wire protocol to exercise the client: SET_*
commands get an ACK, invalid ones an ERROR, and PING@0xFFFF gets a legacy
STATUS followed by PROTOCOL_INFO.
"""

from __future__ import annotations

import can

from beamcontrol import protocol as P


class FakeBeamControlNode:
    def __init__(self, bus: can.BusABC, node_id: int) -> None:
        self._bus = bus
        self.node_id = node_id
        self.seen: list[can.Message] = []

    def _reply(self, msg_type: int, src: int, seq: int, data: bytes) -> None:
        can_id = P.build_id(msg_type, 0, self.node_id, seq)
        self._bus.send(
            can.Message(
                arbitration_id=can_id,
                is_extended_id=True,
                is_remote_frame=False,
                data=data,
            )
        )

    def service(self, count: int = 10) -> int:
        """Process up to `count` inbound frames; returns how many were handled."""
        handled = 0
        for _ in range(count):
            msg = self._bus.recv(timeout=0.05)
            if msg is None or not msg.is_extended_id:
                break
            self.seen.append(msg)
            f = P.parse_id(msg.arbitration_id)
            data = bytes(msg.data)
            if f["type"] == P.PING:
                self._reply(
                    P.STATUS,
                    f["source"],
                    f["sequence"],
                    bytes([P.PROTOCOL_MAJOR, self.node_id, 0, 1, 23, 0, 0, 0]),
                )
                if f["sequence"] == P.SEQ_CAPABILITIES:
                    self._reply(
                        P.STATUS,
                        f["source"],
                        f["sequence"],
                        bytes(
                            [
                                P.STATUS_SUBTYPE_PROTOCOL_INFO,
                                P.PROTOCOL_MAJOR,
                                P.PROTOCOL_MINOR,
                                P.PROTOCOL_PATCH,
                                P.FEATURE_FLAGS & 0xFF,
                                P.FEATURE_FLAGS >> 8,
                                self.node_id,
                                0,
                            ]
                        ),
                    )
            elif f["type"] in (P.SET_PHASE, P.SET_VGA, P.SET_COMBINED, P.ENTER_SAFE):
                if f["type"] == P.SET_PHASE:
                    ok = len(data) == 4 or (len(data) == 2 and data[1] <= P.PHASE_ADDR_MAX)
                elif f["type"] == P.SET_VGA:
                    ok = (len(data) == 4 and all(value <= P.ATTEN_DB_MAX for value in data)) or (
                        len(data) == 2 and data[0] <= P.ATTEN_DB_MAX and data[1] <= P.PHASE_ADDR_MAX
                    )
                elif f["type"] == P.SET_COMBINED:
                    ok = (
                        len(data) == 8 and all(value <= P.ATTEN_DB_MAX for value in data[4:])
                    ) or (
                        len(data) == 3 and data[1] <= P.PHASE_ADDR_MAX and data[2] <= P.ATTEN_DB_MAX
                    )
                else:
                    ok = len(data) == 1 and data[0] <= P.PHASE_ADDR_MAX
                if ok:
                    self._reply(P.ACK, f["source"], f["sequence"], bytes([f["type"], P.RES_OK]))
                else:
                    self._reply(
                        P.ERROR, f["source"], f["sequence"], bytes([f["type"], P.RES_BAD_VALUE])
                    )
            handled += 1
        return handled
