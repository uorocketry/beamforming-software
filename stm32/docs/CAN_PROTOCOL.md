# STM32 CAN protocol

The canonical implemented specification is [`../../docs/can-protocol.md`](../../docs/can-protocol.md).

The STM32 firmware implements protocol 2.0 with four-channel bulk RF payloads:

```text
SET_PHASE     [PS1, PS2, PS3, PS4]
SET_VGA       [VGA1, VGA2, VGA3, VGA4]
SET_COMBINED  [PS1, PS2, PS3, PS4, VGA1, VGA2, VGA3, VGA4]
ENTER_SAFE    [zero-based channel]
```

The four phase bytes are calibrated phase-enum indexes. Firmware maps channel indexes `0..3`
to PE44820 serial addresses `1..4`, constructs each 13-bit command with `MakePSCommand()`, and
uses the safe attenuation/phase/restore ordering documented in the canonical specification.

The four VGA bytes are attenuation requests in integer dB, each `0..23`. The control planner
retains the channel number with every F0480 operation. The checked-in board driver currently
documents only the shared SPI1 bus and PA4 CS line; a board-specific four-device selector map
must be supplied from the final PCB net assignment rather than guessed in firmware.

An ACK confirms STM32-side validation and transmit completion only. Neither RF interface has a
return-data line on this PCB, so ACK does not mean RF-device acknowledgement or measured-state
verification.
