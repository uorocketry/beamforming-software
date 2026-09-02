#include "rf/plan.h"

#include "rf/commands.h"

#include <stddef.h>
#include <string.h>

static can_command_result_t append_operation(
    rf_plan_t *plan,
    rf_operation_type_t type,
    uint16_t command)
{
    if (plan->operation_count >= RF_PLAN_MAX_OPERATIONS) {
        return CAN_COMMAND_RESULT_BUSY;
    }

    rf_operation_t *operation = &plan->operations[plan->operation_count++];
    operation->type = type;
    operation->command = command;
    return CAN_COMMAND_RESULT_OK;
}

static can_command_result_t append_phase(uint8_t phase_state, rf_plan_t *plan)
{
    const optimizedPhaseState_e optimized = GetOptimizedPhaseState(phase_state);
    const uint16_t command = MakePSCommand(optimized, PHASE_UNIT_ADDRESS);
    const can_command_result_t result = append_operation(plan, RF_OPERATION_PHASE, command);
    if (result == CAN_COMMAND_RESULT_OK) {
        plan->resulting_state.phase_state = phase_state;
    }
    return result;
}

static can_command_result_t append_vga(uint8_t attenuation_db, rf_plan_t *plan)
{
    uint8_t command = 0u;
    if (!MakeVGACommand(attenuation_db, &command)) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const can_command_result_t result = append_operation(plan, RF_OPERATION_VGA, command);
    if (result == CAN_COMMAND_RESULT_OK) {
        plan->resulting_state.attenuation_db = attenuation_db;
    }
    return result;
}

static can_command_result_t plan_phase_safely(
    uint8_t phase_state,
    const rf_state_t *current_state,
    rf_plan_t *plan)
{
    const bool restore_attenuation =
        current_state->attenuation_db != VGA_MAX_ATTENUATION_DB;
    if (restore_attenuation) {
        const can_command_result_t result = append_vga(VGA_MAX_ATTENUATION_DB, plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    can_command_result_t result = append_phase(phase_state, plan);
    if (result != CAN_COMMAND_RESULT_OK) {
        return result;
    }

    if (restore_attenuation) {
        result = append_vga(current_state->attenuation_db, plan);
    }
    return result;
}

static can_command_result_t plan_combined(
    uint8_t phase_state,
    uint8_t attenuation_db,
    rf_plan_t *plan)
{
    can_command_result_t result = append_vga(VGA_MAX_ATTENUATION_DB, plan);
    if (result != CAN_COMMAND_RESULT_OK) {
        return result;
    }

    result = append_phase(phase_state, plan);
    if (result != CAN_COMMAND_RESULT_OK) {
        return result;
    }

    return attenuation_db == VGA_MAX_ATTENUATION_DB
        ? CAN_COMMAND_RESULT_OK
        : append_vga(attenuation_db, plan);
}

bool rf_plan_startup(
    uint8_t phase_state,
    uint8_t attenuation_db,
    rf_plan_t *plan)
{
    if (plan == NULL || attenuation_db > VGA_MAX_ATTENUATION_DB) {
        return false;
    }

    memset(plan, 0, sizeof(*plan));
    return append_vga(attenuation_db, plan) == CAN_COMMAND_RESULT_OK
        && append_phase(phase_state, plan) == CAN_COMMAND_RESULT_OK;
}

can_command_result_t rf_plan_command(
    const can_command_t *command,
    const rf_state_t *current_state,
    rf_plan_t *plan)
{
    if (command == NULL || current_state == NULL || plan == NULL) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    memset(plan, 0, sizeof(*plan));
    plan->resulting_state = *current_state;

    switch (command->type) {
    case CAN_MESSAGE_SET_PHASE:
        return plan_phase_safely(command->phase_state, current_state, plan);
    case CAN_MESSAGE_SET_VGA:
        return append_vga(command->attenuation_db, plan);
    case CAN_MESSAGE_SET_COMBINED:
        return plan_combined(command->phase_state, command->attenuation_db, plan);
    case CAN_MESSAGE_ENTER_SAFE: {
        can_command_result_t result = append_vga(VGA_MAX_ATTENUATION_DB, plan);
        return result == CAN_COMMAND_RESULT_OK ? append_phase(0u, plan) : result;
    }
    case CAN_MESSAGE_PING:
        return CAN_COMMAND_RESULT_OK;
    case CAN_MESSAGE_STATUS:
    case CAN_MESSAGE_ACK:
    case CAN_MESSAGE_ERROR:
    case CAN_MESSAGE_TYPE_COUNT:
        return CAN_COMMAND_RESULT_UNSUPPORTED;
    }
    return CAN_COMMAND_RESULT_UNSUPPORTED;
}
