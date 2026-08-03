# RF control encoding

This document records the hardware-level serial formats used by the STM32 after a CAN command
has been decoded. The CAN payload carries logical values; the STM32 converts those values into
the RF IC command words.

## PE44820 phase shifter

`SET_PHASE` and `SET_COMBINED` carry an 8-bit `phase_state` in the range `0..255`. That byte is
the PE44820 phase setting `D7:D0`; it is not the complete SPI word.

In serial mode the PE44820 consumes a 13-bit program word in this logical order:

```text
D0 D1 D2 D3 D4 D5 D6 D7 OPT A0 A1 A2 A3
```

The first nine bits are the phase word and the last four bits are the unit address. Normal-mode
operation requires `OPT` to follow the 90-degree control bit `D6`. Because the STM32 SPI block
transmits MSB first, firmware reverses the eight phase bits and four address bits before packing:

```text
command = (reverse8(phase_state) << 5)
        | (D6 ? 1 : 0) << 4
        | reverse4(unit_address)
```

The datasheet example for approximately 205.3 degrees produces state `146` (`0x92`). At unit
address `3`, the resulting 13-bit command is `0x092C`. This vector is covered by the native
firmware tests.

The old `optimizedPhaseState_e` table assigns enum values `0..255`; those values remain valid
phase-state numbers. Its degree comments are frequency-specific calibration observations and
are not used as the generic wire definition.

## F0480 DVGA

`SET_VGA` and `SET_COMBINED` carry attenuation directly in dB. The F0480 supports every integer
step from `0` through `23` dB.

The F0480 serial byte uses `D6:D2` as a binary-weighted attenuation field:

```text
D6 D5 D4 D3 D2 = 16 dB, 8 dB, 4 dB, 2 dB, 1 dB
D7, D1, D0      = don't care; firmware writes zero
```

Firmware therefore forms the command as:

```text
command = attenuation_db << 2
```

Examples:

| Attenuation | SPI byte |
|:--|:--|
| 0 dB | `0x00` |
| 3 dB | `0x0C` |
| 8 dB | `0x20` |
| 16 dB | `0x40` |
| 23 dB | `0x5C` |

The names in the old VGA enum corresponded to individual bit weights and selected examples;
they were not the complete set of supported attenuation states.

## No RF-device acknowledgement

The receiver PCB connects clock, data-out-from-MCU, and latch/chip-select signals. It does not
connect a return data line from either RF control device to the STM32. Both drivers therefore
configure their SPI peripheral in transmit-only mode.

A BeamControl CAN `ACK` confirms that:

1. the STM32 accepted and validated the CAN command;
2. the requested local operation sequence was formed; and
3. the STM32 SPI peripheral completed transmitting before latch/chip-select was released.

It does not confirm that an RF IC decoded the word, changed state, or produced the expected RF
response. Those properties require board-level logic-analyzer and RF measurements.

## Datasheets

- `docs/pere_s_a0006625230_1-2279326.pdf` — PE44820 product specification
- `docs/REN_F0480_DST_20150427_1.pdf` — IDT/Renesas F0480 datasheet
