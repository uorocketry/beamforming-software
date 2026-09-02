"""BeamControl CAN protocol v3.0 constants and helpers (29-bit extended @ 500 kbit/s).

See docs/can-protocol.md for the full spec.
"""

from __future__ import annotations

PROTOCOL_VERSION = (3, 0, 0)

# --- Identifier bit fields (29-bit extended) ---
TYPE_SHIFT = 26
DEST_SHIFT = 21
SOURCE_SHIFT = 16
TYPE_MASK = 0x7
DEST_MASK = 0x1F
SOURCE_MASK = 0x1F
SEQ_MASK = 0xFFFF
CAN_EXT_ID_MAX = 0x1FFFFFFF

# --- Node numbers ---
CONTROLLER_NODE = 0
BROADCAST_NODE = 31

# --- Message types (numeric values are fixed; ENTER_SAFE is lowest => highest priority) ---
ENTER_SAFE = 0
SET_COMBINED = 1
SET_PHASE = 2
SET_VGA = 3
PING = 4
STATUS = 5
ACK = 6
ERROR = 7

# --- Result codes ---
RES_OK = 0
RES_BAD_LEN = 1
RES_BAD_VALUE = 2
RES_UNSUPPORTED = 3
RES_HW_FAIL = 4
RES_BUSY = 5
RES_SEQUENCE_REUSE = 6
RES_BROADCAST_NOT_ALLOWED = 7

# Field limits
PHASE_STATE_MAX = 255  # logical index into the receiver's calibrated phase lookup
ATTEN_DB_MAX = 23  # F0480 supports every 1 dB step from 0 through 23 dB


def build_id(msg_type: int, destination: int, source: int, sequence: int) -> int:
    if not (0 <= msg_type <= 7 and 0 <= destination <= 31 and 0 <= source <= 31):
        raise ValueError("id field out of range")
    if not (0 <= sequence <= SEQ_MASK):
        raise ValueError("sequence out of range")
    return (
        (msg_type << TYPE_SHIFT)
        | (destination << DEST_SHIFT)
        | (source << SOURCE_SHIFT)
        | (sequence & SEQ_MASK)
    )


def parse_id(can_id: int) -> dict:
    return {
        "type": (can_id >> TYPE_SHIFT) & TYPE_MASK,
        "dest": (can_id >> DEST_SHIFT) & DEST_MASK,
        "source": (can_id >> SOURCE_SHIFT) & SOURCE_MASK,
        "sequence": can_id & SEQ_MASK,
    }


def _validated_value(name: str, value: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= maximum):
        raise ValueError(f"{name} must be 0..{maximum}")
    return value


def validate_phase_state(phase_state: int) -> int:
    return _validated_value("phase_state", phase_state, PHASE_STATE_MAX)


def validate_attenuation(attenuation_db: int) -> int:
    return _validated_value("attenuation_db", attenuation_db, ATTEN_DB_MAX)
