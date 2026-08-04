# BeamControl overview

## 30-second explanation

BeamControl lets a Raspberry Pi control one or more four-channel RF receiver boards over CAN.
The Pi is the controller and hosts the command-line tools, status monitor, and web dashboard.
Each receiver board has one STM32 microcontroller that receives CAN commands and programs the
board's phase shifters and attenuation hardware over SPI.

```text
Operator or browser
        |
Raspberry Pi 5                  CAN node 0
        |
       CAN
        |
STM32 receiver board            CAN node 1..30
  |- RF channel 0
  |- RF channel 1
  |- RF channel 2
  `- RF channel 3
```

A complete receiver board is one CAN node. The four RF paths are channels inside that node;
they are not separate CAN nodes.

## What each part does

### Raspberry Pi controller

The Pi runs the Python software:

- `beamd` monitors receiver boards and serves the read-only web dashboard;
- `beamctl` sends operator commands and diagnostics; and
- SocketCAN provides the connection to the physical CAN HAT.

The Pi uses CAN node address `0`.

### STM32 receiver board

Each receiver board runs the STM32F072 firmware and has a unique CAN node address from `1` to
`30`. The firmware:

- validates incoming commands;
- controls phase and attenuation through SPI and GPIO;
- attenuates before changing phase to reduce unsafe output transitions;
- returns ACK, ERROR, and STATUS messages;
- handles retries without repeating an already completed operation; and
- uses watchdog recovery and retained fault diagnostics.

### RF channels and components

Each board contains four RF channels. The bulk phase, VGA, and combined commands provide four
values in a fixed channel order, while `ENTER_SAFE` identifies one zero-based channel `0..3`.
Phase shifters, amplifiers, filters, detectors, and antenna elements are components of a board,
not CAN nodes.

## Example command path

```text
beamctl set-phase 1 --states 128 64 32 16
        |
        | four phase indexes in one CAN command to receiver node 1
        v
STM32 validates the complete payload before planning any hardware writes
        |
        | attenuate active outputs, then program PE44820 addresses 1..4
        v
All four requested phase states are transmitted in channel order
        |
        | CAN ACK after STM32-side SPI completion
        v
Pi confirms completion of the local transmit sequence
```

## What was added beyond the original STM32 prototype

The original `stm32beamforming` code was a hardware bring-up program. It configured SPI,
wrote one hard-coded phase-shifter command, and then stopped. The VGA driver was present, but
the active program did not initialize or use it.

BeamControl keeps the same basic SPI device-control idea and expands it into production-style
receiver firmware:

| Area | Original STM32 prototype | BeamControl |
|:--|:--|:--|
| Main behavior | Sends one phase command and stops | Runs continuously as a CAN-controlled receiver node |
| Remote control | None | CAN commands for discovery, phase, attenuation, combined updates, and safe mode |
| Addressing | Hard-coded local device address | Receiver-board node `1..30` plus RF channel `0..3` |
| VGA use | Driver existed but was unused by `main` | Initialized at boot and controlled through CAN |
| SPI completion | Wrote data and raised latch/CS immediately | Waits for TX-ready and transfer completion with bounded timeouts |
| Safe phase changes | None | Applies maximum attenuation before changing phase, then restores attenuation |
| Validation | Minimal | Checks CAN IDs, frame type, lengths, ranges, reserved bytes, and broadcast rules |
| Retries | None | Sequence numbers and replay handling avoid repeating completed RF operations |
| Fault handling | Debug breakpoint or infinite loop | Records faults, resets, and can enter safe lockout after repeated incomplete boots |
| Watchdog | None | Independent watchdog supervises the running firmware |
| Diagnostics | None | Boot count, reset flags, fault history, clock source, and last RF commands are retained |
| CAN robustness | No CAN | Acceptance filters, RX/TX queues, priorities, retransmission, and bus-off recovery |
| Testing | Manual hardware experiments | Native C tests, Python/C protocol tests, cross-builds, and Docker/Renode E2E simulation |

The project also corrected issues present in the old codebase, including a phase-conversion
integer-division error, inconsistent function types that prevented modern compilation, and
raising SPI latch signals without explicitly waiting for the transfer to finish.

In simple terms, the original code proved that the STM32 could talk to the RF control chips.
BeamControl turns that proof of concept into a remotely operated, continuously supervised,
testable receiver-board controller.

The current firmware is still not a substitute for hardware qualification. The board does not
route a return data line from either RF control device to the STM32. A CAN ACK therefore means
the STM32 completed its validated transmit sequence, not that an RF device acknowledged the
word or that the resulting RF state was measured. Real SPI timing, CAN electrical behavior,
and RF performance must still be measured on the board.

## Web dashboard

`beamd` serves a compact FastAPI/Jinja2/HTMX dashboard. It shows:

- Pi and service status;
- CAN availability;
- receiver-board health;
- protocol versions and response times; and
- recent monitor events.

The current dashboard is read-only. It remains available when CAN hardware or receiver boards
are offline so it can explain the failure state.

## Virtual end-to-end simulation

The repository can run the controller and the actual compiled STM32 firmware without physical
boards:

```text
Docker Compose
  |- real beamd and dashboard
  |- container-local SocketCAN vcan0
  |- Renode running the real STM32 ELF
  `- automated end-to-end assertions
```

Run it with:

```bash
make simulation-test
```

The test verifies that real CAN commands reach the real firmware, produce the expected ACKs,
and become the expected SPI and GPIO writes. It covers discovery, phase, attenuation, combined
safe transitions, safe mode, and dashboard health.

## What the simulation proves

It verifies the software path end to end:

```text
Python controller -> SocketCAN -> STM32 firmware -> SPI/GPIO behavior -> CAN response
```

It does not verify electrical or RF behavior such as voltage levels, RF phase accuracy, signal
integrity, CAN termination, oscillator tolerance, brownouts, or physical component failures.
Those require hardware-in-the-loop and RF acceptance testing.

## Testing layers

| Layer | Purpose |
|:--|:--|
| Unit and protocol tests | Check Python and C logic quickly |
| Docker + Renode simulation | Exercise the real controller and STM32 firmware together |
| ARM64 deployment test | Verify the offline Raspberry Pi bundle |
| Physical hardware test | Validate CAN electrical behavior, GPIO/SPI timing, and RF performance |

## Simple demonstration

```bash
make simulation-test
```

A successful run demonstrates that:

1. the virtual CAN bus starts;
2. the real STM32 firmware boots in Renode;
3. the real Pi controller discovers receiver node `1`;
4. phase, attenuation, combined, and safe commands are acknowledged;
5. the expected SPI/GPIO transactions occur; and
6. the dashboard reports the receiver as healthy.

The main message is:

> BeamControl separates high-level supervision on the Raspberry Pi from deterministic,
> safety-aware RF control on each STM32 receiver board, and the complete software path is
> tested automatically before physical hardware testing.
