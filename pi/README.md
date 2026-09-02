# Raspberry Pi controller

Python 3.11 controller for Raspberry Pi 5 on Debian GNU/Linux 13 (`trixie`), CAN node `0`. The deployment bundle carries the pinned `uv` binary and managed Python runtime, so the system Python version is not part of the application contract. Receiver boards use nodes `1..30`; each node controls one RF chain. The printed HAT CAN0 connector is exposed to the application as `beamcan0` by resolving SPI parent `spi1.1`, not by trusting Linux `can0`/`can1` probe order.

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

Production installs expose `beamctl` through `/usr/local/bin`, which is on the normal SSH `PATH`. The CLI defaults to `beamcan0`; use `--iface` only when intentionally targeting another SocketCAN interface.

```bash
beamctl discover
beamctl ping 1
beamctl set-phase 1 --state 128
beamctl set-vga 1 --attenuation 8
beamctl set-combined 1 --state 128 --attenuation 8
beamctl enter-safe 1
```

Validate command parsing and inspect the planned target without opening SocketCAN:

```bash
beamctl set-phase 1 --state 128 --dry-run
make pi-command-smoke
```

Command limits:

| Argument | Range | Meaning |
|:--|:--|:--|
| `node` | `1..30` | Receiver board/CAN node |
| `--state` | `0..255` | Calibrated phase-table index |
| `--attenuation` | `0..23` | F0480 attenuation in dB |
| `--source` | `0` only | Pi controller node |

Common options are `--iface`, `--timeout`, `--retries`, and `--dry-run`. A command
timeout means the final hardware state is unknown; retries reuse the exact sequence and
payload so receiver replay protection can return the prior ACK without repeating writes.

## Dashboard

`beamd` serves FastAPI/Jinja2 status on port `8080`. The initial page is server-rendered; live state arrives over `/events` with Server-Sent Events. Updates are atom-scoped, so unchanged cards are not resent or replaced. Receiver-list structure changes only when discovered nodes change, and the event list changes only when events do.

If SocketCAN opens but no other CAN controller acknowledges transmitted frames, the monitor reports `waiting` instead of exposing the Linux `ENOBUFS` transmission error. This is expected with only the Pi CAN HAT attached. `/healthz` remains healthy while `/readyz` stays `503` until the CAN bus and required receivers are ready.

Dashboard state meanings:

| State | Meaning |
|:--|:--|
| Web online | `beamd` and HTTP server are running |
| CAN online | SocketCAN interface opened successfully |
| CAN waiting | Interface opened, but no receiver is acknowledging frames |
| CAN offline | Interface could not be opened or transport failed |
| Board healthy | Node replied with exact protocol version `3.0.0` |
| Board offline | No valid status reply arrived within timeout/retries |

The dashboard is read-only and unauthenticated. Bind `web_host = "127.0.0.1"` and use SSH tunneling outside a trusted network.

## Deploy

Tagged releases contain an offline ARM64 bundle with `uv`, the managed CPython 3.11 runtime, wheels, and systemd units. See [Pi deployment](../docs/operations/pi-provisioning.md).
