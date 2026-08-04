# Raspberry Pi controller

Python 3.11 software for the Raspberry Pi 5 CAN controller.

The Pi is CAN node `0`. It communicates with complete STM32 receiver boards at node IDs
`1..30`. Each receiver board contains four RF channels (`0..3`).

## Package

`src/beamcontrol/` provides:

- `BeamControlClient` for commands, retries, discovery, and response matching;
- `SocketCanTransport` using Linux SocketCAN through `python-can`;
- `beamctl` for operator and diagnostic commands;
- `beamd` for periodic receiver status and the read-only web dashboard;
- TOML configuration loading.

The Pi CAN HAT is controlled by the Linux MCP2515 driver. `can_setup.py` uses `ip` to bring
up `can0` at 500 kbit/s and an 87.5% sample point.

## Develop

```bash
make setup
make pi-test
make pi-lint
```

Development installs the package only in `pi/.venv`; it does not register a system daemon.

## Commands

```bash
beamctl discover
beamctl ping 1
beamctl set-phase 1 --states 128 64 32 16
beamctl set-vga 1 --attenuations 8 9 10 11
beamctl set-combined 1 --states 64 65 66 67 --attenuations 12 13 14 15
beamctl enter-safe 1 --channel 2
```

The first number is the receiver-board CAN node. Bulk commands require four values in channel
order. `--channel` is used only by the one-channel safe command.

## Web dashboard

`beamd` serves a compact FastAPI/Jinja2/HTMX dashboard with:

- Raspberry Pi service uptime and configuration;
- SocketCAN interface state;
- discovered receiver-board protocol and health information; and
- recent monitor events.

The CAN monitor runs in a background thread inside the same `beamd` process as Uvicorn, so
the dashboard does not create a second CAN client. CAN or receiver failures keep the page
online, mark the system degraded/offline, and cause `/readyz` to return `503`.

The first version is read-only. It has no phase, attenuation, reboot, or service-control
actions. By default the deployed configuration listens on all interfaces at port `8080`:

```text
http://beamcontrol-pi.local:8080/
```

Only expose this unauthenticated status page on a trusted network. Set `web_host` to
`127.0.0.1` and use an SSH tunnel when remote network access is not appropriate.

## Deploy to Raspberry Pi 5

Tagged releases contain an offline ARM64 bundle:

```bash
scp beamcontrol-pi-*.tar.gz <user>@beamcontrol-pi.local:/tmp/
ssh <user>@beamcontrol-pi.local \
  'cd /tmp && python3 -m tarfile -e beamcontrol-pi-*.tar.gz . && sudo python3 ./beamcontrol-pi-*/install.py'
```

The installer creates a versioned venv under `/opt/uorocketry/beamcontrol/`, installs the
systemd services, and preserves the existing configuration on upgrades.

See the full [Raspberry Pi 5 deployment guide](../docs/operations/pi-provisioning.md).
