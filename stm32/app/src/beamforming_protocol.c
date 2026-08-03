#include "beamforming_protocol.h"
#include "phase_lookup_2_4_ghz.h"

#include <stddef.h>

_Static_assert(
    PHASE_LOOKUP_2_4_GHZ_STATE_COUNT == PHASE_STATE_COUNT,
    "phase lookup must contain every CAN phase state");

uint16_t beamforming_reverse_bits(uint16_t word, uint8_t bit_count)
{
    uint16_t reversed = 0u;

    for (uint8_t bit = 0u; bit < bit_count; ++bit) {
        reversed = (uint16_t)((reversed << 1u) | (word & 1u));
        word >>= 1u;
    }

    return reversed;
}

uint16_t phase_control_word_from_state(uint8_t phase_state)
{
    return phase_control_word_by_state_2_4_ghz[phase_state];
}

bool phase_command_from_state(uint8_t phase_state, uint8_t unit_address, uint16_t *command)
{
    if ((command == NULL) || (unit_address > 0x0fu)) {
        return false;
    }

    const uint16_t control_word = phase_control_word_from_state(phase_state);
    const uint16_t phase_bits = control_word & PHASE_CONTROL_WORD_DATA_MASK;
    const uint16_t phase_field = beamforming_reverse_bits(phase_bits, PHASE_STATE_BITS);
    const uint16_t address_field =
        beamforming_reverse_bits(unit_address, PHASE_UNIT_ADDRESS_BITS);
    const uint16_t option_field =
        ((control_word & PHASE_CONTROL_WORD_OPTION_MASK) != 0u)
            ? PHASE_COMMAND_OPTION_MASK
            : 0u;

    *command = (uint16_t)(
        (phase_field << PHASE_COMMAND_PHASE_SHIFT)
        | option_field
        | (address_field & PHASE_COMMAND_ADDRESS_MASK));
    return true;
}

bool phase_state_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t *phase_state)
{
    if (phase_state == NULL
        || requested_shift_millidegrees > PHASE_FULL_TURN_MILLIDEGREES) {
        return false;
    }

    const uint64_t scaled =
        ((uint64_t)requested_shift_millidegrees * PHASE_STATE_COUNT)
        + (PHASE_FULL_TURN_MILLIDEGREES / 2u);
    *phase_state = (uint8_t)((scaled / PHASE_FULL_TURN_MILLIDEGREES) & 0xffu);
    return true;
}

bool phase_command_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t unit_address,
    uint16_t *command)
{
    uint8_t phase_state = 0u;
    if (!phase_state_from_millidegrees(requested_shift_millidegrees, &phase_state)) {
        return false;
    }

    return phase_command_from_state(phase_state, unit_address, command);
}

bool vga_command_from_attenuation(uint8_t attenuation_db, uint8_t *command)
{
    if ((command == NULL) || (attenuation_db > VGA_MAX_ATTENUATION_DB)) {
        return false;
    }

    *command = (uint8_t)(attenuation_db << VGA_COMMAND_ATTENUATION_SHIFT);
    return true;
}
