# Raspberry Pi 5 deployment

## Qualified target

| Field | Required |
|:--|:--|
| Hardware | Raspberry Pi 5 |
| Architecture | `aarch64` |
| OS | Debian GNU/Linux 13 (`trixie`) |
| Application Python | uv-managed CPython 3.11, bundled with the release |

The system Python version is not part of the application contract. Other OS releases require requalification and corresponding updates in `pi/deploy/target_platform.py`.

## CI coverage

CI builds the ARM64 offline bundle with the pinned `uv` binary and uv-managed CPython 3.11 runtime, installs it without network access into a clean venv, imports `beamcontrol`, and runs `beamctl --help` and `beamd --help`.

CI does not test device-tree overlays, MCP2515 hardware, the physical CAN bus, SPI-parent interface resolution, or systemd on the target.

## Flash and connect

Use an ARM64 Debian GNU/Linux 13 (`trixie`) image for Raspberry Pi 5. Configure hostname, non-root user, network, and SSH access during imaging or first boot.

```bash
export PI_USER=<user>
export PI_HOST=beamcontrol-pi.local
ssh "$PI_USER@$PI_HOST"
```

Use the Pi's IP address if mDNS is unavailable.

## Provision OS

From the repository root:

```bash
ssh "$PI_USER@$PI_HOST" 'mkdir -p /tmp/beamcontrol-provision'
scp pi/deploy/provision_os.py pi/deploy/target_platform.py \
  "$PI_USER@$PI_HOST:/tmp/beamcontrol-provision/"
ssh -t "$PI_USER@$PI_HOST" \
  'cd /tmp/beamcontrol-provision && sudo python3 provision_os.py'
ssh -t "$PI_USER@$PI_HOST" 'sudo reboot'
```

Provisioning validates Pi 5 + Debian 13 (`trixie`), verifies the base image already provides `/usr/sbin/ip`, configures the CAN overlays, and creates the service account/directories. It does not install Python packages or run `apt-get`; the application runtime comes from the release bundle.

## Obtain a bundle

Preferred: download `beamcontrol-pi-*.tar.gz` and `SHA256SUMS` from a tagged release.

Branch testing: download the 14-day CI artifact:

```bash
gh run download <run-id> --name beamcontrol-pi-<commit-sha> --dir build/deployment
```

Manual networked build on Pi 5:

```bash
git clone https://github.com/uorocketry/beamforming-software.git
cd beamforming-software
make pi-bundle-smoke
```

## Install

```bash
export BUNDLE=build/beamcontrol-pi-<version>.tar.gz
sha256sum "$BUNDLE"
scp "$BUNDLE" "$PI_USER@$PI_HOST:/tmp/"
ssh -t "$PI_USER@$PI_HOST" '
  set -eu
  cd /tmp
  rm -rf beamcontrol-pi-*/
  python3 -m tarfile -e beamcontrol-pi-*.tar.gz .
  sudo python3 ./beamcontrol-pi-*/install.py
'
```

For USB/local transfer, extract with `python3 -m tarfile -e` and run the same `install.py`.

The installer validates Pi 5 + Debian 13 (`trixie`), copies the bundled uv-managed CPython 3.11 runtime under `/opt/uorocketry/python/`, and uses the bundled `uv` binary to create/install the release venv offline. Physical HAT CAN0 is the MCP2515 at SPI parent `spi1.1`; deployment resolves that device and exposes it as the stable application interface `beamcan0`, independent of kernel `can0`/`can1` probe order. It installs versioned application releases under `/opt/uorocketry/beamcontrol/releases/`, switches `current` atomically, exposes `beamctl` at `/usr/local/bin/beamctl`, and installs/enables both services. `beamctl` defaults to `beamcan0`, while `--iface` remains available for diagnostics. Upgrades preserve `/etc/uorocketry/beamcontrol.toml`. Production runs from the system-level `beamcontrol-can.service` and `beamcontrol.service`; do not run a separate repo/user `beamd` service on the same port.

The release venv is created in a staging directory before the release is renamed into place. Python console scripts contain absolute shebangs, so the installer repairs those entrypoints after the rename and before switching `current`; preserve that ordering when changing the installer.

## Configure

```bash
sudo nano /etc/uorocketry/beamcontrol.toml
```

```toml
[beamcontrol]
channel = "beamcan0"
source_node = 0
poll_interval_s = 1.0
can_timeout_s = 0.020
can_retries = 2
nodes = []          # empty: discover nodes 1..30
web_host = "0.0.0.0"
web_port = 8080
```

```bash
sudo systemctl restart beamcontrol.service
```

## Verify

```bash
cat /proc/device-tree/model; echo
uname -m
cat /etc/os-release
/opt/uorocketry/beamcontrol/current/venv/bin/python --version
ip -details -statistics link show beamcan0
systemctl --no-pager --full status beamcontrol-can.service
systemctl --no-pager --full status beamcontrol.service
sudo journalctl -u beamcontrol.service -n 100 --no-pager
beamctl discover
curl --fail http://127.0.0.1:8080/healthz
```

With a receiver attached, expect Pi 5, `aarch64`, Debian GNU/Linux 13 (`trixie`), the application venv on Python 3.11, `beamcan0` at 500 kbit/s, active services, discovered receivers, and `{"status":"ok"}` from `/healthz`.

With no receiver attached, `/healthz` still returns `ok`; dashboard CAN state `waiting` and `/readyz` returning `503` are expected. CAN transmission requires another active controller to assert ACK, so repeated unacknowledged frames can drive the MCP2515 into error-passive state without implying that the Pi HAT itself is faulty.

## Dashboard

Default: `http://beamcontrol-pi.local:8080/`.

The dashboard is read-only and unauthenticated. On untrusted networks:

```toml
web_host = "127.0.0.1"
```

```bash
sudo systemctl restart beamcontrol.service
ssh -L 8080:127.0.0.1:8080 "$PI_USER@$PI_HOST"
```

Endpoints:

| Path | Purpose |
|:--|:--|
| `/api/status` | JSON snapshot |
| `/events` | SSE stream for changed UI atoms |
| `/healthz` | Process liveness |
| `/readyz` | CAN/receiver readiness |
| `/api/docs` | FastAPI docs |

## Troubleshooting

| Symptom | Check | Interpretation/action |
|:--|:--|:--|
| `beamcan0` missing | `systemctl status beamcontrol-can.service` and its journal | Confirm overlays, reboot after provisioning, and verify the HAT SPI parent |
| CAN `waiting` / `ENOBUFS` | Termination, CANH/CANL/ground, receiver power, bitrate | The Pi transmitted without another controller acknowledging the frame |
| Web online, controller offline | `ip link`, both service journals, `/api/status` | HTTP process is healthy but SocketCAN is unavailable |
| Board offline | `beamctl ping <node>` and unique firmware node IDs | Node did not return a valid protocol-3.0 STATUS frame |
| Board reports incompatible version | Reflash the receiver and deploy matching Pi software | Protocol versions must match exactly; there is no compatibility mode |
| Service does not survive reboot | `systemctl is-enabled beamcontrol-can.service beamcontrol.service` | The installer normally enables both units; re-run installation if disabled |
| Dashboard reachable on untrusted LAN | Inspect `web_host` | Bind to `127.0.0.1` and use the documented SSH tunnel |

Useful logs:

```bash
sudo journalctl -b -u beamcontrol-can.service --no-pager
sudo journalctl -b -u beamcontrol.service --no-pager
ip -details -statistics link show beamcan0
```
