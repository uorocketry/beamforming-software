#ifndef RF_PLAN_H
#define RF_PLAN_H

#include "can/protocol.h"

#include <stdbool.h>
#include <stdint.h>

/* Worst case: safe VGA, phase, then requested/restored VGA. */
#define RF_PLAN_MAX_OPERATIONS 3u

typedef enum rf_operation_type {
    RF_OPERATION_PHASE = 0,
    RF_OPERATION_VGA = 1
} rf_operation_type_t;

typedef struct rf_operation {
    rf_operation_type_t type;
    uint16_t command;
} rf_operation_t;

typedef struct rf_state {
    uint8_t phase_state;
    uint8_t attenuation_db;
} rf_state_t;

typedef struct rf_plan {
    rf_operation_t operations[RF_PLAN_MAX_OPERATIONS];
    uint8_t operation_count;
    rf_state_t resulting_state;
} rf_plan_t;

bool rf_plan_startup(
    uint8_t phase_state,
    uint8_t attenuation_db,
    rf_plan_t *plan);

can_command_result_t rf_plan_command(
    const can_command_t *command,
    const rf_state_t *current_state,
    rf_plan_t *plan);

#endif
