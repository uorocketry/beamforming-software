#include "rf/commands.h"
#include "rf/plan.h"

#include <assert.h>
#include <stdio.h>

static uint16_t phase_command(uint8_t state)
{
    return MakePSCommand(GetOptimizedPhaseState(state), PHASE_UNIT_ADDRESS);
}

static void test_startup_orders_safe_vga_before_phase(void)
{
    rf_plan_t plan;
    assert(rf_plan_startup(146u, 23u, &plan));
    assert(plan.operation_count == 2u);
    assert(plan.operations[0].type == RF_OPERATION_VGA);
    assert(plan.operations[0].command == 0x5cu);
    assert(plan.operations[1].type == RF_OPERATION_PHASE);
    assert(plan.operations[1].command == phase_command(146u));
    assert(plan.resulting_state.phase_state == 146u);
    assert(plan.resulting_state.attenuation_db == 23u);
}

static void test_phase_is_guarded_and_attenuation_restored(void)
{
    const rf_state_t current = {.phase_state = 1u, .attenuation_db = 8u};
    const can_command_t command = {
        .type = CAN_MESSAGE_SET_PHASE,
        .phase_state = 146u,
    };
    rf_plan_t plan;
    assert(rf_plan_command(&command, &current, &plan) == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 3u);
    assert(plan.operations[0].type == RF_OPERATION_VGA);
    assert(plan.operations[0].command == 0x5cu);
    assert(plan.operations[1].type == RF_OPERATION_PHASE);
    assert(plan.operations[1].command == phase_command(146u));
    assert(plan.operations[2].type == RF_OPERATION_VGA);
    assert(plan.operations[2].command == 0x20u);
    assert(plan.resulting_state.phase_state == 146u);
    assert(plan.resulting_state.attenuation_db == 8u);
}

static void test_vga_and_combined(void)
{
    const rf_state_t current = {.phase_state = 1u, .attenuation_db = 8u};
    rf_plan_t plan;
    can_command_t command = {
        .type = CAN_MESSAGE_SET_VGA,
        .attenuation_db = 12u,
    };
    assert(rf_plan_command(&command, &current, &plan) == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 1u);
    assert(plan.operations[0].command == 0x30u);

    command.type = CAN_MESSAGE_SET_COMBINED;
    command.phase_state = 64u;
    command.attenuation_db = 6u;
    assert(rf_plan_command(&command, &current, &plan) == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 3u);
    assert(plan.operations[0].command == 0x5cu);
    assert(plan.operations[1].command == phase_command(64u));
    assert(plan.operations[2].command == 0x18u);
}

static void test_enter_safe(void)
{
    const rf_state_t current = {.phase_state = 100u, .attenuation_db = 4u};
    const can_command_t command = {.type = CAN_MESSAGE_ENTER_SAFE};
    rf_plan_t plan;
    assert(rf_plan_command(&command, &current, &plan) == CAN_COMMAND_RESULT_OK);
    assert(plan.operation_count == 2u);
    assert(plan.operations[0].command == 0x5cu);
    assert(plan.operations[1].command == phase_command(0u));
    assert(plan.resulting_state.phase_state == 0u);
    assert(plan.resulting_state.attenuation_db == 23u);
}

int main(void)
{
    test_startup_orders_safe_vga_before_phase();
    test_phase_is_guarded_and_attenuation_restored();
    test_vga_and_combined();
    test_enter_safe();
    puts("RF plan tests passed");
    return 0;
}
