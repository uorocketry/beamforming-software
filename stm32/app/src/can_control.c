#include "can_control.h"

#include "PhaseShifter.h"
#include "Vga.h"
#include "beamforming_protocol.h"

#include <stddef.h>
#include <string.h>

_Static_assert(
    CAN_PHASE_ADDRESS_MIN + CAN_RF_CHANNEL_MAX <= PHASE_COMMAND_ADDRESS_MASK,
    "Every RF channel must map to a valid PE44820 address.");

/*
 * Add one already-formatted SPI write to the execution plan.
 *
 * Planning every write before touching hardware is intentional. It lets the
 * firmware reject an invalid eight-byte command without programming only some
 * of the RF channels, and it keeps the exact write order visible in unit tests.
 */
static can_command_result_t append_operation(
    can_control_plan_t *plan,
    can_control_operation_type_t type,
    uint8_t channel,
    uint16_t command)
{
    if (plan->operation_count >= CAN_CONTROL_MAX_OPERATIONS) {
        return CAN_COMMAND_RESULT_BUSY;
    }

    can_control_operation_t *operation =
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
    can_control_plan_t *plan)
{
    if (channel >= CAN_RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const optimizedPhaseState_e phaseState =
        GetOptimizedPhaseState(phaseStateIndex);
    const uint8_t phaseAddress =
        (uint8_t)(CAN_PHASE_ADDRESS_MIN + channel);
    const uint16_t command = MakePSCommand(phaseState, phaseAddress);

    const can_command_result_t result =
        append_operation(plan, CAN_CONTROL_OPERATION_PHASE, channel, command);
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
    can_control_plan_t *plan)
{
    if (channel >= CAN_RF_CHANNEL_COUNT) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    uint8_t command = 0u;
    if (!MakeVGACommand(attenuationDb, &command)) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    const can_command_result_t result =
        append_operation(plan, CAN_CONTROL_OPERATION_VGA, channel, command);
    if (result == CAN_COMMAND_RESULT_OK) {
        plan->resulting_state.attenuation_db[channel] = attenuationDb;
    }
    return result;
}

/*
 * SET_PHASE changes all four phase shifters while preserving each channel's
 * current attenuation.
 *
 * Stage 1: move every active channel to 23 dB before changing phase.
 * Stage 2: program PE44820 addresses 1, 2, 3 and 4 in channel order.
 * Stage 3: restore the attenuation that each channel had before the command.
 *
 * Channels already at 23 dB do not need an unnecessary stage-1 or stage-3
 * VGA write. The resulting logical state still records all four new phases.
 */
static can_command_result_t plan_phase_safely(
    const can_command_t *command,
    const can_control_state_t *currentState,
    can_control_plan_t *plan)
{
    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        if (currentState->attenuation_db[channel] != VGA_MAX_ATTENUATION_DB) {
            const can_command_result_t result =
                append_vga(channel, VGA_MAX_ATTENUATION_DB, plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
    }

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        const can_command_result_t result =
            append_phase(channel, command->phase_states[channel], plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
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
 * SET_COMBINED is the complete eight-byte bulk update:
 *
 *   bytes 0..3 = phase-state indexes for channels 0..3
 *   bytes 4..7 = attenuation in dB for channels 0..3
 *
 * All outputs are first moved to maximum attenuation. The four phase words are
 * then transmitted, followed by the requested four attenuation values. A
 * requested 23 dB value is not sent twice because stage 1 already applied it.
 */
static can_command_result_t plan_combined(
    const can_command_t *command,
    can_control_plan_t *plan)
{
    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        const can_command_result_t result =
            append_vga(channel, VGA_MAX_ATTENUATION_DB, plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        const can_command_result_t result =
            append_phase(channel, command->phase_states[channel], plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
    }

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
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

can_command_result_t can_control_plan_command(
    const can_command_t *command,
    const can_control_state_t *currentState,
    can_control_plan_t *plan)
{
    if (command == NULL || currentState == NULL || plan == NULL) {
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }

    memset(plan, 0, sizeof(*plan));
    plan->resulting_state = *currentState;

    switch (command->type) {
    case CAN_MESSAGE_SET_PHASE:
        return plan_phase_safely(command, currentState, plan);

    case CAN_MESSAGE_SET_VGA:
        /* SET_VGA carries one attenuation byte for each of the four channels. */
        for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
            const can_command_result_t result = append_vga(
                channel,
                command->attenuation_db[channel],
                plan);
            if (result != CAN_COMMAND_RESULT_OK) {
                return result;
            }
        }
        return CAN_COMMAND_RESULT_OK;

    case CAN_MESSAGE_SET_COMBINED:
        return plan_combined(command, plan);

    case CAN_MESSAGE_ENTER_SAFE: {
        /* ENTER_SAFE intentionally remains a one-channel emergency command. */
        can_command_result_t result = append_vga(
            command->safe_channel,
            VGA_MAX_ATTENUATION_DB,
            plan);
        if (result != CAN_COMMAND_RESULT_OK) {
            return result;
        }
        return append_phase(command->safe_channel, 0u, plan);
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
