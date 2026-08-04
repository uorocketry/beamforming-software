#include "can/bus.h"

#include "platform/board.h"

#include "filter.h"
#include "can/rx_queue.h"
#include "can/tx_queue.h"
#include "platform/clock.h"
#include "platform/firmware_config.h"

#include <libopencm3/cm3/cortex.h>
#include <libopencm3/cm3/nvic.h>
#include <libopencm3/stm32/can.h>
#include <libopencm3/stm32/gpio.h>
#include <libopencm3/stm32/rcc.h>

#include <limits.h>
#include <stddef.h>
#include <string.h>

#define CAN_RECEIVE_FIFO_INDEX 0u
#define CAN_BITRATE_PRESCALER \
    (FIRMWARE_CORE_CLOCK_HZ / (CAN_BUS_BITRATE * CAN_TIME_QUANTA_PER_BIT))

_Static_assert(
    (FIRMWARE_CORE_CLOCK_HZ % (CAN_BUS_BITRATE * CAN_TIME_QUANTA_PER_BIT)) == 0u,
    "CAN bitrate must divide the firmware core clock exactly");
_Static_assert(CAN_BITRATE_PRESCALER == 6u, "unexpected 500 kbit/s CAN prescaler");

#define CAN_TX_COMPLETED_MASK \
    (CAN_TSR_RQCP0 | CAN_TSR_RQCP1 | CAN_TSR_RQCP2)

/*
 * The prioritized TX queue lives in can/tx_queue.c (host-testable, no
 * libopencm3). This file owns the bxCAN register/ISR integration around it:
 * producer = main (interrupts masked), consumer = cec_can_isr().
 */
static can_rx_queue_t receive_queue;
static can_tx_queue_t transmit_queue;
static volatile uint16_t hardware_rx_dropped;
static uint16_t transmit_dropped;
static bool initialized;

static uint16_t saturating_add_u16(uint16_t left, uint16_t right)
{
    return (right > (uint16_t)(UINT16_MAX - left))
        ? UINT16_MAX
        : (uint16_t)(left + right);
}

static void increment_saturating(volatile uint16_t *counter)
{
    if (*counter != UINT16_MAX) {
        ++(*counter);
    }
}

static void increment_transmit_dropped(void)
{
    if (transmit_dropped != UINT16_MAX) {
        ++transmit_dropped;
    }
}

static bool can_bus_try_transmit_frame(const can_frame_t *frame)
{
    uint8_t data[CAN_MAX_DATA_LENGTH] = {0};

    if (frame == NULL) {
        return false;
    }

    memcpy(data, frame->data, frame->length);

    return can_transmit(
               CAN1,
               frame->id,
               true,
               false,
               frame->length,
               data) >= 0;
}

/*
 * May be called from cec_can_isr() (main cannot execute) or from main while
 * interrupts are masked. A frame stays queued until can_transmit() accepts it.
 */
static void can_bus_drain_tx_queue_locked(void)
{
    while ((can_tx_queue_count(&transmit_queue) != 0u) &&
           can_available_mailbox(CAN1)) {
        can_frame_t frame;
        uint8_t entry_index;

        if (!can_tx_queue_peek_highest_locked(
                &transmit_queue,
                &frame,
                &entry_index)) {
            return;
        }

        if (!can_bus_try_transmit_frame(&frame)) {
            /* Leave the frame queued; do not lose it. */
            return;
        }

        can_tx_queue_remove_locked(&transmit_queue, entry_index);
    }
}

/*
 * Transmit exactly one queued frame (the highest-priority one) if a mailbox
 * is available. Returns true if a frame was submitted. Used by the full-queue
 * path so an incoming frame can be reconsidered against the highest-priority
 * queued frame.
 */
static bool can_bus_drain_one_tx_frame_locked(void)
{
    can_frame_t frame;
    uint8_t entry_index;

    if ((can_tx_queue_count(&transmit_queue) == 0u) ||
        !can_available_mailbox(CAN1)) {
        return false;
    }

    if (!can_tx_queue_peek_highest_locked(
            &transmit_queue,
            &frame,
            &entry_index)) {
        return false;
    }

    if (!can_bus_try_transmit_frame(&frame)) {
        return false;
    }

    can_tx_queue_remove_locked(&transmit_queue, entry_index);
    return true;
}

bool can_bus_setup(uint8_t self_node)
{
    if (self_node < CAN_NODE_MIN || self_node > CAN_NODE_MAX) {
        return false;
    }

    initialized = false;
    hardware_rx_dropped = 0u;
    transmit_dropped = 0u;
    can_rx_queue_init(&receive_queue);
    can_tx_queue_init(&transmit_queue);

    rcc_periph_clock_enable(RCC_GPIOA);
    rcc_periph_clock_enable(RCC_CAN1);

    gpio_mode_setup(
        BOARD_CAN_PORT,
        GPIO_MODE_AF,
        GPIO_PUPD_PULLUP,
        BOARD_CAN_RX_PIN | BOARD_CAN_TX_PIN);
    gpio_set_af(
        BOARD_CAN_PORT,
        BOARD_CAN_AF,
        BOARD_CAN_RX_PIN | BOARD_CAN_TX_PIN);
    gpio_set_output_options(
        BOARD_CAN_PORT,
        GPIO_OTYPE_PP,
        GPIO_OSPEED_HIGH,
        BOARD_CAN_TX_PIN);

    can_reset(CAN1);
    if (can_init(
            CAN1,
            false,      /* ttcm */
            true,       /* abom */
            false,      /* awum */
            false,      /* nart: automatic retransmission enabled */
            true,       /* rflm */
            true,       /* txfp: request-order mailbox priority */
            CAN_BTR_SJW_1TQ,
            CAN_BTR_TS1_13TQ,
            CAN_BTR_TS2_2TQ,
            CAN_BITRATE_PRESCALER,
            false,      /* loopback */
            false) != 0) {   /* silent */
        return false;
    }

    if (!can_filter_configure(self_node)) {
        return false;
    }

    can_enable_irq(CAN1, CAN_IER_TMEIE | CAN_IER_FMPIE0 | CAN_IER_FOVIE0);
    nvic_clear_pending_irq(NVIC_CEC_CAN_IRQ);
    nvic_enable_irq(NVIC_CEC_CAN_IRQ);
    initialized = true;
    return true;
}

bool can_bus_receive(can_frame_t *frame)
{
    if (!initialized || frame == NULL) {
        return false;
    }

    return can_rx_queue_pop(&receive_queue, frame);
}

bool can_bus_send(const can_frame_t *frame, can_tx_priority_t priority)
{
    uint32_t previous_interrupt_mask;
    bool accepted = false;

    if (!initialized ||
        (frame == NULL) ||
        !frame->extended ||
        frame->remote ||
        (frame->id > CAN_EXTENDED_ID_MAX) ||
        (frame->length > CAN_MAX_DATA_LENGTH) ||
        !can_tx_priority_valid(priority)) {
        return false;
    }

    /*
     * Both main and cec_can_isr() call can_transmit(). Serialize hardware
     * mailbox selection and all TX-queue mutation. cm_mask_interrupts()
     * returns the old PRIMASK state, so this is safe even when the caller
     * already has interrupts masked.
     */
    previous_interrupt_mask = cm_mask_interrupts(1u);

    /* Do not bypass already queued traffic (keeps priority order). */
    if ((can_tx_queue_count(&transmit_queue) == 0u) &&
        can_bus_try_transmit_frame(frame)) {
        accepted = true;
    } else if (can_tx_queue_count(&transmit_queue) < CAN_TX_QUEUE_CAPACITY) {
        /* Queue has room: enqueue, then drain any now-available mailbox. */
        accepted = can_tx_queue_push_locked(&transmit_queue, frame, priority);
        if (accepted) {
            can_bus_drain_tx_queue_locked();
        }
    } else {
        /*
         * Queue is full. If a mailbox is available, decide between the new
         * frame and the highest-priority queued frame so a high-priority
         * incoming frame is not queued behind a lower-priority one.
         */
        can_tx_priority_t queued_priority;

        if (can_available_mailbox(CAN1) &&
            can_tx_queue_get_highest_priority_locked(
                &transmit_queue,
                &queued_priority)) {
            if (priority < queued_priority) {
                /* Incoming is globally highest priority: transmit it now. */
                accepted = can_bus_try_transmit_frame(frame);
            } else {
                /*
                 * Older frame wins on equal priority: make room by draining
                 * one, then insert the incoming frame.
                 */
                if (can_bus_drain_one_tx_frame_locked()) {
                    accepted = can_tx_queue_push_locked(
                        &transmit_queue, frame, priority);
                    if (accepted) {
                        can_bus_drain_tx_queue_locked();
                    }
                } else {
                    accepted = false;
                }
            }
        } else {
            /*
             * All mailboxes busy and queue full: priority-aware eviction so
             * ERROR/ACK are not dropped behind a telemetry burst.
             *
             * Exactly one frame is dropped here: the evicted lower-priority
             * frame on success, or the incoming frame when nothing is lower
             * priority than it.
             */
            accepted = can_tx_queue_replace_lower_priority_locked(
                &transmit_queue, frame, priority);
            increment_transmit_dropped();
        }
    }

    (void)cm_mask_interrupts(previous_interrupt_mask);

    return accepted;
}

uint16_t can_bus_rx_dropped(void)
{
    return saturating_add_u16(
        hardware_rx_dropped,
        can_rx_queue_dropped(&receive_queue));
}

uint16_t can_bus_tx_dropped(void)
{
    return transmit_dropped;
}

bool can_bus_is_bus_off(void)
{
    return initialized && ((CAN_ESR(CAN1) & CAN_ESR_BOFF) != 0u);
}

void cec_can_isr(void)
{
    const uint32_t completed_mailboxes =
        CAN_TSR(CAN1) & CAN_TX_COMPLETED_MASK;

    /* RQCP0/1/2 = bits 0/8/16; write-one-to-clear acknowledges TX IRQ. */
    if (completed_mailboxes != 0u) {
        CAN_TSR(CAN1) = completed_mailboxes;
    }

    if ((CAN_RF0R(CAN1) & CAN_RF0R_FOVR0) != 0u) {
        increment_saturating(&hardware_rx_dropped);
        CAN_RF0R(CAN1) |= CAN_RF0R_FOVR0;
    }

    while (can_fifo_pending(CAN1, CAN_RECEIVE_FIFO_INDEX) > 0u) {
        can_frame_t frame = {0};
        uint8_t filter_match_index = 0u;

        can_receive(
            CAN1,
            CAN_RECEIVE_FIFO_INDEX,
            true,
            &frame.id,
            &frame.extended,
            &frame.remote,
            &filter_match_index,
            &frame.length,
            frame.data,
            NULL);

        (void)filter_match_index;
        (void)can_rx_queue_push_isr(&receive_queue, &frame);
    }

    /* Fill every currently available mailbox from the prioritized queue. */
    can_bus_drain_tx_queue_locked();
}
