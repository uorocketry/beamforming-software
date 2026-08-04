# BeamControl overview

BeamControl separates Pi supervision from deterministic STM32 RF control. One receiver board is one CAN node; its four RF channels are local peripherals.

## Command path

```mermaid
sequenceDiagram
    participant Operator as beamctl
    participant Pi as Pi client
    participant STM32 as STM32 receiver
    participant RF as RF devices

    Operator->>Pi: Individual or bulk command
    Pi->>STM32: CAN request
    STM32->>STM32: Decode, validate, plan
    STM32->>RF: SPI/GPIO writes
    STM32-->>Pi: ACK or ERROR
    Pi-->>Operator: Result
```

ACK confirms STM32 transfer completion, not RF-device readback. `beamd` continuously discovers boards and serves the read-only status dashboard.

## Test layers

| Layer | Coverage |
|:--|:--|
| Unit/contract | Python and native C logic |
| Renode E2E | Pi client, SocketCAN, STM32 ELF, SPI/GPIO |
| ARM64 bundle | Offline Pi installation |
| Hardware validation | Electrical timing, wiring, RF performance |

Run `make check` for static/unit/build gates and `make simulation-test` for Renode E2E.
