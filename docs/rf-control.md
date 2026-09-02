# RF control encoding

CAN carries logical values; STM32 builds device serial words.

## PE44820

Each receiver board contains one PE44820. A phase value is a `0..255` lookup
index. Firmware maps it to a calibrated 2.4 GHz `optimizedPhaseState_e` value
from `rf/phase_states_2_4ghz.h`:

```text
bit 8     OPT
bits 7:0  D7:D0
```

Source data: `docs/PE44820_Lookup_2.4GHz.csv`. Do not cast the index directly to the enum; the mapping is nonsequential and contains intentional duplicates.

PE44820 serial order:

```text
D0 D1 D2 D3 D4 D5 D6 D7 OPT A0 A1 A2 A3
```

STM32 SPI sends MSB-first, so firmware reverses the 8-bit phase field and 4-bit address before packing:

```text
state = GetOptimizedPhaseState(index)
command =
    (reverseBits(state & 0xff, 8) << 5)
  | (((state >> 8) & 1) << 4)
  | reverseBits(address, 4)
```

The R2A schematic connects PE44820 address pins A0..A3 to PA4, PA5, PA6,
and PC4. Firmware selects serial mode on PC7 and drives static unit address 1
(A0 high, A1..A3 low). Example: index `146` -> word `0b010001101`
(`0x08D`); address `1` -> command `0x1628`.

CANDev-compatible names retained: `optimizedPhaseState_e`, `GetOptimizedPhaseState()`, `reverseBits()`, `MakePSCommand()`, `pe448spisetup()`.

## F0480

Attenuation is `0..23` dB. Command bits `D6:D2` encode `16,8,4,2,1` dB; `D7,D1,D0` are zero.

```text
command = attenuation_db << 2
```

| dB | Byte |
|--:|:--|
| 0 | `0x00` |
| 3 | `0x0C` |
| 8 | `0x20` |
| 16 | `0x40` |
| 23 | `0x5C` |

The R2A schematic contains one F0480. Its SPI1 nets are PA15 chip select,
PB3 clock, and PB5 data.

## ACK limit

Both buses are transmit-only. ACK confirms:

1. CAN validation passed.
2. The operation plan completed.
3. STM32 SPI finished before latch/CS release.

ACK does not confirm RF-device decode or measured RF state.

## References

- `docs/pere_s_a0006625230_1-2279326.pdf`
- `docs/REN_F0480_DST_20150427_1.pdf`
- `docs/PE44820_Lookup_2.4GHz.csv`
