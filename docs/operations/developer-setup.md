# Developer setup

The supported development environment is Linux. Windows developers use WSL2
with an Ubuntu distribution; native Windows is not supported.

## Linux

Install the small set of host prerequisites. On Debian or Ubuntu:

```bash
sudo apt update
sudo apt install --yes build-essential git make python3
```

Clone the repository and run the repository-managed setup:

```bash
git clone https://github.com/uorocketry/beamforming-software.git
cd beamforming-software
make setup
make doctor
make test
make firmware NODE=1
```

`make setup` is idempotent. Before changing anything, it prints the directories
it will use and refuses to run as root unless `ALLOW_ROOT_SETUP=1` is set for an
intentional root-owned container. It installs pinned tooling and dependencies
only in repository-local, gitignored directories:

- `.tools/` for `uv`, the ARM GNU toolchain, uv's cache, and any uv-managed
  Python interpreter;
- `stm32/.deps/` for libopencm3; and
- `pi/.venv/` for the Python environment.

The bootstrap host interpreter must be Python 3.10 or newer. BeamControl itself
supports Python 3.11 only, and `make setup` creates a Python 3.11 project
environment. Setup does not use `sudo`, install OS packages, modify system
Python, write to uv's normal per-user cache, or replace a system compiler.

To remove every downloaded development tool, dependency, environment, cache,
and build output, run:

```bash
make distclean
```

This is the development equivalent of an uninstall. It only removes generated
paths inside the repository and leaves source files untouched.

## Windows with WSL2

From an elevated PowerShell prompt:

```powershell
wsl --install -d Ubuntu
```

Then open Ubuntu and follow the Linux instructions above. Clone the repository
inside the WSL filesystem, for example `~/src/beamforming-software`. Avoid
working under `/mnt/c/...`; Windows-mounted paths are slower and can cause file
permission or executable-bit problems.

## Diagnostics

`make doctor` is read-only. It reports required build blockers separately from
optional capabilities such as `cppcheck`, `ip`, `can-utils`, and a live
`can0` SocketCAN interface.

```bash
make doctor
```

`make help` lists the stable command interface:

```bash
make help
```

For a new checkout, `make quickstart` runs setup, diagnostics, and the host test
suite in sequence.

## Optional packages

Install these only for the associated workflows:

```bash
sudo apt install --yes can-utils cppcheck iproute2
```

- `can-utils` provides tools such as `candump` for physical CAN testing.
- `cppcheck` is used by `python3 stm32/scripts/verify.py`.
- `iproute2` provides `ip`, which configures the Linux `can0` interface. Python
  sends and receives frames through SocketCAN after the interface is configured;
  the standard library does not provide a high-level replacement for CAN
  bitrate, sample-point, and link-state configuration.

The offline Raspberry Pi bundle is a gzip-compressed tar archive created and
extracted with Python's standard-library `tarfile` module. It does not require
external `tar`, `gzip`, or `zstd` commands.

## Offline use

After `make setup` has completed, normal tests and firmware builds use the
repository-local pinned toolchain and cached Python dependencies. Creating a
fresh checkout or rebuilding a missing dependency still requires network access.
The flight Raspberry Pi deployment path is separately packaged as an offline
bundle; see [Pi provisioning](pi-provisioning.md).
