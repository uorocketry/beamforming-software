# STM32 CAN protocol

Canonical specification: [`../../docs/can-protocol.md`](../../docs/can-protocol.md).

Protocol 2.1 supports exact-length individual and bulk payloads:

```text
SET_PHASE     [state, channel] | [PS1, PS2, PS3, PS4]
SET_VGA       [atten, channel] | [VGA1, VGA2, VGA3, VGA4]
SET_COMBINED  [state, channel, atten] | [PS1..PS4, VGA1..VGA4]
ENTER_SAFE    [channel]
```

Channels are zero-based; PE44820 addresses are `1..4`. Phase changes use attenuation, phase, restore/apply ordering.

The F0480 operation retains its channel, but the checked-in board map names only SPI1 and PA4 CS. Add the final selector-net mapping in the driver; do not guess GPIOs.

ACK confirms STM32 validation and SPI completion, not RF-device readback.
