# BeamControl CAN protocol v1.1

This is the implemented wire contract shared by the Raspberry Pi software, STM32 firmware,
and generated protocol-vector tests.

## Bus profile

| Property | Value |
|:--|:--|
| Format | Classical CAN 2.0B extended data frames |
| Identifier | 29-bit |
| Bitrate | 500,000 bit/s |
| Sample point | 87.5% |
| SJW | 1 TQ |
| Controller node | Raspberry Pi, address `0` |
| Receiver nodes | One STM32 board each, addresses `1..30` |
| Broadcast destination | `31` |
| Maximum payload | 8 bytes |
| Protocol version | 1.1 |

## Terminology

- A **receiver node** is one complete BeamControl board with one STM32.
- An **RF channel** is one of the four signal paths inside a receiver node (`0..3`).
- Phase shifters, DVGAs, antenna elements, and other peripherals are not CAN nodes.

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
lowest numeric message type and therefore the highest arbitration priority used by this
protocol.

## Message types

| Type | Message | Direction | Payload |
|:--|:--|:--|:--|
| `0` | `ENTER_SAFE` | Controller → receiver | `[channel]` |
| `1` | `SET_COMBINED` | Controller → receiver | `[phase_state, channel, attenuation_db]` |
| `2` | `SET_PHASE` | Controller → receiver | `[phase_state, channel]` |
| `3` | `SET_VGA` | Controller → receiver | `[attenuation_db]` |
| `4` | `PING` | Controller → receiver | empty |
| `5` | `STATUS` | Receiver → controller | 8-byte status |
| `6` | `ACK` | Receiver → controller | `[command_type, result]` |
| `7` | `ERROR` | Receiver → controller | `[command_type, result]` |

Valid application values are:

- `channel`: `0..3`
- `phase_state`: `0..255`
- `attenuation_db`: `0..23`

Unused payload bytes must be zero. A command may use its minimum DLC or a longer zero-padded
DLC, but an exact retry must preserve the original identifier, DLC, and payload bytes.

## Responses and retries

A unicast state-changing command produces one terminal response:

- `ACK` when the command completes successfully;
- `ERROR` when validation or execution rejects the command.

The controller matches responses by source, destination, sequence, and command type. It keeps
at most one outstanding transaction per receiver node. The default host policy uses a 20 ms
timeout and two exact-message retries. A final timeout means the resulting hardware state is
unknown.

Duplicate requests are handled by a replay cache keyed by source, type, and sequence:

- identical request: replay the cached response;
- same key with different DLC or payload: return sequence-reuse error.

Broadcast address `31` accepts only idempotent `ENTER_SAFE`. Broadcast requests never produce
ACK or ERROR frames.

## Safe output transitions

`SET_PHASE` and `SET_COMBINED` apply outputs in this order:

1. Apply 23 dB attenuation.
2. Program the phase shifter.
3. Apply the final requested attenuation.

An ACK is sent only after all steps complete. Recoverable failures leave attenuation at 23 dB.
Fatal SPI failures reset the firmware, so the controller observes a missing response.

## Capability discovery

Sequence `0xFFFF` is reserved for discovery. A receiver answers `PING` at that sequence with
its normal status and a `PROTOCOL_INFO` status frame:

| Byte | Value |
|:--|:--|
| 0 | `0xF0` subtype |
| 1 | Major version |
| 2 | Minor version |
| 3 | Patch version |
| 4–5 | Feature flags, little-endian |
| 6 | Compiled receiver node ID |
| 7 | Reserved, zero |

A receiver without `PROTOCOL_INFO` is treated as protocol v1.0. Configured receivers must
advertise v1.1 or newer and all required feature flags before the monitor reports them healthy.

## Physical configuration

The repository configures:

- STM32F072 bxCAN at 48 MHz: prescaler 6, BS1 13, BS2 2;
- Raspberry Pi SocketCAN at 500 kbit/s, 87.5% sample point, SJW 1;
- automatic bus restart after 100 ms on the Pi.

The bus requires exactly two 120 Ω termination resistors, a common CAN reference, a linear
trunk, and short stubs.

## Acceptance filters

The STM32 accepts only extended data frames from controller node `0` addressed to its own node
ID or broadcast address `31`. Hardware filters reject standard and remote frames; firmware
rechecks frame format, source, and destination before dispatch.

## Source of truth

The executable contract is maintained in:

- `protocol/v1.1-vectors.toml`
- `protocol/generated/protocol_vectors.h`
- `pi/src/beamcontrol/protocol.py`
- `stm32/app/src/can_protocol.c`

Run `make protocol-check` after any protocol change.
