# Repository instructions

## Protocol and API changes

- Implement one current protocol and one current API.
- Do not add backward-compatibility paths, legacy fallbacks, dual-format decoding, deprecated aliases, migration shims, or compatibility wrappers unless the user explicitly requests them.
- Do not preserve old wire layouts, payload padding rules, status formats, numeric values, or function signatures solely for compatibility.
- Breaking changes are allowed on active development branches. Update firmware, clients, tools, tests, simulation, and documentation together.
- Prefer exact payload lengths and one canonical code path.
- Remove superseded code instead of retaining it behind feature checks or version branches.

## Reference code

- Use only repositories, branches, or implementations named by the user.
- Do not inspect unrelated rewrites as design references unless the user explicitly asks.

## Firmware layout

- Keep production firmware under `stm32/app/src/{can,rf,platform}` with matching headers under `stm32/app/include/`.
- Keep board GPIO and alternate-function assignments in `platform/board.h`.
- Do not track bench experiments or captured media in the software repository; store them with hardware validation records or release artifacts.
- Name modules by responsibility: CAN transport/codec, RF planning/execution, or platform support.
