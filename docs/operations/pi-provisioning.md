# Raspberry Pi 5 deployment

## Qualified target

| Field | Required |
|:--|:--|
| Hardware | Raspberry Pi 5 |
| Architecture | `aarch64` |
| OS | Raspberry Pi OS Lite 64-bit, Bookworm |
| Python | 3.11 |
| Image | `2025-05-13-raspios-bookworm-arm64-lite.img.xz` |
| SHA256 | `62d025b9bc7ca0e1facfec74ae56ac13978b6745c58177f081d39fbb8041ed45` |

Other OS releases require a rebuilt/requalified bundle and updated checks in `pi/deploy/provision_os.py`.

## CI coverage

CI builds the ARM64 offline bundle, installs it without network access into a clean Python 3.11 venv, imports `beamcontrol`, and runs `beamctl --help` and `beamd --help`.

CI does not test device-tree overlays, MCP2515 hardware, physical CAN, `can0`, or systemd on the target.

## Flash and connect

Verify the image:

```bash
echo "62d025b9bc7ca0e1facfec74ae56ac13978b6745c58177f081d39fbb8041ed45  2025-05-13-raspios-bookworm-arm64-lite.img.xz" | sha256sum --check
```

Flash it with Raspberry Pi Imager **Use custom**. Set hostname, non-root user, network, and SSH key.

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

Provisioning validates the target, installs Python/venv, `can-utils`, and `iproute2`, configures CAN overlays, and creates the service account/directories.

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

The installer validates Pi 5/ARM64/Python 3.11, installs a versioned release under `/opt/uorocketry/beamcontrol/releases/`, switches `current` atomically, and installs/enables both services. Upgrades preserve `/etc/uorocketry/beamcontrol.toml`.

## Configure

```bash
sudo nano /etc/uorocketry/beamcontrol.toml
```

```toml
[beamcontrol]
channel = "can0"
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
python3 --version
ip -details -statistics link show can0
systemctl --no-pager --full status beamcontrol-can.service
systemctl --no-pager --full status beamcontrol.service
sudo journalctl -u beamcontrol.service -n 100 --no-pager
/opt/uorocketry/beamcontrol/current/venv/bin/beamctl discover
curl --fail http://127.0.0.1:8080/healthz
candump can0
```

Expected: Pi 5, `aarch64`, Python 3.11, `can0` up at 500 kbit/s, active services, discovered receivers, and `{"status":"ok"}`.

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
| `/healthz` | Process liveness |
| `/readyz` | CAN/receiver readiness |
| `/api/docs` | FastAPI docs |
