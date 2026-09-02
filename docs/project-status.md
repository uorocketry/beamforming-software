# Project status

This page separates implemented software behavior from claims that require receiver
hardware. Update it when the PCB revision, firmware contract, or qualification evidence
changes.

## Implemented

- Raspberry Pi 5 SocketCAN controller, CLI, monitor, and read-only dashboard.
- Persistent systemd services for CAN setup and `beamd`.
- STM32F072R8T6 firmware with watchdog, bounded clock fallback, retained diagnostics,
  safe startup ordering, replay-safe requests, and bus-off recovery.
- Protocol v3.0 for one RF chain per receiver node.
- Schematic-derived CAN, PE44820, and F0480 GPIO/alternate-function assignments.
- Python unit/integration tests, native C tests, shared Python/C protocol vectors,
  command dry-smoke coverage, Renode test definitions, and Pi deployment tooling.

## Software verification boundary

Host tests can verify encoding, parsing, retry/replay behavior, queueing, state planning,
GPIO/SPI intent, deployment scripts, and buildability. They cannot prove:

- CAN electrical integrity, termination, oscillator tolerance, or wiring.
- PE44820/F0480 timing at the pins or successful RF-device decoding.
- Phase, attenuation, gain, noise, bandwidth, or channel-to-channel RF performance.
- Power-ramp, brownout, thermal, EMI, or long-duration behavior.

An STM32 ACK proves only that the MCU-side operation completed before its timeout. The
PCB does not route RF-device readback to the STM32.

## Current qualification state

The software test suite and an ARM firmware build have passed for the schematic-aligned
protocol v3.0 implementation. Physical two-node receiver validation has not yet been
completed. Do not describe the receiver hardware or RF path as qualified until evidence
is recorded against `docs/hardware-validation.md` for the exact PCB and firmware build.

## Next hardware steps

1. Assemble two receiver nodes and flash unique IDs, for example nodes `1` and `2`.
2. Verify rails, reset levels, the 16 MHz HSE, and safe GPIO levels before RF enable.
3. Verify two 120-ohm CAN terminators and inspect `ip -details -statistics link show beamcan0`.
4. Confirm each node answers only its own PING and reports protocol `3.0.0`.
5. Capture PE44820 and F0480 serial transactions for safe, phase, VGA, and combined commands.
6. Measure commanded attenuation and representative phase states before sweeping all states.
7. Run fault, reset, endurance, and release checks from the hardware checklist.

## Known development-host limitation

The repository bootstrap downloads Linux tool archives and officially supports Linux
hosts. Windows development should use WSL2. On macOS, Python and native C checks can be
run with a separately installed native `uv`, but the repository-managed ARM toolchain
bootstrap is not supported:

```bash
make UV="$(command -v uv)" pi-sync
make UV="$(command -v uv)" pi-lint pi-test pi-command-smoke protocol-check
make stm32-test
```

Build release firmware on Linux or the qualified Pi workflow until macOS tool archives
and hashes are added to the bootstrap scripts.
