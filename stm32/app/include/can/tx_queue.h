#ifndef CAN_TX_QUEUE_H
#define CAN_TX_QUEUE_H

#include "can/protocol.h"

#include <stdbool.h>
#include <stdint.h>

#define CAN_TX_QUEUE_CAPACITY 8u

/* Lower numeric value means higher transmit priority. */
typedef enum can_tx_priority {
    CAN_TX_PRIORITY_ERROR = 0,
    CAN_TX_PRIORITY_ACK = 1,
    CAN_TX_PRIORITY_REQUESTED_STATUS = 2,
    CAN_TX_PRIORITY_TELEMETRY = 3,
    CAN_TX_PRIORITY_COUNT = 4
} can_tx_priority_t;

typedef struct can_tx_queue_entry {
    can_frame_t frame;
    can_tx_priority_t priority;
} can_tx_queue_entry_t;

/*
 * Bounded, prioritized transmit queue.
 *
 * Lower numeric priority wins; FIFO order is preserved within an equal
 * priority. This is a pure data structure: it performs no hardware access and
 * assumes the caller serializes against any other context (the ISR). It is
 * host-testable without libopencm3.
 */
typedef struct can_tx_queue {
    can_tx_queue_entry_t entries[CAN_TX_QUEUE_CAPACITY];
    volatile uint8_t count;
} can_tx_queue_t;

void can_tx_queue_init(can_tx_queue_t *queue);

bool can_tx_priority_valid(can_tx_priority_t priority);

/* Caller must serialize access (e.g. interrupts masked). */
bool can_tx_queue_push_locked(
    can_tx_queue_t *queue,
    const can_frame_t *frame,
    can_tx_priority_t priority);

/* Returns a copy of the highest-priority frame and its array index. */
bool can_tx_queue_peek_highest_locked(
    const can_tx_queue_t *queue,
    can_frame_t *frame,
    uint8_t *entry_index);

/* Removes the entry previously returned by peek_highest_locked(). */
void can_tx_queue_remove_locked(can_tx_queue_t *queue, uint8_t entry_index);

/* Returns the priority of the highest-priority queued frame. */
bool can_tx_queue_get_highest_priority_locked(
    const can_tx_queue_t *queue,
    can_tx_priority_t *priority);

/*
 * Priority-aware eviction for a full queue. Returns true and inserts the
 * incoming frame if it outranks the lowest-priority queued frame (that frame
 * is evicted, preserving survivor order; the incoming frame is appended).
 * Equal-priority queued entries always win.
 */
bool can_tx_queue_replace_lower_priority_locked(
    can_tx_queue_t *queue,
    const can_frame_t *frame,
    can_tx_priority_t priority);

uint8_t can_tx_queue_count(const can_tx_queue_t *queue);

#endif /* CAN_TX_QUEUE_H */
