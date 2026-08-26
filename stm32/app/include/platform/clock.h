#ifndef PLATFORM_CLOCK_H
#define PLATFORM_CLOCK_H

#include "platform/diagnostic_record.h"

#include <stdbool.h>

#define FIRMWARE_HSE_CLOCK_HZ 16000000u
#define FIRMWARE_CORE_CLOCK_HZ 48000000u

bool clock_setup(firmware_clock_t *clock_source);

#endif
