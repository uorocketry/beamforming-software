#include "rf/vga.h"

#include "platform/board.h"
#include "rf/commands.h"

#include <libopencm3/stm32/gpio.h>
#include <libopencm3/stm32/rcc.h>
#include <libopencm3/stm32/spi.h>

void f0480spisetup(void)
{
    rcc_periph_clock_enable(RCC_SPI1);
    rcc_periph_clock_enable(RCC_GPIOA);

    gpio_set(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    gpio_mode_setup(BOARD_VGA_CS_PORT, GPIO_MODE_OUTPUT, GPIO_PUPD_NONE, BOARD_VGA_CS_PIN);
    gpio_set_output_options(
        BOARD_VGA_CS_PORT,
        GPIO_OTYPE_PP,
        GPIO_OSPEED_HIGH,
        BOARD_VGA_CS_PIN);

    gpio_mode_setup(BOARD_VGA_CLK_PORT, GPIO_MODE_AF, GPIO_PUPD_NONE, BOARD_VGA_CLK_PIN);
    gpio_mode_setup(BOARD_VGA_MOSI_PORT, GPIO_MODE_AF, GPIO_PUPD_NONE, BOARD_VGA_MOSI_PIN);
    gpio_set_af(BOARD_VGA_CLK_PORT, BOARD_VGA_AF, BOARD_VGA_CLK_PIN);
    gpio_set_af(BOARD_VGA_MOSI_PORT, BOARD_VGA_AF, BOARD_VGA_MOSI_PIN);
    gpio_set_output_options(
        BOARD_VGA_CLK_PORT,
        GPIO_OTYPE_PP,
        GPIO_OSPEED_HIGH,
        BOARD_VGA_CLK_PIN | BOARD_VGA_MOSI_PIN);

    spi_disable(SPI1);
    spi_init_master(
        SPI1,
        SPI_CR1_BAUDRATE_FPCLK_DIV_16,
        SPI_CR1_CPOL_CLK_TO_0_WHEN_IDLE,
        SPI_CR1_CPHA_CLK_TRANSITION_1,
        SPI_CR1_LSBFIRST);
    spi_set_data_size(SPI1, SPI_CR2_DS_8BIT);
    spi_fifo_reception_threshold_8bit(SPI1);
    /* The F0480 three-wire control bus has no return data line on this PCB. */
    spi_set_bidirectional_transmit_only_mode(SPI1);
    spi_enable_software_slave_management(SPI1);
    spi_set_nss_high(SPI1);
    spi_enable(SPI1);
}

spi_guard_status_t vga_write(
    uint8_t channel,
    uint8_t command,
    uint32_t timeout_millis)
{
    if (channel >= RF_CHANNEL_COUNT) {
        return SPI_GUARD_INVALID_ARGUMENT;
    }

    /*
     * The protocol carries four independent VGA values and the RF planner
     * preserves the channel number for every write. The checked-in C board pin
     * map, however, names only one F0480 chip-select line (PA4) and does not
     * identify the selector pins needed to route that CS to one of four chips.
     *
     * Keep the channel in this API so the final PCB selector can be added here
     * without changing the CAN/runtime layers. Until that net mapping is added,
     * the physical transfer below still uses the documented PA4 line.
     */
    (void)channel;

    spi_guard_status_t status = spi_guard_wait_txe(SPI1, timeout_millis);
    if (status != SPI_GUARD_OK) {
        return status;
    }

    gpio_clear(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    SPI_DR8(SPI1) = command;
    __asm__ volatile("dsb" ::: "memory");

    status = spi_guard_wait_complete(SPI1, timeout_millis);
    if (status != SPI_GUARD_OK) {
        return status;
    }

    board_control_line_margin();
    gpio_set(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    board_control_line_margin();
    /* This confirms only MCU-side transfer completion; there is no device ACK. */
    return SPI_GUARD_OK;
}
