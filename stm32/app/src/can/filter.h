#ifndef CAN_FILTER_H
#define CAN_FILTER_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Configure two bxCAN filter banks:
 *
 * Bank 0:
 *   Any message type and sequence
 *   Destination = this receiver
 *   Source = controller node 0
 *   Extended data frames only
 *
 * Bank 1:
 *   Type = ENTER_SAFE
 *   Destination = broadcast node 31
 *   Source = controller node 0
 *   Extended data frames only
 */
bool can_filter_configure(uint8_t self_node);

#endif
