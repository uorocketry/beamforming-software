#ifndef RF_EXECUTE_H
#define RF_EXECUTE_H

#include "rf/plan.h"

#include <stdint.h>

void rf_execute_operation(
    const rf_operation_t *operation,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command);

/* Execute a validated plan in order. Hardware failures enter firmware_fail(). */
void rf_execute_plan(
    const rf_plan_t *plan,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command);

#endif
