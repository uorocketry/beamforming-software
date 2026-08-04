# BeamControl CAN protocol v2.0

This document defines the implemented wire contract shared by the Raspberry Pi controller,
the STM32 receiver firmware, and the generated Python/C protocol-vector tests.

Protocol 2.0 is a breaking payload revision. The 29-bit identifier layout and numeric message
types are unchanged, but the three RF configuration commands now carry all four receiver
channels in one Classical CAN frame.

## Bus profile

| Property | Value |
|:--|:--|
| Format | Classical CAN 2.0B extended data frames |
| Identifier | 29-bit |
| Bitrate | 500,000 bit/s |
| Sample point | 87.5% |
| SJW | 1 TQ |
| Controller node | Raspberry Pi, address `0` |
| Receiver nodes | STM32 boards, addresses `1..30` |
| Broadcast destination | `31` |
| Maximum payload | 8 bytes |
| Protocol version | 2.0.0 |

## Terminology and channel order

A **receiver node** is one BeamControl board with one STM32. Each receiver has four RF
channels. Every bulk payload uses the same fixed order:

```text
array index / CAN byte position:  0   1   2   3
physical channel name:           1   2   3   4
PE44820 serial address:           1   2   3   4
```

The software arrays are zero-based, but the PE44820 addresses transmitted by the STM32 are
one-based. The phase address is derived from the array index and is not sent in the payload.

## Identifier layout

```text
Bits 28:26  TYPE        3 bits
Bits 25:21  DEST        5 bits
Bits 20:16  SOURCE      5 bits
Bits 15:0   SEQUENCE    16 bits
```

```text
identifier = (type << 26) | (destination << 21) | (source << 16) | sequence
```

Responses swap source and destination and retain the request sequence. `ENTER_SAFE` has the
lowest numeric type and therefore the highest arbitration priority used by this protocol.

## Message types and payloads

| Type | Message | Direction | Payload |
|:--|:--|:--|:--|
| `0` | `ENTER_SAFE` | Controller → receiver | `[channel]` |
| `1` | `SET_COMBINED` | Controller → receiver | `[PS1, PS2, PS3, PS4, VGA1, VGA2, VGA3, VGA4]` |
| `2` | `SET_PHASE` | Controller → receiver | `[PS1, PS2, PS3, PS4]` |
| `3` | `SET_VGA` | Controller → receiver | `[VGA1, VGA2, VGA3, VGA4]` |
| `4` | `PING` | Controller → receiver | empty |
| `5` | `STATUS` | Receiver → controller | 8-byte status |
| `6` | `ACK` | Receiver → controller | `[command_type, result]` |
| `7` | `ERROR` | Receiver → controller | `[command_type, result]` |

Field ranges are:

- `channel`: `0..3`, used only by `ENTER_SAFE`;
- `PS1..PS4`: `0..255`, each interpreted as an index into the calibrated 2.4 GHz phase enum;
- `VGA1..VGA4`: `0..23`, each expressed in integer dB.

### `SET_PHASE`

```text
byte 0  phase-state index for channel 1 / PE44820 address 1
byte 1  phase-state index for channel 2 / PE44820 address 2
byte 2  phase-state index for channel 3 / PE44820 address 3
byte 3  phase-state index for channel 4 / PE44820 address 4
```

The firmware performs a safe three-stage transition. Channels below 23 dB are first moved to
23 dB, all four phase shifters are programmed, and each affected channel's previous
attenuation is restored.

### `SET_VGA`

```text
byte 0  attenuation for VGA channel 1
byte 1  attenuation for VGA channel 2
byte 2  attenuation for VGA channel 3
byte 3  attenuation for VGA channel 4
```

All four values are validated before any hardware operation is planned.

### `SET_COMBINED`

```text
bytes 0..3  phase-state indexes for channels 1..4
bytes 4..7  attenuation values for VGA channels 1..4
```

The firmware first plans 23 dB for all channels, then plans the four phase writes, then plans
the requested attenuation values. A requested value of 23 dB is not written twice because
the first stage already applied it.

### `ENTER_SAFE`

`ENTER_SAFE` intentionally remains a one-channel emergency command. The payload byte is the
zero-based channel index `0..3`. The STM32 plans 23 dB attenuation and calibrated phase state
zero for that channel. Broadcast destination `31` is accepted only for `ENTER_SAFE`.

## DLC and reserved bytes

The minimum semantic payload lengths are:

| Message | Used bytes |
|:--|--:|
| `ENTER_SAFE` | 1 |
| `SET_PHASE` | 4 |
| `SET_VGA` | 4 |
| `SET_COMBINED` | 8 |
| `PING` | 0 |

A frame may use a longer DLC only when every byte after the semantic payload is zero.
`SET_COMBINED` already occupies all eight Classical CAN bytes and cannot be padded further.
An exact retry must preserve the original identifier, DLC, and payload bytes.

## Responses, retries, and acknowledgement meaning

A unicast state-changing command produces one terminal response:

- `ACK` when STM32-side validation and all planned SPI transfers complete;
- `ERROR` when decoding, validation, sequencing, or execution rejects the command.

The RF control interfaces on this PCB are transmit-only. There is no MISO/readback path from
the PE44820 or F0480 devices. Therefore an `ACK` does **not** prove that an RF IC accepted the
word or that the analog RF state was measured and verified.

The controller matches responses by source, destination, sequence, and command type. It keeps
at most one outstanding transaction per receiver node. The default host policy uses a 20 ms
timeout and two exact-message retries. A final timeout means the resulting hardware state is
unknown.

The receiver caches the most recent successful unicast state-changing request and ACK:

- an identical request replays the cached ACK without repeating RF writes;
- the same source/type/sequence with different DLC or data returns `SEQUENCE_REUSE`;
- broadcast commands are not cached and do not receive a response.

## Result codes

| Value | Name | Meaning |
|:--|:--|:--|
| `0` | `OK` | Command completed on the STM32 side |
| `1` | `INVALID_LENGTH` | DLC is shorter than the required payload |
| `2` | `INVALID_PAYLOAD` | A channel or attenuation value is outside its range |
| `3` | `UNSUPPORTED` | Message type is not a controller command |
| `4` | `HARDWARE` | Hardware operation failed |
| `5` | `BUSY` | Receiver cannot accept the command |
| `6` | `RESERVED_BYTES` | A byte after the semantic payload was nonzero |
| `7` | `SEQUENCE_REUSE` | A sequence was reused with different request bytes |
| `8` | `BROADCAST_NOT_ALLOWED` | A non-safe command used broadcast destination `31` |

## Status and capability discovery

A normal `PING` returns the existing eight-byte status payload. Because that legacy payload
has room for only one phase/VGA snapshot, protocol 2.0 reports channel 1 deterministically:

```text
byte 0  protocol major (`2`)
byte 1  receiver node ID
byte 2  channel-1 phase-state index
byte 3  channel-1 PE44820 address (`1`)
byte 4  channel-1 attenuation in dB
byte 5  health flags
byte 6  receive-drop count, low byte
byte 7  invalid-command count, low byte
```

A `PING` with sequence `0xffff` returns that status frame followed by `PROTOCOL_INFO`:

```text
byte 0  0xf0 subtype
byte 1  major (`2`)
byte 2  minor (`0`)
byte 3  patch (`0`)
byte 4  feature flags bits 7:0
byte 5  feature flags bits 15:8
byte 6  receiver node ID
byte 7  reserved zero
```

Protocol 2.0 adds feature bit 8, `BULK_RF_UPDATE`. The production monitor requires protocol
major 2 and every advertised required feature bit before reporting a configured node healthy.

## Shared contract vectors

Language-neutral vectors live in:

- `protocol/v2.0-vectors.toml`
- `protocol/generated/protocol_vectors.h`

Run `python3 tools/generate-protocol-vectors.py` after changing the TOML file. CI verifies that
the generated C header and the Python/C implementations remain in agreement.
