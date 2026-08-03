# RF control encoding

This document records the hardware-level serial formats used by the STM32 after a CAN command
has been decoded. The CAN payload carries logical values; the STM32 converts those values into
the RF IC command words.

## PE44820 phase shifter

`SET_PHASE` and `SET_COMBINED` carry an 8-bit `phase_state` in the range `0..255`. The byte is a
logical phase index, not the PE44820 `D7:D0` field itself.

Firmware indexes the calibrated 2.4 GHz table in
`stm32/app/include/phase_lookup_2_4_ghz.h`. Each entry is the complete 9-bit PE44820 control
word:

```text
bit 8     OPT
bits 7:0  D7:D0
```

The table was extracted from the `2.4GHz` worksheet of `PE44820_Lookup_3Feb2025.xlsx`. A
reviewable export is stored in `docs/PE44820_Lookup_2.4GHz.csv`.

In serial mode the PE44820 consumes a 13-bit program word in this logical order:

```text
D0 D1 D2 D3 D4 D5 D6 D7 OPT A0 A1 A2 A3
```

The first nine bits are the looked-up phase word and the last four bits are the unit address.
Because the STM32 SPI block transmits MSB first, firmware reverses the looked-up eight data bits
and four address bits before packing. `OPT` comes directly from bit 8 of the calibrated word:

```text
phase_word = phase_lookup_2_4_ghz[phase_state]

command = (reverse8(phase_word & 0xff) << 5)
        | (((phase_word >> 8) & 1) << 4)
        | reverse4(unit_address)
```

For approximately 205.3 degrees, the logical index is `146`. The 2.4 GHz lookup maps that index
to 9-bit word `0x08D` (`010001101`). At unit address `3`, the resulting 13-bit command is
`0x162C`. This vector is covered by the native firmware tests.

Some logical indices intentionally map to the same hardware word because the calibration table
selects the closest measured state. The CAN protocol continues to transmit only the one-byte
logical index; the frequency-specific hardware mapping remains on the STM32.

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
- `docs/PE44820_Lookup_2.4GHz.csv` — calibrated 2.4 GHz phase lookup used by firmware
