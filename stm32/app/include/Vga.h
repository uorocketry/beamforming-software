#ifndef VGA_H
#define VGA_H

#include "spi_guard.h"

#include <stdbool.h>
#include <stdint.h>

#define SPI1_VGA_CSB_PORT GPIOA
#define SPI1_VGA_CSB_PIN GPIO4
#define SPI1_VGA_CLK_PORT GPIOA
#define SPI1_VGA_CLK_PIN GPIO5
#define SPI1_VGA_MOSI_PORT GPIOA
#define SPI1_VGA_MOSI_PIN GPIO7

/* Protocol 2.0 carries one attenuation value for each receiver RF channel. */
#define F0480_CHANNEL_COUNT 4u

bool MakeVGACommand(uint8_t attenuationDb, uint8_t *command);

void f0480spisetup(void);
spi_guard_status_t vga_write(
    uint8_t channel,
    uint8_t command,
    uint32_t timeout_millis);

#endif
