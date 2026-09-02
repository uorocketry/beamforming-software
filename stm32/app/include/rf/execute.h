#ifndef RF_EXECUTE_H
#define RF_EXECUTE_H

#include "platform/diagnostic_record.h"
#include "rf/plan.h"

#include <stdint.h>

firmware_fault_t rf_execute_operation(
    const rf_operation_t *operation,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command);

/* Execute a validated plan in order and return the first hardware fault. */
firmware_fault_t rf_execute_plan(
    const rf_plan_t *plan,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command);

#endif
