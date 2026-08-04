# STM32 receiver firmware

Bare-metal C/libopencm3 firmware for STM32F072R8T6. Each board is one CAN node (`1..30`) with four RF channels (`0..3`).

## Behavior

- 48 MHz clock with bounded HSI48 fallback
- watchdog and retained fault/reset diagnostics
- safe maximum-attenuation startup
- CAN protocol 2.1 from controller node `0`
- individual and bulk phase/VGA updates
- attenuation before phase changes
- filtered RX, prioritized TX, replay-safe retries, bus-off recovery

## Build

```bash
make firmware NODE=1
make firmware-size NODE=1
```

`NODE` is required and must be unique. Outputs are under `stm32/app/build/`.

## Test

```bash
make stm32-test
make check
```

## Target

| Property | Value |
|:--|:--|
| MCU | STM32F072R8T6, Cortex-M0 |
| Flash / RAM | 64 KiB / 16 KiB |
| Clock | 48 MHz, HSE/PLL with HSI48 fallback |
| CAN | 2.0B extended, 500 kbit/s, PA11/PA12 AF4 |
| Phase bus | SPI2 |
| VGA bus | SPI1 |

Both RF buses are transmit-only. ACK means the STM32 completed the transfer, not that an RF IC accepted or applied it.

## Source map

```text
app/src/main.c              startup/main loop
app/src/can_runtime.c       execution/responses/replay
app/src/can_protocol.c      CAN codec
app/src/can_bus.c           bxCAN transport/ISR
app/src/can_control.c       safe operation planner
app/src/phaseShifter.c      PE44820 driver
app/src/vga.c               F0480 driver
app/src/diagnostics.c       retained diagnostics
app/src/faults.c            fault reset handlers
tests/                      native tests
```

See [RF encoding](../docs/rf-control.md) and [hardware validation](docs/HARDWARE_VALIDATION.md).
