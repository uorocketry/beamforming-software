#ifndef CAN_BUS_H
#define CAN_BUS_H

#include "can_protocol.h"

#include <stdbool.h>
#include <stdint.h>

/* Software TX-queue priority. Lower numeric value = higher priority. */
typedef enum can_tx_priority {
    CAN_TX_PRIORITY_ERROR = 0,
    CAN_TX_PRIORITY_ACK = 1,
    CAN_TX_PRIORITY_REQUESTED_STATUS = 2,
    CAN_TX_PRIORITY_TELEMETRY = 3,
    CAN_TX_PRIORITY_COUNT = 4
} can_tx_priority_t;

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
