/* Host test for the prioritized TX queue (can_tx_queue.c). No libopencm3. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "can_tx_queue.h"

static can_frame_t frame_with(uint32_t id, uint8_t tag)
{
    can_frame_t f;
    memset(&f, 0, sizeof(f));
    f.id = id;
    f.extended = true;
    f.remote = false;
    f.length = 1u;
    f.data[0] = tag;
    return f;
}

static void test_init_empty(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    assert(can_tx_queue_count(&q) == 0u);
    can_frame_t out;
    uint8_t idx;
    assert(!can_tx_queue_peek_highest_locked(&q, &out, &idx));
    printf("ok init_empty\n");
}

static void test_fifo_within_priority(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    assert(can_tx_queue_push_locked(&q, &(can_frame_t){0}, CAN_TX_PRIORITY_TELEMETRY));
    /* push three frames of equal priority */
    can_frame_t a = frame_with(1, 0xAA);
    can_frame_t b = frame_with(2, 0xBB);
    can_frame_t c = frame_with(3, 0xCC);
    assert(can_tx_queue_push_locked(&q, &a, CAN_TX_PRIORITY_TELEMETRY));
    assert(can_tx_queue_push_locked(&q, &b, CAN_TX_PRIORITY_TELEMETRY));
    assert(can_tx_queue_push_locked(&q, &c, CAN_TX_PRIORITY_TELEMETRY));
    /* first entry (index 0) is a zeroed frame; pop it off first */
    can_frame_t out;
    uint8_t idx;
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    can_tx_queue_remove_locked(&q, idx);
    /* now FIFO: a, b, c */
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0xAA);
    can_tx_queue_remove_locked(&q, idx);
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0xBB);
    can_tx_queue_remove_locked(&q, idx);
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0xCC);
    can_tx_queue_remove_locked(&q, idx);
    assert(can_tx_queue_count(&q) == 0u);
    printf("ok fifo_within_priority\n");
}

static void test_priority_ordering(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    /* telemetry pushed first, then ACK; ACK (higher priority) must come out first */
    can_frame_t tele = frame_with(10, 0x10);
    can_frame_t ack = frame_with(11, 0x11);
    can_frame_t err = frame_with(12, 0x12);
    assert(can_tx_queue_push_locked(&q, &tele, CAN_TX_PRIORITY_TELEMETRY));
    assert(can_tx_queue_push_locked(&q, &ack, CAN_TX_PRIORITY_ACK));
    assert(can_tx_queue_push_locked(&q, &err, CAN_TX_PRIORITY_ERROR));

    can_tx_priority_t prio;
    assert(can_tx_queue_get_highest_priority_locked(&q, &prio));
    assert(prio == CAN_TX_PRIORITY_ERROR);

    can_frame_t out;
    uint8_t idx;
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0x12);  /* ERROR */
    can_tx_queue_remove_locked(&q, idx);
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0x11);  /* ACK */
    can_tx_queue_remove_locked(&q, idx);
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0x10);  /* TELEMETRY */
    can_tx_queue_remove_locked(&q, idx);
    printf("ok priority_ordering\n");
}

static void test_full_queue_rejects(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    for (uint8_t i = 0u; i < CAN_TX_QUEUE_CAPACITY; ++i) {
        can_frame_t f = frame_with(i, i);
        assert(can_tx_queue_push_locked(&q, &f, CAN_TX_PRIORITY_TELEMETRY));
    }
    can_frame_t extra = frame_with(99, 0xEE);
    assert(!can_tx_queue_push_locked(&q, &extra, CAN_TX_PRIORITY_TELEMETRY));
    assert(can_tx_queue_count(&q) == CAN_TX_QUEUE_CAPACITY);
    printf("ok full_queue_rejects\n");
}

static void test_eviction_preserves_order(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    /* fill with telemetry */
    for (uint8_t i = 0u; i < CAN_TX_QUEUE_CAPACITY; ++i) {
        can_frame_t f = frame_with(i, (uint8_t)(0x10 + i));
        assert(can_tx_queue_push_locked(&q, &f, CAN_TX_PRIORITY_TELEMETRY));
    }
    /* evict with an ACK (higher priority); the newest lowest-priority (index 7) is replaced */
    can_frame_t ack = frame_with(200, 0x55);
    assert(can_tx_queue_replace_lower_priority_locked(&q, &ack, CAN_TX_PRIORITY_ACK));
    assert(can_tx_queue_count(&q) == CAN_TX_QUEUE_CAPACITY);
    /* the ACK must be the highest priority, and the frame at index 7 must be the ACK */
    can_frame_t out;
    uint8_t idx;
    assert(can_tx_queue_peek_highest_locked(&q, &out, &idx));
    assert(out.data[0] == 0x55);
    assert(idx == CAN_TX_QUEUE_CAPACITY - 1u);  /* appended last */
    printf("ok eviction_preserves_order\n");
}

static void test_no_eviction_on_equal_priority(void)
{
    can_tx_queue_t q;
    can_tx_queue_init(&q);
    for (uint8_t i = 0u; i < CAN_TX_QUEUE_CAPACITY; ++i) {
        can_frame_t f = frame_with(i, i);
        assert(can_tx_queue_push_locked(&q, &f, CAN_TX_PRIORITY_TELEMETRY));
    }
    /* equal-priority incoming must not evict */
    can_frame_t new_frame = frame_with(77, 0x77);
    assert(!can_tx_queue_replace_lower_priority_locked(&q, &new_frame, CAN_TX_PRIORITY_TELEMETRY));
    printf("ok no_eviction_on_equal_priority\n");
}

int main(void)
{
    test_init_empty();
    test_fifo_within_priority();
    test_priority_ordering();
    test_full_queue_rejects();
    test_eviction_preserves_order();
    test_no_eviction_on_equal_priority();
    printf("ALL CAN_TX_QUEUE TESTS PASSED\n");
    return 0;
}
