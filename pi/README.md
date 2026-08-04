# Raspberry Pi controller

Python 3.11 controller for Raspberry Pi 5, CAN node `0`. Receiver boards use nodes `1..30` and channels `0..3`.

## Package

`src/beamcontrol/` contains:

- `BeamControlClient`: commands, retries, discovery, response matching
- `SocketCanTransport`: Linux SocketCAN via `python-can`
- `beamctl`: operator CLI
- `beamd`: monitor and read-only dashboard
- TOML configuration

## Develop

```bash
make setup
make pi-test
make pi-lint
```

## Commands

```bash
beamctl discover
beamctl ping 1
beamctl set-phase 1 --state 128 --channel 2
beamctl set-phase 1 --states 128 64 32 16
beamctl set-vga 1 --attenuation 8 --channel 2
beamctl set-vga 1 --attenuations 8 9 10 11
beamctl set-combined 1 --state 128 --attenuation 8 --channel 2
beamctl set-combined 1 --states 64 65 66 67 --attenuations 12 13 14 15
beamctl enter-safe 1 --channel 2
```

## Dashboard

`beamd` serves FastAPI/Jinja2 status on port `8080`. It shows service, CAN, node health, protocol, response time, and recent events. `/readyz` returns `503` when CAN or required nodes are unhealthy.

The dashboard is read-only and unauthenticated. Bind `web_host = "127.0.0.1"` and use SSH tunneling outside a trusted network.

## Deploy

Tagged releases contain an offline ARM64 bundle. See [Pi deployment](../docs/operations/pi-provisioning.md).
