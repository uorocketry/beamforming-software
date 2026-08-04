#include "rf/plan.h"

#include "rf/commands.h"

#include <stddef.h>
#include <string.h>

_Static_assert(
    PHASE_UNIT_ADDRESS_MIN + RF_CHANNEL_MAX <= PHASE_COMMAND_ADDRESS_MASK,
    "Every RF channel must map to a valid PE44820 address.");

/*
 * Add one already-formatted SPI write to the execution plan.
 *
 * Planning every write before touching hardware is intentional. It lets the
 * firmware reject an invalid eight-byte command without programming only some
 * of the RF channels, and it keeps the exact write order visible in unit tests.
 */
static can_command_result_t append_operation(
    rf_plan_t *plan,
    rf_operation_type_t type,
    uint8_t channel,
    uint16_t command)
{
    if (plan->operation_count >= RF_PLAN_MAX_OPERATIONS) {
        return CAN_COMMAND_RESULT_BUSY;
    }

    rf_operation_t *operation =
        &plan->operations[plan->operation_count++];
    operation->type = type;
    operation->channel = channel;
    operation->command = command;
    return CAN_COMMAND_RESULT_OK;
}

/*
 * Convert a CAN phase-state index into the calibrated 9-bit PE44820 enum word,
 * then build the 13-bit serial command with the channel's hardware address.
 *
 * CAN channels are zero based:       0, 1, 2, 3
 * PE44820 unit addresses are:        1, 2, 3, 4
 */
static can_command_result_t append_phase(
    uint8_t channel,
    uint8_t phaseStateIndex,
    rf_plan_t *plan)
{
    if (channel >= RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const optimizedPhaseState_e phaseState =
        GetOptimizedPhaseState(phaseStateIndex);
    const uint8_t phaseAddress =
        (uint8_t)(PHASE_UNIT_ADDRESS_MIN + channel);
    const uint16_t command = MakePSCommand(phaseState, phaseAddress);

    const can_command_result_t result =
        append_operation(plan, RF_OPERATION_PHASE, channel, command);
    if (result == CAN_COMMAND_RESULT_OK) {
        plan->resulting_state.phase_states[channel] = phaseStateIndex;
    }
    return result;
}

/*
 * Validate one requested attenuation and add its eight-bit F0480 command to
 * the plan. The operation keeps the channel number because the final hardware
 * driver must select the corresponding VGA before transmitting the byte.
 */
static can_command_result_t append_vga(
    uint8_t channel,
    uint8_t attenuationDb,
    rf_plan_t *plan)
{
    if (channel >= RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    uint8_t command = 0u;
    if (!MakeVGACommand(attenuationDb, &command)) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const can_command_result_t result =
        append_operation(plan, RF_OPERATION_VGA, channel, command);
    if (result == CAN_COMMAND_RESULT_OK) {
        plan->resulting_state.attenuation_db[channel] = attenuationDb;
    }
    return result;
}

/*
 * SET_PHASE changes one or four phase shifters while preserving each channel's
 * current attenuation.
 *
 * Stage 1: move every active channel to 23 dB before changing phase.
 * Stage 2: program the selected PE44820 address(es) in channel order.
 * Stage 3: restore the attenuation that each channel had before the command.
 *
 * Channels already at 23 dB do not need an unnecessary stage-1 or stage-3
 * VGA write. The resulting state records each updated phase.
 */
static can_command_result_t plan_phase_safely(
    const can_command_t *command,
    const rf_state_t *currentState,
    rf_plan_t *plan)
{
    if (!command->bulk_update && command->channel >= RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const uint8_t firstChannel = command->bulk_update ? 0u : command->channel;
    const uint8_t endChannel = command->bulk_update
        ? RF_CHANNEL_COUNT
        : (uint8_t)(command->channel + 1u);

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        if (currentState->attenuation_db[channel] != VGA_MAX_ATTENUATION_DB) {
            const can_command_result_t result =
                append_vga(channel, VGA_MAX_ATTENUATION_DB, plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
    }

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        const can_command_result_t result =
            append_phase(channel, command->phase_states[channel], plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        if (currentState->attenuation_db[channel] != VGA_MAX_ATTENUATION_DB) {
            const can_command_result_t result = append_vga(
                channel,
                currentState->attenuation_db[channel],
                plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
    }

    return CAN_COMMAND_RESULT_OK;
}

/*
 * SET_COMBINED updates one channel (DLC 3) or all channels (DLC 8):
 *
 * Each affected output moves to maximum attenuation, receives its phase word,
 * then receives the requested attenuation. A requested 23 dB is not sent twice.
 */
static can_command_result_t plan_combined(
    const can_command_t *command,
    rf_plan_t *plan)
{
    if (!command->bulk_update && command->channel >= RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const uint8_t firstChannel = command->bulk_update ? 0u : command->channel;
    const uint8_t endChannel = command->bulk_update
        ? RF_CHANNEL_COUNT
        : (uint8_t)(command->channel + 1u);

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        const can_command_result_t result =
            append_vga(channel, VGA_MAX_ATTENUATION_DB, plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        const can_command_result_t result =
            append_phase(channel, command->phase_states[channel], plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
        if (command->attenuation_db[channel] != VGA_MAX_ATTENUATION_DB) {
            const can_command_result_t result = append_vga(
                channel,
                command->attenuation_db[channel],
                plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
    }

    return CAN_COMMAND_RESULT_OK;
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

    /* Put every output at the requested attenuation before changing phase. */
    for (uint8_t channel = 0u; channel < RF_CHANNEL_COUNT; ++channel) {
        if (append_vga(channel, attenuation_db, plan) != CAN_COMMAND_RESULT_OK) {
            return false;
        }
    }

    /* PE44820 channel indexes 0..3 map to hardware addresses 1..4. */
    for (uint8_t channel = 0u; channel < RF_CHANNEL_COUNT; ++channel) {
        if (append_phase(channel, phase_state, plan) != CAN_COMMAND_RESULT_OK) {
            return false;
        }
    }

    return true;
}

can_command_result_t rf_plan_command(
    const can_command_t *command,
    const rf_state_t *currentState,
    rf_plan_t *plan)
{
    if (command == NULL || currentState == NULL || plan == NULL) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    memset(plan, 0, sizeof(*plan));
    plan->resulting_state = *currentState;

    switch (command->type) {
    case CAN_MESSAGE_SET_PHASE:
        return plan_phase_safely(command, currentState, plan);

    case CAN_MESSAGE_SET_VGA: {
        if (!command->bulk_update && command->channel >= RF_CHANNEL_COUNT) {
            return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
        }

        const uint8_t firstChannel = command->bulk_update ? 0u : command->channel;
        const uint8_t endChannel = command->bulk_update
            ? RF_CHANNEL_COUNT
            : (uint8_t)(command->channel + 1u);
        for (uint8_t channel = firstChannel; channel < endChannel; ++channel) {
            const can_command_result_t result = append_vga(
                channel,
                command->attenuation_db[channel],
                plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
        return CAN_COMMAND_RESULT_OK;
    }

    case CAN_MESSAGE_SET_COMBINED:
        return plan_combined(command, plan);

    case CAN_MESSAGE_ENTER_SAFE: {
        /* ENTER_SAFE intentionally remains a one-channel emergency command. */
        can_command_result_t result = append_vga(
            command->channel,
            VGA_MAX_ATTENUATION_DB,
            plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
        return append_phase(command->channel, 0u, plan);
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
