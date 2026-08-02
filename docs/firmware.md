# Firmware

The active firmware is the C implementation under [`../stm32/`](../stm32/). It targets the
STM32F072R8T6 on one four-channel receiver board and uses libopencm3.

Each flashed board is one CAN receiver node. Its node ID is compiled into the image and must
be selected explicitly:

```bash
make firmware NODE=<1..30>
```

The build produces `beamcontrol.elf`, `beamcontrol.bin`, and `beamcontrol.map` under
`stm32/app/build/`.

The firmware:

- controls four local RF channels;
- implements [CAN protocol v1.1](can-protocol.md);
- applies safe phase and attenuation transitions;
- validates commands and sends ACK or ERROR responses; and
- records retained reset and fault diagnostics.

The detailed source layout, hardware pins, and test commands are in the
[STM32 README](../stm32/README.md).
