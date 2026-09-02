#ifndef RF_VGA_H
#define RF_VGA_H

#include "platform/spi_guard.h"

#include <stdint.h>

void f0480spisetup(void);
spi_guard_status_t vga_write(uint8_t command, uint32_t timeout_millis);

#endif
