# Contributing

Keep changes small, tested, and reviewable.

## Layout

- `pi/`: Python 3.11 controller, `beamctl`, `beamd`
- `stm32/`: STM32F072 firmware in C/libopencm3
- `protocol/`: shared Python/C vectors
- `simulation/`: Docker, SocketCAN, Renode E2E
- `tools/`: setup, generators, bundles
- `docs/`: protocol, RF, operations

## Commands

Use the root `Makefile`:

```bash
make setup
make doctor
make test
make check
make firmware NODE=1
```

Before a PR:

- Run `make check`.
- Add Python tests under `pi/tests/`.
- For protocol changes, edit `protocol/v2.1-vectors.toml` and run `python3 tools/generate-protocol-vectors.py`.
- Keep queue/priority logic in host-testable `can_tx_queue.c/h`.

## Style

- Python: Ruff, 100 columns, Python 3.11.
- C: C2x, `-Wall -Wextra -Werror -pedantic`.
- Markdown: direct, concise, no duplicated explanations.
- Repository automation: Python, not new shell scripts.

## Managed dependencies

`make setup` installs pinned tools only in gitignored paths:

- `.tools/`: `uv`, ARM GNU toolchain, caches
- `stm32/.deps/`: libopencm3
- `pi/.venv/`: Python environment

libopencm3 is pinned in `stm32/third_party/libopencm3.lock`.

## Releases

CI builds a temporary ARM64 Pi bundle. A matching `v<version>` tag creates a GitHub Release. See [releases](docs/operations/releases.md).
