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

uint16_t beamforming_reverse_bits(uint16_t word, uint8_t bit_count);
bool phase_state_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t *phase_state);
/* Return the calibrated 2.4 GHz PE44820 word: OPT in bit 8 and D7:D0 below. */
uint16_t phase_control_word_from_state(uint8_t phase_state);
/* Look up the 9-bit phase word and form the PE44820 13-bit serial command. */
bool phase_command_from_state(uint8_t phase_state, uint8_t unit_address, uint16_t *command);
bool phase_command_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t unit_address,
    uint16_t *command);
bool vga_command_from_attenuation(uint8_t attenuation_db, uint8_t *command);

#endif
