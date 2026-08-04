#ifndef CAN_CONTROL_H
#define CAN_CONTROL_H

#include "can_protocol.h"

#include <stdint.h>

/*
 * Worst case for a four-channel safe transition:
 *   4 writes to apply 23 dB + 4 phase writes + 4 final VGA writes.
 */
#define CAN_CONTROL_MAX_OPERATIONS 12u

typedef enum can_control_operation_type {
    CAN_CONTROL_OPERATION_PHASE = 0,
    CAN_CONTROL_OPERATION_VGA = 1
} can_control_operation_type_t;

typedef struct can_control_operation {
    can_control_operation_type_t type;
    uint8_t channel; /* zero-based RF channel 0..3 */
    uint16_t command;
} can_control_operation_t;

/* Array index 0..3 always means physical RF channel 1..4. */
typedef struct can_control_state {
    uint8_t phase_states[CAN_RF_CHANNEL_COUNT];
    uint8_t attenuation_db[CAN_RF_CHANNEL_COUNT];
} can_control_state_t;

typedef struct can_control_plan {
    can_control_operation_t operations[CAN_CONTROL_MAX_OPERATIONS];
    uint8_t operation_count;
    can_control_state_t resulting_state;
} can_control_plan_t;

can_command_result_t can_control_plan_command(
    const can_command_t *command,
    const can_control_state_t *current_state,
    can_control_plan_t *plan);

#endif
