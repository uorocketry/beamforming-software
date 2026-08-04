# BeamControl

BeamControl controls four-channel RF receiver boards from a Raspberry Pi 5 over CAN.

```mermaid
flowchart LR
    operator["Operator<br/>beamctl / dashboard"] --> pi["Raspberry Pi 5<br/>CAN node 0"]
    pi -->|"CAN 2.0B<br/>500 kbit/s"| stm32["STM32 receiver board<br/>node 1..30"]
    stm32 --> channels["RF channels 0..3"]
```

One board is one CAN node. Phase shifters and DVGAs are board-local devices.

## Layout

| Path | Purpose |
|:--|:--|
| `pi/` | Python client, CLI, monitor, dashboard, deployment |
| `stm32/` | STM32F072 firmware |
| `protocol/` | Shared Python/C vectors |
| `simulation/` | Docker/SocketCAN/Renode E2E |
| `tools/` | Setup, checks, bundles |
| `docs/` | Protocol, RF, operations |

## Develop

```bash
make setup
make doctor
make test
make check
make simulation-test
```

## Firmware

```bash
make firmware NODE=1
make firmware-size NODE=1
```

Node IDs are `1..30` and must be unique. Outputs are under `stm32/app/build/`.

## Controller

```bash
beamctl discover
beamctl ping 1

# Individual
beamctl set-phase 1 --state 128 --channel 2
beamctl set-vga 1 --attenuation 8 --channel 2
beamctl set-combined 1 --state 128 --attenuation 8 --channel 2

# Bulk, channel order 0..3
beamctl set-phase 1 --states 128 64 32 16
beamctl set-vga 1 --attenuations 8 9 10 11
beamctl set-combined 1 --states 64 65 66 67 --attenuations 12 13 14 15

beamctl enter-safe 1 --channel 2
beamd --config /etc/uorocketry/beamcontrol.toml
```

`beamd` serves a read-only dashboard on port `8080` and stays available when CAN is offline.

## Docs

- [Overview](docs/overview.md)
- [CAN protocol](docs/can-protocol.md)
- [RF encoding](docs/rf-control.md)
- [Developer setup](docs/operations/developer-setup.md)
- [Pi deployment](docs/operations/pi-provisioning.md)
- [Releases](docs/operations/releases.md)
