#include "can/runtime.h"
#include "platform/build_info.h"
#include "platform/clock.h"
#include "platform/retained_diagnostics.h"
#include "platform/faults.h"
#include "platform/firmware_config.h"
#include "platform/timebase.h"
#include "platform/watchdog.h"
#include "rf/commands.h"
#include "rf/execute.h"
#include "rf/phase_shifter.h"
#include "rf/plan.h"
#include "rf/vga.h"

#include <libopencm3/stm32/rcc.h>

#include <stdbool.h>
#include <stdint.h>

#define WATCHDOG_TIMEOUT_MILLIS 1000u
#define SPI_TIMEOUT_MILLIS 2u
#define OPERATIONAL_PHASE_MILLIDEGREES 205300u
#define SAFE_PHASE_MILLIDEGREES 0u
#define SAFE_VGA_ATTENUATION_DB 23u
#define FIRMWARE_RESET_FLAG_MASK 0xfe000000u

static void service_without_can(void) __attribute__((noreturn));

static void service_without_can(void)
{
    while (1) {
        watchdog_service();
        __asm__ volatile("wfi");
    }
}

static void service_runtime(can_runtime_t *runtime) __attribute__((noreturn));

static void service_runtime(can_runtime_t *runtime)
{
    while (1) {
        bool processed_frame = false;
        while (can_runtime_service_next(runtime)) {
            processed_frame = true;
            watchdog_service();
        }

        watchdog_service();
        if (!processed_frame) {
            __asm__ volatile("wfi");
        }
    }
}

int main(void)
{
    const uint32_t reset_flags = RCC_CSR & FIRMWARE_RESET_FLAG_MASK;
    RCC_CSR |= RCC_CSR_RMVF;

    watchdog_start(WATCHDOG_TIMEOUT_MILLIS);
    retained_diagnostics_begin(reset_flags, firmware_build_id());
    const bool safe_lockout = retained_diagnostics_lockout_required();

    firmware_clock_t clock_source = FIRMWARE_CLOCK_UNKNOWN;
    if (!clock_setup(&clock_source)) {
        firmware_fail(FIRMWARE_FAULT_CLOCK_STARTUP);
    }

    timebase_setup(FIRMWARE_CORE_CLOCK_HZ);
    retained_diagnostics_set_clock(clock_source);
    retained_diagnostics_set_state(FIRMWARE_STATE_CLOCK_READY);

    f0480spisetup();
    pe448spisetup();

    const uint32_t requested_phase = safe_lockout
        ? SAFE_PHASE_MILLIDEGREES
        : OPERATIONAL_PHASE_MILLIDEGREES;
    uint8_t phase_state = 0u;
    if (!phase_state_from_millidegrees(requested_phase, &phase_state)) {
        firmware_fail(FIRMWARE_FAULT_PHASE_COMMAND);
    }

    rf_plan_t startup_plan = {0};
    if (!rf_plan_startup(
            phase_state,
            SAFE_VGA_ATTENUATION_DB,
            &startup_plan)) {
        firmware_fail(FIRMWARE_FAULT_PHASE_COMMAND);
    }

    uint16_t phase_command = 0u;
    uint8_t vga_command = 0u;

    /* The startup plan begins with one maximum-attenuation write per channel. */
    for (uint8_t index = 0u; index < RF_CHANNEL_COUNT; ++index) {
        rf_execute_operation(
            &startup_plan.operations[index],
            SPI_TIMEOUT_MILLIS,
            &phase_command,
            &vga_command);
    }
    retained_diagnostics_set_state(FIRMWARE_STATE_SAFE_OUTPUTS);

    for (uint8_t index = RF_CHANNEL_COUNT;
         index < startup_plan.operation_count;
         ++index) {
        rf_execute_operation(
            &startup_plan.operations[index],
            SPI_TIMEOUT_MILLIS,
            &phase_command,
            &vga_command);
    }
    retained_diagnostics_set_commands(phase_command, vga_command);

    can_runtime_t runtime = {0};
    if (!can_runtime_start(
            &runtime,
            BEAMFORMER_NODE_ID,
            clock_source,
            safe_lockout,
            &startup_plan.resulting_state,
            phase_command,
            vga_command)) {
        if (safe_lockout) {
            retained_diagnostics_set_fault(FIRMWARE_FAULT_CAN_INIT);
            retained_diagnostics_set_state(FIRMWARE_STATE_SAFE_LOCKOUT);
            service_without_can();
        }
        firmware_fail(FIRMWARE_FAULT_CAN_INIT);
    }

    if (safe_lockout) {
        retained_diagnostics_set_state(FIRMWARE_STATE_SAFE_LOCKOUT);
    } else {
        retained_diagnostics_mark_healthy();
    }

    service_runtime(&runtime);
}
