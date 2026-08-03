#ifndef BEAMFORMING_PROTOCOL_H
#define BEAMFORMING_PROTOCOL_H

#include <stdbool.h>
#include <stdint.h>

#define PHASE_STATE_BITS 8u
#define PHASE_STATE_COUNT 256u
#define PHASE_FULL_TURN_MILLIDEGREES 360000u
#define PHASE_CONTROL_WORD_BITS 9u
#define PHASE_CONTROL_WORD_DATA_MASK 0x00ffu
#define PHASE_CONTROL_WORD_OPTION_MASK 0x0100u
#define PHASE_UNIT_ADDRESS_BITS 4u
#define PHASE_COMMAND_PHASE_SHIFT 5u
#define PHASE_COMMAND_OPTION_SHIFT 4u
#define PHASE_COMMAND_ADDRESS_MASK 0x000fu
#define PHASE_COMMAND_OPTION_MASK (1u << PHASE_COMMAND_OPTION_SHIFT)
#define PHASE_COMMAND_MAX 0x1fffu

#define VGA_MAX_ATTENUATION_DB 23u
#define VGA_COMMAND_ATTENUATION_SHIFT 2u

bool phase_state_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t *phase_state);

#endif
