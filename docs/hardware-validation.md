# Hardware validation checklist

Run for every PCB revision and release artifact before enabling RF. Record firmware revision, ELF SHA256, board revision/serial, equipment, operator, date, and evidence.

Current receiver timing configuration is a 16 MHz HSE with PLL x3 for a 48 MHz system clock. CAN uses PA11/PA12 AF4 at 500 kbit/s. HSI48 is the bounded fallback clock source when HSE startup is unavailable.

## Identification

- [ ] MCU is STM32F072R8T6.
- [ ] Schematic and PCB revisions recorded.
- [ ] Firmware revision, CAN node ID, and ELF SHA256 recorded.
- [ ] Rails and logic levels verified.
- [ ] Pull resistors provide RF-safe reset states.

## Power/reset

- [ ] Normal and slow ramps tested.
- [ ] Repeated power cycles tested.
- [ ] Brownout/recovery tested.
- [ ] Watchdog recovery verified.
- [ ] Reset flags and retained diagnostics readable.
- [ ] Invalid retained RAM reinitializes safely.
- [ ] Three incomplete boots trigger safe lockout.
- [ ] New firmware revision clears the prior lockout streak.

## Clock

- [ ] 16 MHz HSE with PLL x3 produces the 48 MHz system clock.
- [ ] Missing HSE uses bounded HSI48 fallback.
- [ ] SPI clocks correct in both modes.
- [ ] Clock-security failure records fault and resets.

## F0480 VGA

Capture CS, SCK, and data.

- [ ] CS idle high.
- [ ] CPOL=0, CPHA=0.
- [ ] Eight clocks per word.
- [ ] 23 dB command is `0x5C`.
- [ ] Data is LSB-first.
- [ ] CS timing meets datasheet.
- [ ] Measured attenuation matches every setting `0..23` dB.
- [ ] PA15 chip select reaches the board's single F0480.
- [ ] Pre-write timeout leaves CS high.
- [ ] In-flight timeout does not intentionally latch partial data before reset.

## PE44820 phase shifter

Capture LE, SCK, data, and serial-select.

- [ ] Serial-select high before programming.
- [ ] LE idle high and low during transfer.
- [ ] CPOL=0, CPHA=0.
- [ ] Thirteen clocks per word.
- [ ] State 146 -> `0x08D`; schematic-selected address 1 -> `0x1628`.
- [ ] Phase/address fields use required order.
- [ ] Representative states match `docs/PE44820_Lookup_2.4GHz.csv`, including OPT.
- [ ] LE timing meets datasheet.
- [ ] Measured phase matches all 256 states or approved sample plan.
- [ ] Pre-write timeout leaves LE high.
- [ ] In-flight timeout does not intentionally latch partial data before reset.

## CAN

- [ ] PA11/AF4 RX and PA12/AF4 TX verified.
- [ ] Transceiver voltage compatibility verified.
- [ ] CANH/CANL/ground connector mapping verified.
- [ ] Two 120-ohm terminators at bus ends.
- [ ] 500 kbit/s and sample point measured.
- [ ] Nodes 1, 2, 3 answer only their unicast pings.
- [ ] Standard-ID and remote frames rejected.
- [ ] Valid unicast gets sequence-matched ACK.
- [ ] Invalid DLC/value gets sequence-matched ERROR.
- [ ] Broadcast safe changes all nodes with no responses.
- [ ] Phase, VGA, and combined single-chain payloads verified.
- [ ] Phase changes apply 23 dB before phase and restore/apply afterward.
- [ ] RX overflow appears in STATUS.
- [ ] TX exhaustion appears in STATUS.
- [ ] Bus-off and recovery verified.
- [ ] Pi completes repeated command cycles without unexpected timeout.
- [ ] RJ11/RJ45 pinouts documented independently of connector type.

## Fault injection

- [ ] Disconnect/hold each SPI line; failure remains bounded.
- [ ] Inject SPI errors; fault codes recorded.
- [ ] HardFault resets and records history.
- [ ] Unused interrupt resets and records history.
- [ ] Watchdog is not refreshed in fault paths.

## Environment/endurance

- [ ] Min/max qualified supply voltage.
- [ ] Intended temperature range.
- [ ] Repeated startup/command cycles.
- [ ] Installation-appropriate EMI test.
- [ ] Deployment-duration or approved accelerated soak.

## Release approval

- [ ] CI passes for exact revision.
- [ ] Tested ELF SHA256 matches archive.
- [ ] Deviations accepted and recorded.
- [ ] Rollback procedure and prior qualified artifact available.
