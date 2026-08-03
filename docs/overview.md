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

Each board contains four RF channels, numbered `0` through `3`. A command therefore identifies:

1. the receiver-board CAN node; and
2. the channel inside that board when the operation is channel-specific.

Phase shifters, amplifiers, filters, detectors, and antenna elements are components of a board,
not CAN nodes.

## Example command path

```text
beamctl set-phase 1 --channel 2 --state 128
        |
        | CAN command to receiver node 1
        v
STM32 validates the request
        |
        | SPI and GPIO transaction
        v
Phase shifter for channel 2 is programmed
        |
        | CAN ACK
        v
Pi confirms that the command completed
```

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
