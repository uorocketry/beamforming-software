# STM32 receiver-board firmware

Bare-metal C firmware for the STM32F072R8T6 on one BeamControl receiver PCB.

## Role in the system

One flashed STM32 board is one CAN receiver node. The Raspberry Pi is controller node `0`;
receiver boards use unique addresses from `1` through `30`.

Each receiver board controls four RF channels (`0..3`). The phase shifters and DVGAs are local
peripherals on that board, not separate CAN nodes.

```text
CAN receiver node N
  |- channel 0: phase shifter + DVGA
  |- channel 1: phase shifter + DVGA
  |- channel 2: phase shifter + DVGA
  `- channel 3: phase shifter + DVGA
```

## Implemented behavior

The firmware:

- starts the watchdog and configures a bounded 48 MHz clock path;
- initializes the phase-shifter, DVGA, and CAN peripherals;
- starts in maximum attenuation;
- accepts CAN commands only from controller node `0`;
- applies safe phase transitions by attenuating before changing phase;
- sends ACK, ERROR, and STATUS responses defined by protocol v1.1;
- filters frames for its own node ID or broadcast address `31`;
- records retained reset and fault diagnostics; and
- enters safe lockout after repeated incomplete boots of the same image.

See [`../docs/can-protocol.md`](../docs/can-protocol.md) for the wire format.

## Build

The CAN node ID is compiled into the image. It is intentionally required at build time:

```bash
make firmware NODE=1
make firmware-size NODE=1
```

Valid IDs are `1..30`. Assign a different ID to every receiver board on the same bus. Building
without `NODE` fails instead of silently producing another node-1 image.

Outputs are written to `stm32/app/build/`:

- `beamcontrol.elf`
- `beamcontrol.bin`
- `beamcontrol.map`

CI compiles one representative node-1 image to verify the firmware. It does not publish
pre-addressed firmware images. Build the required node ID explicitly before flashing a board.

## Test

From the repository root:

```bash
make stm32-test
make check
```

The native C tests cover protocol encoding, command validation, queue behavior, safe output
ordering, diagnostics, build identity, and generated protocol vectors. `make check` also runs
Python tests and one representative cross-compiled firmware build.

## Hardware target

| Property | Value |
|:--|:--|
| MCU | STM32F072R8T6 |
| Core | Arm Cortex-M0 |
| Flash | 64 KiB |
| RAM | 16 KiB |
| Clock | 48 MHz, HSE/PLL with HSI48 fallback |
| CAN | Classical CAN 2.0B extended frames, 500 kbit/s |
| CAN pins | PA11 RX, PA12 TX, AF4 |
| Phase-shifter bus | SPI2 |
| DVGA bus | SPI1 |

Deployment still depends on PCB-level safe defaults during power-up. See
[`docs/HARDWARE_VALIDATION.md`](docs/HARDWARE_VALIDATION.md).

## Source layout

```text
app/src/main.c                 startup and main loop
app/src/can_runtime.c          command execution and responses
app/src/can_protocol.c         CAN identifier and payload codec
app/src/can_bus.c              bxCAN transport and interrupt handling
app/src/can_filter.c           acceptance-filter encoding
app/src/can_queue.c            ISR-to-main receive queue
app/src/can_control.c          safe hardware-operation planning
app/src/phaseShifter.c         phase-shifter driver
app/src/vga.c                  DVGA driver
app/src/diagnostics.c          retained diagnostic storage
app/src/faults.c               reset-on-fault handlers
tests/                         native C tests
```
