"""BeamControl CAN protocol v2.0 constants and helpers (29-bit extended @ 500 kbit/s).

See docs/can-protocol.md for the full spec.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

PROTOCOL_MAJOR = 2
PROTOCOL_MINOR = 0
PROTOCOL_PATCH = 0

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
RES_RESERVED_BYTES = 6
RES_SEQUENCE_REUSE = 7
RES_BROADCAST_NOT_ALLOWED = 8

# --- Capability-discovery feature bits (mirror firmware CAN_PROTOCOL_FEATURE_*) ---
FEATURE_STRICT_CHANNELS = 1 << 0
FEATURE_ENTER_SAFE_ONLY_BROADCAST = 1 << 1
FEATURE_RESERVED_ZERO_VALIDATION = 1 << 2
FEATURE_DUPLICATE_REPLAY = 1 << 3
FEATURE_PROTOCOL_INFO = 1 << 4
FEATURE_SAFE_TRANSITIONS = 1 << 5
FEATURE_TERMINAL_RESPONSE = 1 << 6
FEATURE_STATUS_SUBTYPES = 1 << 7
FEATURE_BULK_RF_UPDATE = 1 << 8
FEATURE_FLAGS = (
    FEATURE_STRICT_CHANNELS
    | FEATURE_ENTER_SAFE_ONLY_BROADCAST
    | FEATURE_RESERVED_ZERO_VALIDATION
    | FEATURE_DUPLICATE_REPLAY
    | FEATURE_PROTOCOL_INFO
    | FEATURE_SAFE_TRANSITIONS
    | FEATURE_TERMINAL_RESPONSE
    | FEATURE_STATUS_SUBTYPES
    | FEATURE_BULK_RF_UPDATE
)

# --- Status subtypes / health flags ---
STATUS_SUBTYPE_PROTOCOL_INFO = 0xF0

# --- Capability discovery ---
SEQ_CAPABILITIES = 0xFFFF

# Field limits
PHASE_STATE_MAX = 255  # logical index into the receiver's calibrated phase lookup
RF_CHANNEL_COUNT = 4
PHASE_ADDR_MAX = RF_CHANNEL_COUNT - 1
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


def validate_channel(channel: int) -> None:
    if not (0 <= channel <= PHASE_ADDR_MAX):
        raise ValueError(f"channel must be 0..{PHASE_ADDR_MAX}")


def _validated_four(name: str, values: Iterable[int], maximum: int) -> bytes:
    try:
        items = list(values)
    except TypeError as exc:
        raise ValueError(f"{name} must contain exactly {RF_CHANNEL_COUNT} values") from exc
    if len(items) != RF_CHANNEL_COUNT:
        raise ValueError(f"{name} must contain exactly {RF_CHANNEL_COUNT} values")
    for value in items:
        if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= maximum):
            raise ValueError(f"each {name} value must be 0..{maximum}")
    return bytes(items)


def validate_phase_states(phase_states: Sequence[int]) -> bytes:
    return _validated_four("phase_states", phase_states, PHASE_STATE_MAX)


def validate_attenuations(attenuation_db: Sequence[int]) -> bytes:
    return _validated_four("attenuation_db", attenuation_db, ATTEN_DB_MAX)
