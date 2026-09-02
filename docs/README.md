# Documentation

- [Overview](overview.md): command path and test layers
- [Project status](project-status.md): completed work, qualification boundary, and next steps
- [CAN protocol v3.0](can-protocol.md): wire contract
- [RF encoding](rf-control.md): PE44820/F0480 commands and ACK limits
- [Hardware validation](hardware-validation.md): release and PCB checks
- [Developer setup](operations/developer-setup.md)
- [Pi deployment](operations/pi-provisioning.md)
- [Releases](operations/releases.md)
- [Virtual E2E](../simulation/README.md)
- [Pi controller](../pi/README.md)
- [STM32 firmware](../stm32/README.md)

Reference files:

- `pere_s_a0006625230_1-2279326.pdf`: PE44820
- `REN_F0480_DST_20150427_1.pdf`: F0480
- `PE44820_Lookup_2.4GHz.csv`: calibrated phase lookup

The STM32F072 peripheral reference manual is ST RM0091. RM0360 covers the
STM32F030/F070 families and must not be used to resolve STM32F072 peripheral details.
