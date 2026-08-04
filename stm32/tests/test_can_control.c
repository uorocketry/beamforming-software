#include "PhaseShifter.h"
#include "can_control.h"
#include "beamforming_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static can_command_t command_of(can_message_type_t type)
{
    can_command_t command = {0};
    command.type = type;
    command.source = CAN_NODE_CONTROLLER;
    command.destination = 1u;
    command.sequence = 1u;
    return command;
}

static can_control_state_t initial_state(void)
{
    const can_control_state_t state = {
        .phase_states = {0u, 0u, 0u, 0u},
        .attenuation_db = {23u, 23u, 23u, 23u},
    };
    return state;
}

static uint16_t phase_command(uint8_t channel, uint8_t state_index)
{
    const optimizedPhaseState_e phase_state =
        GetOptimizedPhaseState(state_index);
    return MakePSCommand(
        phase_state,
        (uint8_t)(CAN_PHASE_ADDRESS_MIN + channel));
}

static void assert_operation(
    const can_control_plan_t *plan,
    uint8_t index,
    can_control_operation_type_t type,
    uint8_t channel,
    uint16_t command)
{
    assert(index < plan->operation_count);
    assert(plan->operations[index].type == type);
    assert(plan->operations[index].channel == channel);
    assert(plan->operations[index].command == command);
}

static void test_bulk_phase_plan(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_PHASE);
    command.bulk_update = true;
    const uint8_t requested[] = {146u, 128u, 64u, 0u};
    memcpy(command.phase_states, requested, sizeof(requested));

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 4u);

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        assert_operation(
            &plan,
            channel,
            CAN_CONTROL_OPERATION_PHASE,
            channel,
            phase_command(channel, requested[channel]));
    }

    assert(memcmp(plan.resulting_state.phase_states, requested, sizeof(requested)) == 0);
    assert(memcmp(
        plan.resulting_state.attenuation_db,
        current.attenuation_db,
        CAN_RF_CHANNEL_COUNT) == 0);
}

static void test_bulk_phase_plan_attenuates_then_restores(void)
{
    const can_control_state_t current = {
        .phase_states = {1u, 2u, 3u, 4u},
        .attenuation_db = {8u, 23u, 12u, 23u},
    };
    can_command_t command = command_of(CAN_MESSAGE_SET_PHASE);
    command.bulk_update = true;
    const uint8_t requested[] = {10u, 20u, 30u, 40u};
    memcpy(command.phase_states, requested, sizeof(requested));

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 8u);

    assert_operation(&plan, 0u, CAN_CONTROL_OPERATION_VGA, 0u, 0x5cu);
    assert_operation(&plan, 1u, CAN_CONTROL_OPERATION_VGA, 2u, 0x5cu);
    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        assert_operation(
            &plan,
            (uint8_t)(2u + channel),
            CAN_CONTROL_OPERATION_PHASE,
            channel,
            phase_command(channel, requested[channel]));
    }
    assert_operation(&plan, 6u, CAN_CONTROL_OPERATION_VGA, 0u, 0x20u);
    assert_operation(&plan, 7u, CAN_CONTROL_OPERATION_VGA, 2u, 0x30u);

    assert(memcmp(plan.resulting_state.phase_states, requested, sizeof(requested)) == 0);
    assert(memcmp(
        plan.resulting_state.attenuation_db,
        current.attenuation_db,
        CAN_RF_CHANNEL_COUNT) == 0);
}

static void test_bulk_vga_plan(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_VGA);
    command.bulk_update = true;
    const uint8_t requested[] = {0u, 8u, 12u, 23u};
    memcpy(command.attenuation_db, requested, sizeof(requested));

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 4u);

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        assert_operation(
            &plan,
            channel,
            CAN_CONTROL_OPERATION_VGA,
            channel,
            (uint16_t)(requested[channel] << VGA_COMMAND_ATTENUATION_SHIFT));
    }
    assert(memcmp(
        plan.resulting_state.attenuation_db,
        requested,
        sizeof(requested)) == 0);
}

static void test_bulk_combined_plan_uses_safe_transition_order(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_COMBINED);
    command.bulk_update = true;
    const uint8_t phases[] = {64u, 65u, 66u, 67u};
    const uint8_t attenuations[] = {12u, 23u, 0u, 8u};
    memcpy(command.phase_states, phases, sizeof(phases));
    memcpy(command.attenuation_db, attenuations, sizeof(attenuations));

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 11u);

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        assert_operation(
            &plan,
            channel,
            CAN_CONTROL_OPERATION_VGA,
            channel,
            0x5cu);
        assert_operation(
            &plan,
            (uint8_t)(4u + channel),
            CAN_CONTROL_OPERATION_PHASE,
            channel,
            phase_command(channel, phases[channel]));
    }
    assert_operation(&plan, 8u, CAN_CONTROL_OPERATION_VGA, 0u, 0x30u);
    assert_operation(&plan, 9u, CAN_CONTROL_OPERATION_VGA, 2u, 0x00u);
    assert_operation(&plan, 10u, CAN_CONTROL_OPERATION_VGA, 3u, 0x20u);

    assert(memcmp(plan.resulting_state.phase_states, phases, sizeof(phases)) == 0);
    assert(memcmp(
        plan.resulting_state.attenuation_db,
        attenuations,
        sizeof(attenuations)) == 0);
}

static void test_bulk_combined_all_max_uses_eight_operations(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_COMBINED);
    command.bulk_update = true;
    const uint8_t phases[] = {1u, 2u, 3u, 4u};
    const uint8_t attenuations[] = {23u, 23u, 23u, 23u};
    memcpy(command.phase_states, phases, sizeof(phases));
    memcpy(command.attenuation_db, attenuations, sizeof(attenuations));

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 8u);
}


static void test_individual_phase_plan(void)
{
    const can_control_state_t current = {
        .phase_states = {1u, 2u, 3u, 4u},
        .attenuation_db = {23u, 8u, 23u, 23u},
    };
    can_command_t command = command_of(CAN_MESSAGE_SET_PHASE);
    command.channel = 1u;
    command.phase_states[1] = 146u;

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 3u);
    assert_operation(&plan, 0u, CAN_CONTROL_OPERATION_VGA, 1u, 0x5cu);
    assert_operation(
        &plan, 1u, CAN_CONTROL_OPERATION_PHASE, 1u, phase_command(1u, 146u));
    assert_operation(&plan, 2u, CAN_CONTROL_OPERATION_VGA, 1u, 0x20u);
    assert(plan.resulting_state.phase_states[1] == 146u);
    assert(plan.resulting_state.phase_states[0] == current.phase_states[0]);
}

static void test_individual_vga_plan(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_VGA);
    command.channel = 2u;
    command.attenuation_db[2] = 12u;

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 1u);
    assert_operation(&plan, 0u, CAN_CONTROL_OPERATION_VGA, 2u, 0x30u);
    assert(plan.resulting_state.attenuation_db[2] == 12u);
    assert(plan.resulting_state.attenuation_db[1] == current.attenuation_db[1]);
}

static void test_individual_combined_plan(void)
{
    const can_control_state_t current = initial_state();
    can_command_t command = command_of(CAN_MESSAGE_SET_COMBINED);
    command.channel = 3u;
    command.phase_states[3] = 64u;
    command.attenuation_db[3] = 8u;

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 3u);
    assert_operation(&plan, 0u, CAN_CONTROL_OPERATION_VGA, 3u, 0x5cu);
    assert_operation(
        &plan, 1u, CAN_CONTROL_OPERATION_PHASE, 3u, phase_command(3u, 64u));
    assert_operation(&plan, 2u, CAN_CONTROL_OPERATION_VGA, 3u, 0x20u);
    assert(plan.resulting_state.phase_states[3] == 64u);
    assert(plan.resulting_state.attenuation_db[3] == 8u);
}

static void test_safe_plan_targets_one_channel(void)
{
    const can_control_state_t current = {
        .phase_states = {100u, 110u, 120u, 130u},
        .attenuation_db = {0u, 1u, 2u, 3u},
    };
    can_command_t command = command_of(CAN_MESSAGE_ENTER_SAFE);
    command.channel = 2u;

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 2u);
    assert_operation(&plan, 0u, CAN_CONTROL_OPERATION_VGA, 2u, 0x5cu);
    assert_operation(
        &plan,
        1u,
        CAN_CONTROL_OPERATION_PHASE,
        2u,
        phase_command(2u, 0u));
    assert(plan.resulting_state.phase_states[2] == 0u);
    assert(plan.resulting_state.attenuation_db[2] == 23u);
    assert(plan.resulting_state.phase_states[1] == current.phase_states[1]);
}

static void test_ping_has_no_hardware_actions(void)
{
    const can_control_state_t current = {
        .phase_states = {1u, 2u, 3u, 4u},
        .attenuation_db = {3u, 4u, 5u, 6u},
    };
    const can_command_t command = command_of(CAN_MESSAGE_PING);

    can_control_plan_t plan = {0};
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 0u);
    assert(memcmp(&plan.resulting_state, &current, sizeof(current)) == 0);
}

static void test_invalid_arguments_and_channel(void)
{
    const can_control_state_t current = initial_state();
    can_control_plan_t plan = {0};
    can_command_t command = command_of(CAN_MESSAGE_ENTER_SAFE);
    command.channel = CAN_RF_CHANNEL_COUNT;

    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_INVALID_PAYLOAD);
    assert(can_control_plan_command(NULL, &current, &plan)
        == CAN_COMMAND_RESULT_INVALID_PAYLOAD);
    assert(can_control_plan_command(&command, NULL, &plan)
        == CAN_COMMAND_RESULT_INVALID_PAYLOAD);
    assert(can_control_plan_command(&command, &current, NULL)
        == CAN_COMMAND_RESULT_INVALID_PAYLOAD);

    command = command_of(CAN_MESSAGE_STATUS);
    assert(can_control_plan_command(&command, &current, &plan)
        == CAN_COMMAND_RESULT_UNSUPPORTED);
}

int main(void)
{
    test_bulk_phase_plan();
    test_bulk_phase_plan_attenuates_then_restores();
    test_bulk_vga_plan();
    test_bulk_combined_plan_uses_safe_transition_order();
    test_bulk_combined_all_max_uses_eight_operations();
    test_individual_phase_plan();
    test_individual_vga_plan();
    test_individual_combined_plan();
    test_safe_plan_targets_one_channel();
    test_ping_has_no_hardware_actions();
    test_invalid_arguments_and_channel();
    puts("CAN control tests passed");
    return 0;
}
