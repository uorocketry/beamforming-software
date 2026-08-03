#include "beamforming_protocol.h"
#include "phase_lookup_2_4_ghz.h"

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

static void test_known_phase_command(void)
{
    uint8_t state = 0u;
    assert(phase_state_from_millidegrees(205300u, &state));
    assert(state == 146u);
    assert(PE44820_OPTIMIZED_STATE_146 == 0x08d);
    assert(pe44820_optimized_state_by_index_2_4_ghz[state]
        == PE44820_OPTIMIZED_STATE_146);
    assert(phase_control_word_from_state(state)
        == (uint16_t)PE44820_OPTIMIZED_STATE_146);

    uint16_t command = 0;
    assert(phase_command_from_millidegrees(205300u, 3u, &command));
    assert(command == 0x162cu);

    assert(PE44820_OPTIMIZED_STATE_1 == 0x101);
    assert(pe44820_optimized_state_by_index_2_4_ghz[1u]
        == PE44820_OPTIMIZED_STATE_1);
    assert(phase_control_word_from_state(1u)
        == (uint16_t)PE44820_OPTIMIZED_STATE_1);
    assert(phase_command_from_state(1u, 3u, &command));
    assert(command == 0x101cu);
}

static void test_phase_boundaries(void)
{
    uint16_t command = 0xffffu;

    assert(phase_command_from_millidegrees(0u, 3u, &command));
    assert(command == 0x000cu);

    assert(phase_command_from_millidegrees(360000u, 3u, &command));
    assert(command == 0x000cu);

    assert(!phase_command_from_millidegrees(360001u, 3u, &command));
    assert(!phase_command_from_millidegrees(0u, 16u, &command));
    assert(!phase_command_from_millidegrees(0u, 0u, NULL));

    uint8_t state = 0xffu;
    assert(phase_state_from_millidegrees(360000u, &state));
    assert(state == 0u);
    assert(!phase_state_from_millidegrees(360001u, &state));
    assert(!phase_state_from_millidegrees(0u, NULL));
}

static void test_every_phase_state(void)
{
    for (uint16_t state = 0; state < PHASE_STATE_COUNT; ++state) {
        const uint16_t control_word = phase_control_word_from_state((uint8_t)state);
        assert(control_word < (1u << PHASE_CONTROL_WORD_BITS));

        uint16_t command = 0;
        assert(phase_command_from_state((uint8_t)state, 0x0fu, &command));
        assert(command <= PHASE_COMMAND_MAX);

        const bool expected_option =
            (control_word & PHASE_CONTROL_WORD_OPTION_MASK) != 0u;
        const bool encoded_option = (command & PHASE_COMMAND_OPTION_MASK) != 0u;
        assert(expected_option == encoded_option);
    }

    assert(phase_control_word_from_state(71u) == 0x147u);
    assert(phase_control_word_from_state(72u) == 0x147u);
    assert(phase_control_word_from_state(255u) == 0x1f9u);
}

static void test_bit_reversal(void)
{
    assert(beamforming_reverse_bits(0x92u, 8u) == 0x49u);
    assert(beamforming_reverse_bits(0x03u, 4u) == 0x0cu);
    assert(beamforming_reverse_bits(0xffffu, 0u) == 0u);
}

static void test_vga_commands(void)
{
    for (uint8_t attenuation = 0u; attenuation <= VGA_MAX_ATTENUATION_DB; ++attenuation) {
        uint8_t command = 0u;
        assert(vga_command_from_attenuation(attenuation, &command));
        assert(command == (uint8_t)(attenuation << VGA_COMMAND_ATTENUATION_SHIFT));
    }

    uint8_t command = 0u;
    assert(vga_command_from_attenuation(3u, &command));
    assert(command == 0x0cu);
    assert(vga_command_from_attenuation(23u, &command));
    assert(command == 0x5cu);
    assert(!vga_command_from_attenuation(24u, &command));
    assert(!vga_command_from_attenuation(0u, NULL));
}

int main(void)
{
    test_known_phase_command();
    test_phase_boundaries();
    test_every_phase_state();
    test_bit_reversal();
    test_vga_commands();

    puts("protocol tests passed");
    return 0;
}
