#ifndef RF_PHASE_SHIFTER_H
#define RF_PHASE_SHIFTER_H

#include "platform/spi_guard.h"

#include <stdint.h>

void pe448spisetup(void);
spi_guard_status_t phase_shifter_write(uint16_t command, uint32_t timeout_millis);

#endif
