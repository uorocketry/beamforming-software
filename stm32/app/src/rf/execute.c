#include "rf/execute.h"

#include "platform/faults.h"
#include "rf/phase_shifter.h"
#include "rf/vga.h"

#include <stddef.h>

static firmware_fault_t phase_fault(spi_guard_status_t status)
{
    return (status == SPI_GUARD_TIMEOUT)
        ? FIRMWARE_FAULT_PHASE_SPI_TIMEOUT
        : FIRMWARE_FAULT_PHASE_SPI_ERROR;
}

static firmware_fault_t vga_fault(spi_guard_status_t status)
{
    return (status == SPI_GUARD_TIMEOUT)
        ? FIRMWARE_FAULT_VGA_SPI_TIMEOUT
        : FIRMWARE_FAULT_VGA_SPI_ERROR;
}

void rf_execute_operation(
    const rf_operation_t *operation,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command)
{
    if (operation == NULL
        || last_phase_command == NULL
        || last_vga_command == NULL) {
        firmware_fail(FIRMWARE_FAULT_PHASE_COMMAND);
    }

    if (operation->type == RF_OPERATION_VGA) {
        const uint8_t command = (uint8_t)operation->command;
        const spi_guard_status_t status = vga_write(
            operation->channel,
            command,
            timeout_millis);
        if (status != SPI_GUARD_OK) {
            firmware_fail(vga_fault(status));
        }
        *last_vga_command = command;
        return;
    }

    const spi_guard_status_t status =
        phase_shifter_write(operation->command, timeout_millis);
    if (status != SPI_GUARD_OK) {
        firmware_fail(phase_fault(status));
    }
    *last_phase_command = operation->command;
}

void rf_execute_plan(
    const rf_plan_t *plan,
    uint32_t timeout_millis,
    uint16_t *last_phase_command,
    uint8_t *last_vga_command)
{
    if (plan == NULL || last_phase_command == NULL || last_vga_command == NULL) {
        firmware_fail(FIRMWARE_FAULT_PHASE_COMMAND);
    }

    for (uint8_t index = 0u; index < plan->operation_count; ++index) {
        rf_execute_operation(
            &plan->operations[index],
            timeout_millis,
            last_phase_command,
            last_vga_command);
    }
}
