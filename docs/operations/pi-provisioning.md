# Raspberry Pi 5 provisioning and deployment

BeamControl is deployed to a Raspberry Pi 5 running the qualified 64-bit
Raspberry Pi OS Bookworm image. The deployment installer rejects other hardware,
non-ARM64 systems, and unsupported Python versions before making system changes.

## Supported target

| Field | Required value |
| --- | --- |
| Computer | Raspberry Pi 5 |
| Architecture | ARM64 (`aarch64`) |
| Distribution | Raspberry Pi OS Lite, 64-bit, Bookworm |
| Python | 3.11 |
| Qualified image | `2025-05-13-raspios-bookworm-arm64-lite.img.xz` |
| Image SHA256 | `62d025b9bc7ca0e1facfec74ae56ac13978b6745c58177f081d39fbb8041ed45` |

The offline bundle is built for Python 3.11. Moving to another Raspberry Pi OS
release requires rebuilding and requalifying the bundle and updating the OS check
in `pi/deploy/provision_os.py`.

## What CI verifies

Every pull request and `main` push builds the real ARM64 offline bundle on a
GitHub-hosted ARM64 runner. CI extracts the archive, installs every dependency
from its wheelhouse into a clean Python 3.11 virtual environment without network
access, imports `beamcontrol`, and runs `beamctl --help` and `beamd --help`.

CI cannot emulate Raspberry Pi device-tree overlays, the MCP2515 controllers,
physical CAN wiring, `can0`, or systemd startup on the flight computer. Those are
covered by the verification steps at the end of this guide.

## Flash the Pi and enable SSH

1. Verify the downloaded image before flashing:

   ```bash
   echo "62d025b9bc7ca0e1facfec74ae56ac13978b6745c58177f081d39fbb8041ed45  2025-05-13-raspios-bookworm-arm64-lite.img.xz" | sha256sum --check
   ```

2. In Raspberry Pi Imager, choose **Use custom** and select the qualified image.
3. In the Imager customization screen:
   - set a hostname such as `beamcontrol-pi`;
   - create a non-root user;
   - configure Wi-Fi or plan to use Ethernet;
   - enable SSH, preferably with your public key.
4. Boot the Pi 5 and connect from your development computer:

   ```bash
   ssh <user>@beamcontrol-pi.local
   ```

   When multicast DNS is unavailable, find the Pi's address from your router and
   connect with `ssh <user>@<ip-address>`.

The examples below use these local shell variables:

```bash
export PI_USER=<user>
export PI_HOST=beamcontrol-pi.local
```

## Provision over SSH

From the repository root on your development computer:

```bash
ssh "$PI_USER@$PI_HOST" 'mkdir -p /tmp/beamcontrol-provision'
scp pi/deploy/provision_os.py pi/deploy/target_platform.py \
  "$PI_USER@$PI_HOST:/tmp/beamcontrol-provision/"
ssh -t "$PI_USER@$PI_HOST" \
  'cd /tmp/beamcontrol-provision && sudo python3 provision_os.py'
ssh -t "$PI_USER@$PI_HOST" 'sudo reboot'
```

The provisioning script verifies the Raspberry Pi 5 model and Bookworm, installs
`python3`, `python3-venv`, `can-utils`, and `iproute2`, configures the CAN device-
tree overlays, and creates the `beamcontrol` service account and directories.
The SSH connection will close during reboot.

Reconnect after the Pi comes back:

```bash
ssh "$PI_USER@$PI_HOST"
```

## Obtain a deployment bundle

### Tagged release, recommended for deployment

Pushing a version tag such as `v0.1.0` automatically runs the complete release
workflow and publishes firmware plus `beamcontrol-pi-*.tar.gz` on the repository's
GitHub Releases page. The tag must match the version in `pi/pyproject.toml`.

Download the archive and its `SHA256SUMS` file to your development computer, then
verify it before copying it to the Pi.

### CI artifact, useful for testing a branch

Every CI run uploads a 14-day artifact named `beamcontrol-pi-<commit-sha>`. In the
GitHub web interface, open **Actions**, select the CI run, and download the artifact
from the run summary.

With GitHub CLI, a specific run can be downloaded with:

```bash
gh run download <run-id> --name beamcontrol-pi-<commit-sha> --dir build/deployment
```

CI artifacts are intended for testing commits. Prefer a tagged release for the
flight image.

### Build directly on the Pi 5

For a manual networked build, clone the repository on the Pi and run:

```bash
git clone https://github.com/uorocketry/beamforming-software.git
cd beamforming-software
make pi-bundle-smoke
```

The command builds the archive and verifies a clean offline installation before
returning. The resulting archive is written under `build/`. This path downloads
build-time Python dependencies; the deployment archive itself installs offline.

## Install the bundle over SSH

On the development computer, set `BUNDLE` to the downloaded archive:

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

The installer verifies Raspberry Pi 5, ARM64, and Python 3.11; installs the wheel
and dependencies into a versioned virtual environment under
`/opt/uorocketry/beamcontrol/releases/`; updates the `current` symlink atomically;
and installs, enables, and starts both systemd units.

## Fully manual installation on the Pi

When the archive reaches the Pi through a USB drive or another transfer method:

```bash
mkdir -p ~/beamcontrol-install
cd ~/beamcontrol-install
cp /path/to/beamcontrol-pi-*.tar.gz .
python3 -m tarfile -e beamcontrol-pi-*.tar.gz .
sudo python3 ./beamcontrol-pi-*/install.py
```

No SSH-specific behavior is required. The same installer performs the target and
version checks.

## Configure nodes

Edit the installed configuration:

```bash
sudo nano /etc/uorocketry/beamcontrol.toml
```

The default structure is:

```toml
[beamcontrol]
channel = "can0"
source_node = 0
poll_interval_s = 1.0
# Empty means discover all receiver-board nodes 1 through 30.
nodes = []
web_host = "0.0.0.0"
web_port = 8080
```

Restart the daemon after changing configuration:

```bash
sudo systemctl restart beamcontrol.service
```

## Verify the installation

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
```

Expected results:

- the model starts with `Raspberry Pi 5 Model`;
- the architecture is `aarch64`;
- Python is 3.11;
- `can0` is `UP` at 500 kbit/s;
- both services are active without restart loops;
- `beamctl discover` reports the connected receiver nodes; and
- the dashboard health endpoint returns `{"status":"ok"}`.

Physical CAN verification should also include `candump can0` while commands and
status frames are being exchanged.

## Open the web dashboard

The default configuration listens on port `8080` on every Pi network interface:

```text
http://beamcontrol-pi.local:8080/
```

The dashboard is read-only but does not provide authentication. Use it only on a trusted
network. For localhost-only access, set:

```toml
web_host = "127.0.0.1"
```

Then restart the service and create an SSH tunnel from the operator computer:

```bash
sudo systemctl restart beamcontrol.service
ssh -L 8080:127.0.0.1:8080 <user>@beamcontrol-pi.local
```

Open `http://127.0.0.1:8080/` locally. Other useful endpoints are:

| Endpoint | Purpose |
|:--|:--|
| `/api/status` | Complete JSON status snapshot |
| `/healthz` | Web-process liveness |
| `/readyz` | `200` only when CAN and required receivers are healthy |
| `/api/docs` | FastAPI endpoint documentation |

## Upgrade

Install a newer verified bundle using the same extraction and `install.py` steps.
Releases are stored in versioned directories and the `current` symlink is switched
atomically. Existing `/etc/uorocketry/beamcontrol.toml` configuration is preserved.
