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

RF frames are not padded: DLC 2/3 means individual and DLC 4/8 means bulk. A padded individual frame is therefore a bulk frame. `ENTER_SAFE` uses one semantic byte; `PING` may be zero-padded only with zero bytes.

## Execution order

- Individual `SET_PHASE`: attenuate the selected channel to 23 dB if needed, write phase, restore attenuation.
- Bulk `SET_PHASE`: attenuate affected channels, write all four phases, restore each prior attenuation.
- Individual `SET_VGA`: write one attenuation.
- Bulk `SET_VGA`: validate all four values, then write all four.
- Individual `SET_COMBINED`: 23 dB, phase, requested attenuation on one channel.
- Bulk `SET_COMBINED`: 23 dB on all channels, four phases, four requested attenuations.
- `ENTER_SAFE`: 23 dB and phase state zero on one channel. Broadcast is allowed only for this command.

The planner validates the complete frame before hardware writes.

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
| `6` | `RESERVED_BYTES` | Nonzero padding on a command that permits padding |
| `7` | `SEQUENCE_REUSE` | Same key, different request bytes |
| `8` | `BROADCAST_NOT_ALLOWED` | Non-safe broadcast |

## Status and discovery

Normal `PING` returns a channel-0 snapshot:

```text
0 protocol major (2)
1 node ID
2 phase state
3 PE44820 address (1)
4 attenuation dB
5 health flags
6 RX-drop count low byte
7 invalid-command count low byte
```

`PING` sequence `0xffff` also returns `PROTOCOL_INFO`:

```text
0 0xf0
1 major (2)
2 minor (1)
3 patch (0)
4 feature flags low
5 feature flags high
6 node ID
7 zero
```

Required feature bits include `BULK_RF_UPDATE` (bit 8) and `INDIVIDUAL_RF_UPDATE` (bit 9).

## Contract vectors

- Source: `protocol/v2.1-vectors.toml`
- Generated C: `protocol/generated/protocol_vectors.h`

```bash
python3 tools/generate-protocol-vectors.py
```
