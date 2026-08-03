# BeamControl documentation

These documents describe the software and firmware contained in this repository.

## System model

```text
Operator / browser / beamctl
            |
Raspberry Pi 5 + CAN HAT       controller node 0
            |
        CAN 2.0B bus
            |
STM32 receiver board           receiver node 1..30
  |- RF channel 0
  |- RF channel 1
  |- RF channel 2
  `- RF channel 3
```

One complete STM32 receiver board is one CAN node. Its four RF paths are channels inside that
node. Board-local components such as phase shifters and DVGAs are not CAN nodes.

## Documents

- [Project overview](overview.md) — architecture, original STM32 comparison, command flow, simulation, and test scope
- [CAN protocol v1.1](can-protocol.md) — implemented Python/C wire contract
- [RF control encoding](rf-control.md) — PE44820 and F0480 serial command formation and ACK limits
- [Firmware](firmware.md) — STM32 target and build entry points
- [Developer setup](operations/developer-setup.md) — local environment and checks
- [Raspberry Pi 5 deployment](operations/pi-provisioning.md) — installation and verification
- [Release process](operations/releases.md) — CI artifacts and tagged releases
- [Virtual end-to-end simulation](../simulation/README.md) — Docker, SocketCAN, and Renode

Component-specific details are also documented next to their code:

- [Raspberry Pi controller](../pi/README.md)
- [STM32 receiver firmware](../stm32/README.md)

Component datasheets used to verify the RF serial encoders are stored alongside these docs:

- [PE44820 digital phase shifter](pere_s_a0006625230_1-2279326.pdf)
- [IDT/Renesas F0480 RF DVGA](REN_F0480_DST_20150427_1.pdf)
