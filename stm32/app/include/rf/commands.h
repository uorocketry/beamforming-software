#ifndef RF_COMMANDS_H
#define RF_COMMANDS_H

#include "rf/limits.h"
#include "rf/phase_states_2_4ghz.h"

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
#define VGA_COMMAND_ATTENUATION_SHIFT 2u

uint16_t reverseBits(uint16_t word, uint8_t numBits);
optimizedPhaseState_e GetOptimizedPhaseState(uint8_t stateWordTableIndex);
uint16_t MakePSCommand(optimizedPhaseState_e phaseState, uint8_t unitAddressWord);
bool MakeVGACommand(uint8_t attenuationDb, uint8_t *command);

bool phase_state_from_millidegrees(
    uint32_t requested_shift_millidegrees,
    uint8_t *phase_state);

#endif
