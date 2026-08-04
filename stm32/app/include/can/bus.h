#ifndef CAN_BUS_H
#define CAN_BUS_H

#include "can/protocol.h"
#include "can/tx_queue.h"

#include <stdbool.h>
#include <stdint.h>

bool can_bus_setup(uint8_t self_node);
bool can_bus_receive(can_frame_t *frame);

/*
 * Returns true when the frame was accepted either by a hardware mailbox or
 * by the software TX queue.
 *
 * Returns false for:
 * - Invalid arguments/frame
 * - CAN not initialized
 * - Software queue full while no hardware capacity is available
 */
bool can_bus_send(const can_frame_t *frame, can_tx_priority_t priority);

uint16_t can_bus_rx_dropped(void);
uint16_t can_bus_tx_dropped(void);
bool can_bus_is_bus_off(void);

#endif
