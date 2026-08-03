# RF control encoding

This document records the hardware-level serial formats used by the STM32 after a CAN command
has been decoded. The CAN payload carries logical values; the STM32 converts those values into
the RF IC command words.

## PE44820 phase shifter

`SET_PHASE` and `SET_COMBINED` carry an 8-bit `phase_state` in the range `0..255`. The byte is a
logical phase index, not the PE44820 `D7:D0` field itself.

Firmware defines the calibrated 2.4 GHz words as `optimizedPhaseState_e` enum constants
in `stm32/app/include/PhaseStateEnum.h`. Each C2x binary literal shows the complete
9-bit PE44820 control word directly:

```text
bit 8     OPT
bits 7:0  D7:D0
```

The enum was extracted from the `2.4GHz` worksheet of `PE44820_Lookup_3Feb2025.xlsx`. A
reviewable export is stored in `docs/PE44820_Lookup_2.4GHz.csv`. An indexed enum table converts
the sequential CAN state number to the nonsequential enum value; directly casting the CAN index
to `optimizedPhaseState_e` would be incorrect.

In serial mode the PE44820 consumes a 13-bit program word in this logical order:

```text
D0 D1 D2 D3 D4 D5 D6 D7 OPT A0 A1 A2 A3
```

The first nine bits are the looked-up phase word and the last four bits are the unit address.
Because the STM32 SPI block transmits MSB first, firmware reverses the looked-up eight data bits
and four address bits before packing. `OPT` comes directly from bit 8 of the calibrated word:

```text
phase_state_enum = GetOptimizedPhaseState(phase_state)

command = MakePSCommand(phase_state_enum, unit_address)

MakePSCommand:
    (reverseBits(phase_state_enum & 0xff, 8) << 5)
  | (((phase_state_enum >> 8) & 1) << 4)
  | reverseBits(unit_address, 4)
```

For approximately 205.3 degrees, the logical index is `146`. The 2.4 GHz lookup maps that index
to 9-bit word `0x08D` (`010001101`). At unit address `3`, the resulting 13-bit command is
`0x162C`. This vector is covered by the native firmware tests.

Some logical indices intentionally map to the same hardware word because the calibration table
selects the closest measured state. The CAN protocol continues to transmit only the one-byte
logical index; the frequency-specific hardware mapping remains on the STM32.


## CANDev-compatible API

The RF helpers intentionally reuse the names and compact function boundaries from the
STM32Beamforming `CANDev` branch:

- `reverseBits()` reverses a field before serial packing;
- `GetOptimizedPhaseState()` converts the sequential CAN `stateWordTableIndex` to the
  nonsequential `optimizedPhaseState_e` value;
- `MakePSCommand()` forms the 13-bit PE44820 command;
- `pe448spisetup()` and `f0480spisetup()` retain the chip-specific setup names.

The pure builders remain in `beamforming_protocol.c` so they can be tested on the host without
linking STM32 peripheral code. The guarded `phase_shifter_write()` and `vga_write()` functions
remain separate because they add bounded waits, fault propagation, and explicit one-way-write
semantics that were not present in CANDev.

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
