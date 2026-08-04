# Virtual end-to-end simulation

The simulation runs the real BeamControl controller and STM32 firmware without physical CAN
hardware:

```text
beamd + FastAPI ── SocketCAN vcan0 ── Renode STM32F072
                                          ├── SPI1 VGA sink
                                          └── SPI2 phase-shifter sink
```

Docker Compose owns the network namespace and creates `vcan0` inside it. The controller,
Renode, and test runner share that namespace. No CAN interface is created on the host.

## Run

Docker and Docker Compose are required. The Linux Docker kernel must support SocketCAN `vcan`,
and the module must be loaded. On distributions that build it as a module, run
`sudo modprobe vcan` once before starting the simulation. The repository setup must already
provide the ARM toolchain and libopencm3.

```bash
make simulation-test
```

The test builds node-1 firmware, starts the stack, and verifies:

- dashboard liveness and readiness;
- protocol v2.0 discovery;
- phase, VGA, combined, and safe CAN transactions;
- ACK responses from the real STM32 ELF;
- complete SPI data-register values; and
- phase-latch, serial-select, and VGA chip-select GPIO writes.

For interactive inspection:

```bash
make simulation-up
# dashboard: http://127.0.0.1:18080
make simulation-down
```

Set `BEAMCONTROL_SIM_PORT` to publish a different host port.

## Scope

The platform overlay supplies deterministic RCC, flash-control, and watchdog register behavior
that Renode 1.16.1 does not model for STM32F072. The test is a functional digital simulation;
it does not validate RF performance, voltages, oscillator tolerance, CAN termination, physical
SPI timing, brownouts, or watchdog expiry. Those remain hardware-in-the-loop acceptance tests.
