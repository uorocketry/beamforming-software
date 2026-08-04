#include "rf/commands.h"

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

static void test_known_phase_command(void)
{
    uint8_t stateWordTableIndex = 0u;
    assert(phase_state_from_millidegrees(205300u, &stateWordTableIndex));
    assert(stateWordTableIndex == 146u);

    const optimizedPhaseState_e phaseState =
        GetOptimizedPhaseState(stateWordTableIndex);
    assert(phaseState == OPTIMIZED_STATE_146);
    assert(phaseState == 0b010001101);
    assert(MakePSCommand(phaseState, 0b0011) == 0x162cu);

    assert(GetOptimizedPhaseState(1u) == OPTIMIZED_STATE_1);
    assert(OPTIMIZED_STATE_1 == 0b100000001);
    assert(MakePSCommand(OPTIMIZED_STATE_1, 0b0011) == 0x101cu);
}

static void test_phase_boundaries(void)
{
    uint8_t stateWordTableIndex = 0xffu;

    assert(phase_state_from_millidegrees(0u, &stateWordTableIndex));
    assert(stateWordTableIndex == 0u);
    assert(MakePSCommand(GetOptimizedPhaseState(stateWordTableIndex), 0b0011)
        == 0x000cu);

    assert(phase_state_from_millidegrees(360000u, &stateWordTableIndex));
    assert(stateWordTableIndex == 0u);
    assert(!phase_state_from_millidegrees(360001u, &stateWordTableIndex));
    assert(!phase_state_from_millidegrees(0u, NULL));
}

static void test_every_phase_state(void)
{
    for (uint16_t index = 0u; index < PHASE_STATE_COUNT; ++index) {
        const optimizedPhaseState_e phaseState =
            GetOptimizedPhaseState((uint8_t)index);
        const uint16_t stateWord = (uint16_t)phaseState;
        assert(stateWord < (1u << PHASE_CONTROL_WORD_BITS));

        const uint16_t command = MakePSCommand(phaseState, 0b1111);
        assert(command <= PHASE_COMMAND_MAX);

        const bool expectedOptBit =
            (stateWord & PHASE_CONTROL_WORD_OPTION_MASK) != 0u;
        const bool encodedOptBit =
            (command & PHASE_COMMAND_OPTION_MASK) != 0u;
        assert(expectedOptBit == encodedOptBit);
    }

    assert(GetOptimizedPhaseState(71u) == OPTIMIZED_STATE_71);
    assert(GetOptimizedPhaseState(72u) == OPTIMIZED_STATE_72);
    assert(OPTIMIZED_STATE_71 == OPTIMIZED_STATE_72);
    assert(GetOptimizedPhaseState(255u) == OPTIMIZED_STATE_255);
}

static void test_bit_reversal(void)
{
    assert(reverseBits(0x92u, 8u) == 0x49u);
    assert(reverseBits(0x03u, 4u) == 0x0cu);
    assert(reverseBits(0xffffu, 0u) == 0u);
}

static void test_vga_commands(void)
{
    for (uint8_t attenuation = 0u; attenuation <= VGA_MAX_ATTENUATION_DB; ++attenuation) {
        uint8_t command = 0u;
        assert(MakeVGACommand(attenuation, &command));
        assert(command == (uint8_t)(attenuation << VGA_COMMAND_ATTENUATION_SHIFT));
    }

    uint8_t command = 0u;
    assert(MakeVGACommand(3u, &command));
    assert(command == 0x0cu);
    assert(MakeVGACommand(23u, &command));
    assert(command == 0x5cu);
    assert(!MakeVGACommand(24u, &command));
    assert(!MakeVGACommand(0u, NULL));
}

int main(void)
{
    test_known_phase_command();
    test_phase_boundaries();
    test_every_phase_state();
    test_bit_reversal();
    test_vga_commands();

    puts("RF command tests passed");
    return 0;
}
