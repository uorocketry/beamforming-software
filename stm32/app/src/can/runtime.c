#include "can/runtime.h"

#include "can/bus.h"
#include "can/protocol.h"
#include "platform/retained_diagnostics.h"
#include "rf/execute.h"

#include <limits.h>
#include <stddef.h>
#include <string.h>

#define CAN_SPI_TIMEOUT_MILLIS 2u

/* Replays the last successful unicast command without repeating RF writes. */
typedef struct can_replay_cache {
    bool valid;
    can_command_t command;

    uint8_t request_length;
    uint8_t request_data[CAN_MAX_DATA_LENGTH];

    can_frame_t response;
} can_replay_cache_t;

typedef enum can_replay_result {
    CAN_REPLAY_MISS = 0,
    CAN_REPLAY_HIT = 1,
    CAN_REPLAY_SEQUENCE_REUSE = 2
} can_replay_result_t;

static can_replay_cache_t replay_cache;

static void replay_cache_invalidate(void)
{
    memset(&replay_cache, 0, sizeof(replay_cache));
}

static void increment_invalid_commands(can_runtime_t *runtime)
{
    if (runtime->invalid_commands != UINT16_MAX) {
        ++runtime->invalid_commands;
    }
}

static bool replay_command_key_equal(
    const can_command_t *left,
    const can_command_t *right)
{
    return
        (left->type == right->type) &&
        (left->destination == right->destination) &&
        (left->source == right->source) &&
        (left->sequence == right->sequence);
}

static can_replay_result_t replay_cache_lookup(
    const can_command_t *command,
    const can_frame_t *request,
    can_frame_t *cached_response)
{
    if ((command == NULL) || (request == NULL) || (cached_response == NULL)) {
        return CAN_REPLAY_MISS;
    }

    /* Broadcast commands never receive a response and are not replay-cached. */
    if (command->destination == CAN_NODE_BROADCAST) {
        return CAN_REPLAY_MISS;
    }

    if (!can_protocol_is_state_changing_type(command->type)) {
        return CAN_REPLAY_MISS;
    }

    if (!replay_cache.valid) {
        return CAN_REPLAY_MISS;
    }

    if (!replay_command_key_equal(command, &replay_cache.command)) {
        return CAN_REPLAY_MISS;
    }

    /*
     * A retry must be byte-for-byte identical to the original request:
     * same DLC and identical payload bytes. A same-key frame that differs
     * in any byte is sequence reuse, not a retry.
     */
    if (request->length != replay_cache.request_length) {
        return CAN_REPLAY_SEQUENCE_REUSE;
    }

    if (memcmp(request->data, replay_cache.request_data, request->length) != 0) {
        return CAN_REPLAY_SEQUENCE_REUSE;
    }

    *cached_response = replay_cache.response;
    return CAN_REPLAY_HIT;
}

static void replay_cache_store_ack(
    const can_command_t *command,
    const can_frame_t *request,
    const can_frame_t *ack)
{
    if ((command == NULL) || (request == NULL) || (ack == NULL)) {
        return;
    }

    if (command->destination == CAN_NODE_BROADCAST) {
        return;
    }

    if (!can_protocol_is_state_changing_type(command->type)) {
        return;
    }

    replay_cache.command = *command;
    replay_cache.request_length = request->length;

    memset(replay_cache.request_data, 0, sizeof(replay_cache.request_data));
    memcpy(replay_cache.request_data, request->data, request->length);

    replay_cache.response = *ack;
    replay_cache.valid = true;
}

static void send_ack(
    const can_runtime_t *runtime,
    const can_command_t *command,
    const can_frame_t *request)
{
    if (command->destination == CAN_NODE_BROADCAST) {
        return;
    }

    can_frame_t response = {0};
    if (can_protocol_make_ack(
            runtime->node_id,
            command->source,
            command->sequence,
            command->type,
            &response)) {
        /* Cache before transmit: a retry must replay, not re-run the RF step. */
        replay_cache_store_ack(command, request, &response);
        (void)can_bus_send(&response, CAN_TX_PRIORITY_ACK);
    }
}

static void send_error_for_command(
    const can_runtime_t *runtime,
    const can_command_t *command,
    can_command_result_t result)
{
    if (command->destination == CAN_NODE_BROADCAST) {
        return;
    }

    can_frame_t response = {0};
    if (can_protocol_make_error(
            runtime->node_id,
            command->source,
            command->sequence,
            command->type,
            result,
            &response)) {
        (void)can_bus_send(&response, CAN_TX_PRIORITY_ERROR);
    }
}

static void send_error_for_frame(
    const can_runtime_t *runtime,
    const can_frame_t *frame,
    can_decode_result_t decode_result)
{
    if (!frame->extended || frame->remote) {
        return;
    }

    can_message_type_t type = CAN_MESSAGE_TYPE_COUNT;
    uint8_t destination = 0u;
    uint8_t source = 0u;
    uint16_t sequence = 0u;
    if (!can_protocol_parse_id(
            frame->id,
            &type,
            &destination,
            &source,
            &sequence)
        || destination != runtime->node_id
        || source != CAN_NODE_CONTROLLER
        || type > CAN_MESSAGE_PING) {
        return;
    }

    can_frame_t response = {0};
    if (can_protocol_make_error(
            runtime->node_id,
            source,
            sequence,
            type,
            can_protocol_result_from_decode(decode_result),
            &response)) {
        (void)can_bus_send(&response, CAN_TX_PRIORITY_ERROR);
    }
}

static uint8_t health_flags(const can_runtime_t *runtime)
{
    uint8_t flags = CAN_HEALTH_NONE;

    if (runtime->clock_source == FIRMWARE_CLOCK_HSI48) {
        flags |= CAN_HEALTH_CLOCK_FALLBACK;
    }
    if (can_bus_rx_dropped() != 0u) {
        flags |= CAN_HEALTH_RX_DROPPED;
    }
    if (runtime->invalid_commands != 0u) {
        flags |= CAN_HEALTH_INVALID_COMMAND;
    }
    if (runtime->safe_lockout) {
        flags |= CAN_HEALTH_SAFE_LOCKOUT;
    }
    if (can_bus_is_bus_off()) {
        flags |= CAN_HEALTH_BUS_OFF;
    }
    if (can_bus_tx_dropped() != 0u) {
        flags |= CAN_HEALTH_TX_DROPPED;
    }

    return flags;
}

static void send_status(const can_runtime_t *runtime, const can_command_t *command)
{
    if (command->destination == CAN_NODE_BROADCAST) {
        return;
    }

    const can_status_payload_t status = {
        .node_id = runtime->node_id,
        .health_flags = health_flags(runtime),
        .rx_dropped = can_bus_rx_dropped(),
        .tx_dropped = can_bus_tx_dropped(),
        .invalid_commands = runtime->invalid_commands,
    };

    can_frame_t response = {0};
    if (can_protocol_make_status(
            runtime->node_id,
            command->source,
            command->sequence,
            &status,
            &response)) {
        (void)can_bus_send(&response, CAN_TX_PRIORITY_REQUESTED_STATUS);
    }
}

bool can_runtime_start(
    can_runtime_t *runtime,
    uint8_t node_id,
    firmware_clock_t clock_source,
    bool safe_lockout,
    const rf_state_t *initial_state,
    uint16_t initial_phase_command,
    uint8_t initial_vga_command)
{
    if (runtime == NULL
        || initial_state == NULL
        || node_id < CAN_NODE_MIN
        || node_id > CAN_NODE_MAX) {
        return false;
    }

    if (initial_state->attenuation_db > VGA_MAX_ATTENUATION_DB) {
        return false;
    }

    memset(runtime, 0, sizeof(*runtime));
    replay_cache_invalidate();
    runtime->state = *initial_state;
    runtime->last_phase_command = initial_phase_command;
    runtime->last_vga_command = initial_vga_command;
    runtime->node_id = node_id;
    runtime->clock_source = clock_source;
    runtime->safe_lockout = safe_lockout;

    return can_bus_setup(node_id);
}

bool can_runtime_service_next(can_runtime_t *runtime)
{
    if (runtime == NULL) {
        return false;
    }

    can_frame_t frame = {0};
    if (!can_bus_receive(&frame)) {
        return false;
    }

    can_command_t command = {0};
    const can_decode_result_t decode_result =
        can_protocol_decode_command(&frame, runtime->node_id, &command);

    if (decode_result == CAN_DECODE_IGNORED) {
        return true;
    }
    if (decode_result != CAN_DECODE_OK) {
        increment_invalid_commands(runtime);
        send_error_for_frame(runtime, &frame, decode_result);
        return true;
    }

    /* Replay check must precede PING, lockout, plan and hardware access. */
    can_frame_t cached_response = {0};
    const can_replay_result_t replay_result =
        replay_cache_lookup(&command, &frame, &cached_response);

    if (replay_result == CAN_REPLAY_HIT) {
        (void)can_bus_send(&cached_response, CAN_TX_PRIORITY_ACK);
        return true;
    }
    if (replay_result == CAN_REPLAY_SEQUENCE_REUSE) {
        increment_invalid_commands(runtime);
        send_error_for_command(runtime, &command, CAN_COMMAND_RESULT_SEQUENCE_REUSE);
        return true;
    }

    if (command.type == CAN_MESSAGE_PING) {
        send_status(runtime, &command);
        return true;
    }

    if (runtime->safe_lockout && command.type != CAN_MESSAGE_ENTER_SAFE) {
        send_error_for_command(runtime, &command, CAN_COMMAND_RESULT_BUSY);
        return true;
    }

    rf_plan_t plan = {0};
    const can_command_result_t plan_result =
        rf_plan_command(&command, &runtime->state, &plan);
    if (plan_result != CAN_COMMAND_RESULT_OK) {
        increment_invalid_commands(runtime);
        send_error_for_command(runtime, &command, plan_result);
        return true;
    }

    const firmware_fault_t execution_fault = rf_execute_plan(
        &plan,
        CAN_SPI_TIMEOUT_MILLIS,
        &runtime->last_phase_command,
        &runtime->last_vga_command);
    if (execution_fault != FIRMWARE_FAULT_NONE) {
        retained_diagnostics_set_fault(execution_fault);
        send_error_for_command(runtime, &command, CAN_COMMAND_RESULT_HARDWARE);
        return true;
    }
    runtime->state = plan.resulting_state;
    retained_diagnostics_set_commands(
        runtime->last_phase_command,
        runtime->last_vga_command);

    /*
     * A successful broadcast ENTER_SAFE changes hardware state but has no
     * ACK to cache. Any older cached ACK is no longer safe to replay.
     */
    if (command.destination == CAN_NODE_BROADCAST) {
        replay_cache_invalidate();
        return true;
    }

    send_ack(runtime, &command, &frame);
    return true;
}
