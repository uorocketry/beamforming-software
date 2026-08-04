#include "can/tx_queue.h"

#include <stddef.h>
#include <string.h>

_Static_assert(
    (CAN_TX_QUEUE_CAPACITY & (CAN_TX_QUEUE_CAPACITY - 1u)) == 0u,
    "CAN_TX_QUEUE_CAPACITY must be a power of two");

static void can_tx_compiler_barrier(void)
{
    __asm__ volatile ("" ::: "memory");
}

void can_tx_queue_init(can_tx_queue_t *queue)
{
    if (queue == NULL) {
        return;
    }
    memset(queue, 0, sizeof(*queue));
}

bool can_tx_priority_valid(can_tx_priority_t priority)
{
    return ((uint32_t)priority < (uint32_t)CAN_TX_PRIORITY_COUNT);
}

bool can_tx_queue_push_locked(
    can_tx_queue_t *queue,
    const can_frame_t *frame,
    can_tx_priority_t priority)
{
    uint8_t index;

    if ((queue == NULL) ||
        (frame == NULL) ||
        !can_tx_priority_valid(priority)) {
        return false;
    }

    index = queue->count;
    if (index >= CAN_TX_QUEUE_CAPACITY) {
        return false;
    }

    queue->entries[index].frame = *frame;
    queue->entries[index].priority = priority;

    can_tx_compiler_barrier();
    queue->count = (uint8_t)(index + 1u);

    return true;
}

bool can_tx_queue_peek_highest_locked(
    const can_tx_queue_t *queue,
    can_frame_t *frame,
    uint8_t *entry_index)
{
    uint8_t count;
    uint8_t selected;
    uint8_t index;

    if ((queue == NULL) ||
        (frame == NULL) ||
        (entry_index == NULL)) {
        return false;
    }

    count = queue->count;
    if (count == 0u) {
        return false;
    }

    selected = 0u;
    for (index = 1u; index < count; ++index) {
        if (queue->entries[index].priority <
            queue->entries[selected].priority) {
            selected = index;
        }
    }

    *frame = queue->entries[selected].frame;
    *entry_index = selected;
    return true;
}

void can_tx_queue_remove_locked(can_tx_queue_t *queue, uint8_t entry_index)
{
    uint8_t count;
    uint8_t index;

    if (queue == NULL) {
        return;
    }

    count = queue->count;
    if ((count == 0u) || (entry_index >= count)) {
        return;
    }

    for (index = entry_index; (uint8_t)(index + 1u) < count; ++index) {
        queue->entries[index] = queue->entries[index + 1u];
    }

    can_tx_compiler_barrier();
    queue->count = (uint8_t)(count - 1u);
}

bool can_tx_queue_get_highest_priority_locked(
    const can_tx_queue_t *queue,
    can_tx_priority_t *priority)
{
    uint8_t count;
    uint8_t selected = 0u;
    uint8_t index;

    if ((queue == NULL) || (priority == NULL)) {
        return false;
    }

    count = queue->count;
    if (count == 0u) {
        return false;
    }

    for (index = 1u; index < count; ++index) {
        if (queue->entries[index].priority <
            queue->entries[selected].priority) {
            selected = index;
        }
    }

    *priority = queue->entries[selected].priority;
    return true;
}

bool can_tx_queue_replace_lower_priority_locked(
    can_tx_queue_t *queue,
    const can_frame_t *frame,
    can_tx_priority_t priority)
{
    uint8_t count;
    uint8_t candidate;
    uint8_t index;

    if ((queue == NULL) ||
        (frame == NULL) ||
        !can_tx_priority_valid(priority)) {
        return false;
    }

    count = queue->count;
    if (count != CAN_TX_QUEUE_CAPACITY) {
        return false;
    }

    candidate = count;

    /* Search backward so the newest lowest-priority frame is selected. */
    for (index = count; index > 0u; --index) {
        const uint8_t current = (uint8_t)(index - 1u);

        /* Numerically larger = lower priority; equal priority is kept. */
        if (queue->entries[current].priority <= priority) {
            continue;
        }

        if ((candidate == count) ||
            (queue->entries[current].priority >
             queue->entries[candidate].priority)) {
            candidate = current;
        }
    }

    if (candidate == count) {
        return false;
    }

    /* Remove the evicted entry, preserving the order of survivors. */
    for (index = candidate; (uint8_t)(index + 1u) < count; ++index) {
        queue->entries[index] = queue->entries[index + 1u];
    }

    /* Append the incoming frame as the newest entry. */
    queue->entries[count - 1u].frame = *frame;
    queue->entries[count - 1u].priority = priority;

    can_tx_compiler_barrier();
    return true;
}

uint8_t can_tx_queue_count(const can_tx_queue_t *queue)
{
    return (queue == NULL) ? 0u : queue->count;
}
