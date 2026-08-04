# Firmware

The active firmware is under [`../stm32/`](../stm32/). It targets STM32F072R8T6 with libopencm3.

```bash
make firmware NODE=<1..30>
```

Outputs: `stm32/app/build/beamcontrol.{elf,bin,map}`.

The firmware implements CAN protocol 2.1, four local RF channels, safe phase transitions, ACK/ERROR responses, watchdog recovery, and retained diagnostics. See the [STM32 README](../stm32/README.md).
