#include "platform/retained_diagnostics.h"

/* Global so a debugger can inspect retained state after reset. */
volatile diagnostic_record_t RETAINED_DIAGNOSTICS
    __attribute__((section(".noinit.retained_diagnostics"), used));

static diagnostic_record_t valid_record(void)
{
    diagnostic_record_t record = RETAINED_DIAGNOSTICS;
    if (!diagnostic_record_is_valid(&record)) {
        record = diagnostic_record_new();
    }

    return record;
}

void retained_diagnostics_begin(uint32_t reset_flags, uint32_t build_id)
{
    const diagnostic_record_t previous = RETAINED_DIAGNOSTICS;
    RETAINED_DIAGNOSTICS =
        diagnostic_record_begin_boot(&previous, reset_flags, build_id);
}

bool retained_diagnostics_lockout_required(void)
{
    const diagnostic_record_t record = RETAINED_DIAGNOSTICS;
    return diagnostic_record_should_lockout(&record);
}

void retained_diagnostics_set_state(firmware_state_t state)
{
    diagnostic_record_t record = valid_record();
    diagnostic_record_set_state(&record, state);
    RETAINED_DIAGNOSTICS = record;
}

void retained_diagnostics_set_clock(firmware_clock_t clock_source)
{
    diagnostic_record_t record = valid_record();
    diagnostic_record_set_clock(&record, clock_source);
    RETAINED_DIAGNOSTICS = record;
}

void retained_diagnostics_set_commands(
    uint16_t phase_command,
    uint8_t vga_command)
{
    diagnostic_record_t record = valid_record();
    diagnostic_record_set_commands(&record, phase_command, vga_command);
    RETAINED_DIAGNOSTICS = record;
}

void retained_diagnostics_set_fault(firmware_fault_t fault)
{
    diagnostic_record_t record = valid_record();
    diagnostic_record_set_fault(&record, fault);
    RETAINED_DIAGNOSTICS = record;
}

void retained_diagnostics_mark_healthy(void)
{
    diagnostic_record_t record = valid_record();
    diagnostic_record_mark_healthy(&record);
    RETAINED_DIAGNOSTICS = record;
}
