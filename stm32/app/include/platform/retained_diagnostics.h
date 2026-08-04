#ifndef RETAINED_DIAGNOSTICS_H
#define RETAINED_DIAGNOSTICS_H

#include "platform/diagnostic_record.h"

#include <stdbool.h>
#include <stdint.h>

void retained_diagnostics_begin(uint32_t reset_flags, uint32_t build_id);
bool retained_diagnostics_lockout_required(void);
void retained_diagnostics_set_state(firmware_state_t state);
void retained_diagnostics_set_clock(firmware_clock_t clock_source);
void retained_diagnostics_set_commands(
    uint16_t phase_command,
    uint8_t vga_command);
void retained_diagnostics_set_fault(firmware_fault_t fault);
void retained_diagnostics_mark_healthy(void);

#endif
