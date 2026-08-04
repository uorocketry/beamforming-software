# Developer setup

Supported host: Linux. On Windows, use Ubuntu in WSL2 and clone inside the WSL filesystem.

## Install

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install --yes build-essential git make python3

git clone https://github.com/uorocketry/beamforming-software.git
cd beamforming-software
make setup
make doctor
make test
make firmware NODE=1
```

Host Python must be 3.10+; the project environment is Python 3.11.

`make setup` is idempotent and writes only to:

- `.tools/`: `uv`, ARM toolchain, caches
- `stm32/.deps/`: libopencm3
- `pi/.venv/`: Python environment

It does not install OS packages, modify system Python, or use `sudo`. Root setup requires `ALLOW_ROOT_SETUP=1`.

Remove generated tools and builds:

```bash
make distclean
```

## WSL2

```powershell
wsl --install -d Ubuntu
```

Use a path such as `~/src/beamforming-software`, not `/mnt/c/...`.

## Diagnostics

```bash
make doctor     # read-only checks
make help
make quickstart # setup + doctor + host tests
```

Optional packages:

```bash
sudo apt install --yes can-utils cppcheck iproute2
```

- `can-utils`: physical CAN inspection
- `cppcheck`: `make stm32-static`
- `iproute2`: configure SocketCAN links

Run `make stm32-sanitize` for ASan/UBSan native tests or `make stm32-verify` for all extended firmware checks.

After setup, tests and firmware builds use local caches. A fresh checkout still needs network access. Pi deployment uses an offline bundle.
