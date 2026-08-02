# BeamControl

BeamControl controls a four-channel RF receiver board from a Raspberry Pi 5 over CAN.
The repository contains the Pi software, STM32 firmware, shared protocol tests, deployment
tooling, and hardware notes.

## Implemented architecture

```text
Operator / browser / beamctl
            |
Raspberry Pi 5 + CAN HAT       CAN controller node 0
            |
        CAN 2.0 bus
            |
STM32 receiver board           CAN receiver node 1..30
  |- RF channel 0
  |- RF channel 1
  |- RF channel 2
  `- RF channel 3
```

One complete STM32 receiver board is one CAN node. Its four RF paths are channels inside
that node. Phase shifters, DVGAs, LNAs, filters, detectors, and antenna elements are not CAN
nodes. The Arduino/Wi-Fi and external ADC path shown in the REV3 design drawing is not part
of the implemented software or CAN protocol.

The protocol uses controller node `0`, receiver-board nodes `1..30`, and broadcast address
`31`. See [`docs/can-protocol.md`](docs/can-protocol.md).

## Repository layout

| Path | Purpose |
|:--|:--|
| `pi/` | Python 3.11 controller package, CLI, FastAPI dashboard, and Raspberry Pi deployment files |
| `stm32/` | STM32F072 firmware for one receiver board |
| `protocol/` | Shared Python/C protocol vectors |
| `simulation/` | Docker Compose, Renode platform, and virtual end-to-end test |
| `tools/` | Reproducible setup, diagnostics, bundle building, and checks |
| `docs/` | Current architecture, operations, and hardware design notes |

## Develop and test

```bash
make setup
make doctor
make test
make check
```

`make check` runs linting, all host tests, the protocol contract, and one representative
STM32 build. CI does not prebuild firmware for arbitrary receiver addresses.

Run the real controller and STM32 ELF together over container-local virtual CAN with:

```bash
make simulation-test
```

See [`simulation/README.md`](simulation/README.md) for scope and interactive use.

## Build STM32 firmware

A node ID is required and must be unique on the physical CAN bus:

```bash
make firmware NODE=1
make firmware-size NODE=1
```

Valid receiver-board IDs are `1..30`. The build writes `beamcontrol.elf`,
`beamcontrol.bin`, and `beamcontrol.map` under `stm32/app/build/`.

## Use the Pi controller

```bash
beamctl discover
beamctl ping 1
beamctl set-phase 1 --channel 2 --state 128
beamd --config /etc/uorocketry/beamcontrol.toml
```

The first positional ID is the receiver-board CAN node. `--channel` selects one of that
board's four RF channels (`0..3`).

`beamd` owns the CAN status monitor and serves a read-only FastAPI/Jinja2/HTMX dashboard on
port `8080`. The dashboard remains available when CAN hardware or receiver boards are offline.

For installation and releases, see:

- [Developer setup](docs/operations/developer-setup.md)
- [Raspberry Pi 5 deployment](docs/operations/pi-provisioning.md)
- [Release process](docs/operations/releases.md)
