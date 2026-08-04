#ifndef PLATFORM_BOARD_H
#define PLATFORM_BOARD_H

#include <libopencm3/stm32/gpio.h>

/* bxCAN on PA11/PA12, alternate function 4. */
#define BOARD_CAN_PORT GPIOA
#define BOARD_CAN_RX_PIN GPIO11
#define BOARD_CAN_TX_PIN GPIO12
#define BOARD_CAN_AF GPIO_AF4

/* PE44820 serial interface on SPI2. */
#define BOARD_PHASE_LE_PORT GPIOB
#define BOARD_PHASE_LE_PIN GPIO12
#define BOARD_PHASE_SP_PORT GPIOC
#define BOARD_PHASE_SP_PIN GPIO10
#define BOARD_PHASE_CLK_PORT GPIOB
#define BOARD_PHASE_CLK_PIN GPIO13
#define BOARD_PHASE_MOSI_PORT GPIOB
#define BOARD_PHASE_MOSI_PIN GPIO15
#define BOARD_PHASE_AF GPIO_AF0

/* F0480 serial interface on SPI1. */
#define BOARD_VGA_CS_PORT GPIOA
#define BOARD_VGA_CS_PIN GPIO4
#define BOARD_VGA_CLK_PORT GPIOA
#define BOARD_VGA_CLK_PIN GPIO5
#define BOARD_VGA_MOSI_PORT GPIOA
#define BOARD_VGA_MOSI_PIN GPIO7
#define BOARD_VGA_AF GPIO_AF0

/* Two core cycles between the final SPI edge and a control-line transition. */
static inline void board_control_line_margin(void)
{
    __asm__ volatile("nop");
    __asm__ volatile("nop");
}

#endif
