#include "can_filter.h"

#include "can_protocol.h"

#include <libopencm3/stm32/can.h>

/*
 * bxCAN 32-bit filter-register representation:
 *
 * Bits 31:3  Extended identifier
 * Bit 2      IDE
 * Bit 1      RTR
 * Bit 0      Reserved
 */
#define CAN_FILTER_IDE_BIT (1u << 2)
#define CAN_FILTER_RTR_BIT (1u << 1)

#define CAN_FILTER_BANK_UNICAST 0u
#define CAN_FILTER_BANK_BROADCAST_SAFE 1u
/* libopencm3 CAN_FIFO0 is a receive-register offset, not FIFO index 0. */
#define CAN_FILTER_FIFO0_INDEX 0u

static uint32_t can_filter_pack_extended_id(uint32_t id)
{
    return
        ((id & CAN_EXTENDED_ID_MAX) << 3) |
        CAN_FILTER_IDE_BIT;
}

static uint32_t can_filter_pack_extended_mask(uint32_t mask)
{
    /*
     * Setting IDE and RTR in the mask means:
     *
     * - IDE must match the ID word's IDE=1: extended frames only.
     * - RTR must match the ID word's RTR=0: data frames only.
     */
    return
        ((mask & CAN_EXTENDED_ID_MAX) << 3) |
        CAN_FILTER_IDE_BIT |
        CAN_FILTER_RTR_BIT;
}

bool can_filter_configure(uint8_t self_node)
{
    uint32_t unicast_id;
    uint32_t unicast_mask;

    uint32_t broadcast_id;
    uint32_t broadcast_mask;

    if ((self_node < CAN_NODE_MIN) ||
        (self_node > CAN_NODE_MAX)) {
        return false;
    }

    /*
     * Unicast filter:
     *
     * Match destination and source.
     * Wildcard type and sequence.
     */
    unicast_id =
        ((uint32_t)self_node << CAN_ID_DESTINATION_SHIFT) |
        ((uint32_t)CAN_NODE_CONTROLLER << CAN_ID_SOURCE_SHIFT);

    unicast_mask =
        ((uint32_t)CAN_ID_NODE_MASK << CAN_ID_DESTINATION_SHIFT) |
        ((uint32_t)CAN_ID_NODE_MASK << CAN_ID_SOURCE_SHIFT);

    can_filter_id_mask_32bit_init(
        CAN_FILTER_BANK_UNICAST,
        can_filter_pack_extended_id(unicast_id),
        can_filter_pack_extended_mask(unicast_mask),
        CAN_FILTER_FIFO0_INDEX,
        true);

    /*
     * Broadcast filter:
     *
     * Match ENTER_SAFE, destination 31 and controller source 0.
     * Wildcard sequence.
     *
     * Other broadcast message types are rejected in hardware and are also
     * rejected defensively by can_protocol_decode_command().
     */
    broadcast_id =
        ((uint32_t)CAN_MESSAGE_ENTER_SAFE << CAN_ID_TYPE_SHIFT) |
        ((uint32_t)CAN_NODE_BROADCAST <<
         CAN_ID_DESTINATION_SHIFT) |
        ((uint32_t)CAN_NODE_CONTROLLER <<
         CAN_ID_SOURCE_SHIFT);

    broadcast_mask =
        ((uint32_t)CAN_ID_TYPE_MASK << CAN_ID_TYPE_SHIFT) |
        ((uint32_t)CAN_ID_NODE_MASK <<
         CAN_ID_DESTINATION_SHIFT) |
        ((uint32_t)CAN_ID_NODE_MASK <<
         CAN_ID_SOURCE_SHIFT);

    can_filter_id_mask_32bit_init(
        CAN_FILTER_BANK_BROADCAST_SAFE,
        can_filter_pack_extended_id(broadcast_id),
        can_filter_pack_extended_mask(broadcast_mask),
        CAN_FILTER_FIFO0_INDEX,
        true);

    return true;
}
