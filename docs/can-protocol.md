# BeamControl CAN protocol v2.1

Implemented by the Pi client, STM32 firmware, and shared vectors.

## Bus

| Property | Value |
|:--|:--|
| Frame | Classical CAN 2.0B extended data |
| Bitrate | 500 kbit/s |
| Sample point / SJW | 87.5% / 1 TQ |
| Controller | Node `0` |
| Receivers | Nodes `1..30` |
| Broadcast | `31` |
| Payload | 0..8 bytes |

## Identifier

```text
28:26 TYPE
25:21 DEST
20:16 SOURCE
15:0  SEQUENCE
```

```text
id = (type << 26) | (dest << 21) | (source << 16) | sequence
```

Responses swap source/destination and preserve sequence. `ENTER_SAFE` has the highest command priority because its type is `0`.

## Channels

Software channels are `0..3`. Bulk array indexes map to PE44820 addresses `1..4`.

## Messages

| Type | Name | Direction | Exact payload |
|:--|:--|:--|:--|
| `0` | `ENTER_SAFE` | Controller -> receiver | `[channel]` |
| `1` | `SET_COMBINED` | Controller -> receiver | `[state, channel, atten]` or `[PS1..PS4, VGA1..VGA4]` |
| `2` | `SET_PHASE` | Controller -> receiver | `[state, channel]` or `[PS1, PS2, PS3, PS4]` |
| `3` | `SET_VGA` | Controller -> receiver | `[atten, channel]` or `[VGA1, VGA2, VGA3, VGA4]` |
| `4` | `PING` | Controller -> receiver | empty |
| `5` | `STATUS` | Receiver -> controller | 8 bytes |
| `6` | `ACK` | Receiver -> controller | `[command_type, result]` |
| `7` | `ERROR` | Receiver -> controller | `[command_type, result]` |

Ranges:

- `channel`: `0..3`
- phase state: `0..255`, index into the calibrated 2.4 GHz enum
- attenuation: `0..23` dB

RF commands require exact DLCs:

| Command | Individual | Bulk |
|:--|--:|--:|
| `SET_PHASE` | 2 | 4 |
| `SET_VGA` | 2 | 4 |
| `SET_COMBINED` | 3 | 8 |

Every command uses an exact DLC. `ENTER_SAFE` is 1 byte and `PING` is empty.

## Execution order

```mermaid
flowchart LR
    vga[SET_VGA] --> vgaWrite["Write attenuation(s)"]
    phase[SET_PHASE] --> phaseSafe["23 dB"] --> phaseWrite["Write phase(s)"] --> restore["Restore attenuation(s)"]
    combined[SET_COMBINED] --> combinedSafe["23 dB"] --> combinedPhase["Write phase(s)"] --> apply["Apply attenuation(s)"]
    safe[ENTER_SAFE] --> safeAtten["23 dB"] --> safePhase["Phase state 0"]
```

The planner validates the complete frame before hardware writes. Broadcast is allowed only for `ENTER_SAFE`.

## ACK, retries, replay

A unicast state-changing request returns:

- `ACK` after validation and planned STM32 SPI transfers complete
- `ERROR` on decode, validation, sequence, or execution failure

ACK is not RF-device readback; neither RF interface has MISO connected.

The client matches source, destination, sequence, and command type. Default timeout: 20 ms. Default retries: two, using identical ID, DLC, and bytes. A final timeout means hardware state is unknown.

The receiver caches the latest successful unicast state-changing request:

- identical retry: replay ACK, no RF writes
- same source/type/sequence with different DLC or data: `SEQUENCE_REUSE`
- broadcast: no cache, no response

## Results

| Value | Name | Meaning |
|:--|:--|:--|
| `0` | `OK` | Completed on STM32 |
| `1` | `INVALID_LENGTH` | Unsupported DLC |
| `2` | `INVALID_PAYLOAD` | Invalid channel or attenuation |
| `3` | `UNSUPPORTED` | Not a controller command |
| `4` | `HARDWARE` | Hardware operation failed |
| `5` | `BUSY` | Cannot accept command |
| `6` | `SEQUENCE_REUSE` | Same key, different request bytes |
| `7` | `BROADCAST_NOT_ALLOWED` | Non-safe broadcast |

## Status and discovery

`PING` returns one STATUS frame:

```text
0 protocol major (2)
1 protocol minor (1)
2 protocol patch (0)
3 node ID
4 health flags
5 RX-drop count low byte
6 TX-drop count low byte
7 invalid-command count low byte
```

Version matching is exact.

## Contract vectors

- Source: `protocol/v2.1-vectors.toml`
- Generated C: `protocol/generated/protocol_vectors.h`

```bash
python3 tools/generate-protocol-vectors.py
```
