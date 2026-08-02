# Contributing

Thanks for helping with the uORocketry BeamControl beamforming software. This is a small
team project, so keep changes minimal and reviewable.

## Repo layout

- `pi/` — Raspberry Pi CAN controller (Python, `src/beamcontrol` package, console entry points `beamctl` and `beamd`).
- `stm32/` — STM32 embedded firmware (C, libopencm3). CAN protocol v1.1 + prioritized TX queue.
- `docs/` — project knowledge base (protocol spec, hardware, operations).
- `protocol/` — shared, language-neutral protocol test vectors.
- `tools/` — repo orchestration (toolchain/dependency fetch, generators, bundle builder).

## The one command interface

Everything runs through the root `Makefile`. Do not scatter setup instructions.

```bash
make setup     # fetch pinned uv + ARM toolchain + libopencm3, sync Python env
make doctor    # diagnose required and optional environment capabilities
make test      # pi tests + native firmware unit tests + protocol contract
make check     # lint + tests + one representative firmware build
make firmware NODE=1
```

## Before you open a PR

- `make check` must pass clean (lint, all tests, and a representative firmware build).
- New/edited Python must be covered by a test in `pi/tests/` (unit with a fake
  transport, or integration on the virtual CAN bus).
- Protocol changes must update `protocol/v1.1-vectors.toml` and regenerate the
  C header: `python3 tools/generate-protocol-vectors.py`. Both Python and C
  tests consume the same vectors, so they cannot silently drift.
- Firmware queue/priority logic goes in `can_tx_queue.c/h` (host-testable), not
  buried in `can_bus.c`.

## Style

- Python: `ruff` (see `pi/pyproject.toml`), line length 100, target 3.11.
- C: `-Wall -Wextra -Werror`, the firmware never builds with warnings.
- No em dashes in prose; keep messages human and direct.

## Dependencies

- `libopencm3` is pinned by commit + SHA256 in `stm32/third_party/libopencm3.lock`
  and fetched by `tools/fetch_libopencm3.py` into gitignored `stm32/.deps/`.
- The ARM cross-toolchain is fetched into gitignored `.tools/` by
  `tools/fetch_arm_toolchain.py`.
- `make setup` bootstraps the pinned `uv` binary into `.tools/`; only a host
  Python 3.10+ interpreter and the documented OS packages are needed first.
- Repository automation is Python. Do not add new shell scripts.

## Releases

Normal CI builds and smoke-tests the ARM64 Raspberry Pi 5 deployment bundle and
uploads it as a temporary artifact. Permanent GitHub Releases are created
automatically when a `v<version>` tag matching `pi/pyproject.toml` is pushed.
See [`docs/operations/releases.md`](docs/operations/releases.md).
