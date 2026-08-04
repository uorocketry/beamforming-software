#include "can_protocol.h"

#include <stddef.h>
#include <string.h>

_Static_assert(CAN_MESSAGE_TYPE_COUNT == 8,
               "The CAN ID allocates exactly three bits to message type.");

_Static_assert(CAN_RF_CHANNEL_COUNT == 4,
               "BeamControl protocol requires exactly four RF channels.");

_Static_assert(CAN_PROTOCOL_FEATURE_FLAGS <= UINT16_MAX,
               "Protocol feature flags must fit in 16 bits.");

static void can_protocol_clear_frame(can_frame_t *frame)
{
    memset(frame, 0, sizeof(*frame));
    frame->extended = true;
    frame->remote = false;
}

static can_decode_result_t can_protocol_validate_used_length(
    const can_frame_t *frame,
    uint8_t used_length)
{
    uint8_t index;

    if (frame->length < used_length || frame->length > CAN_MAX_DATA_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

    /*
     * Bytes after the command's semantic payload are reserved. They must be
     * zero when present.
     */
    for (index = used_length; index < frame->length; ++index) {
        if (frame->data[index] != 0u) {
            return CAN_DECODE_RESERVED_BYTES;
        }
    }

    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_enter_safe(
    const can_frame_t *frame,
    can_command_t *command)
{
    const can_decode_result_t result =
        can_protocol_validate_used_length(
            frame,
            CAN_ENTER_SAFE_USED_LENGTH);

    if (result != CAN_DECODE_OK) {
        return result;
    }

    command->safe_channel = frame->data[0];
    if (command->safe_channel > CAN_RF_CHANNEL_MAX) {
        return CAN_DECODE_INVALID_PAYLOAD;
    }

    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_combined(
    const can_frame_t *frame,
    can_command_t *command)
{
    const can_decode_result_t result =
        can_protocol_validate_used_length(
            frame,
            CAN_SET_COMBINED_USED_LENGTH);

    if (result != CAN_DECODE_OK) {
        return result;
    }

    /* Bytes 0..3 are phase indexes; bytes 4..7 are VGA attenuations. */
    memcpy(command->phase_states, frame->data, CAN_RF_CHANNEL_COUNT);
    memcpy(
        command->attenuation_db,
        &frame->data[CAN_RF_CHANNEL_COUNT],
        CAN_RF_CHANNEL_COUNT);

    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        if (command->attenuation_db[channel] > CAN_VGA_ATTENUATION_MAX_DB) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }
    }

    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_phase(
    const can_frame_t *frame,
    can_command_t *command)
{
    const can_decode_result_t result =
        can_protocol_validate_used_length(
            frame,
            CAN_SET_PHASE_USED_LENGTH);

    if (result != CAN_DECODE_OK) {
        return result;
    }

    /* The four bytes are phase-enum indexes for channels 1 through 4. */
    memcpy(command->phase_states, frame->data, CAN_RF_CHANNEL_COUNT);
    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_vga(
    const can_frame_t *frame,
    can_command_t *command)
{
    const can_decode_result_t result =
        can_protocol_validate_used_length(
            frame,
            CAN_SET_VGA_USED_LENGTH);

    if (result != CAN_DECODE_OK) {
        return result;
    }

    /* The four bytes are integer-dB attenuation values for VGA channels 1..4. */
    memcpy(command->attenuation_db, frame->data, CAN_RF_CHANNEL_COUNT);
    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        if (command->attenuation_db[channel] > CAN_VGA_ATTENUATION_MAX_DB) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }
    }

    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_ping(
    const can_frame_t *frame)
{
    /*
     * A normal legacy PING uses DLC 0.
     *
     * Zero-padded PING frames with DLC 1-8 are also valid, but every byte must
     * be zero.
     */
    return can_protocol_validate_used_length(
        frame,
        CAN_PING_USED_LENGTH);
}

bool can_protocol_make_id(
    can_message_type_t type,
    uint8_t destination,
    uint8_t source,
    uint16_t sequence,
    uint32_t *id)
{
    uint32_t value;

    if (id == NULL) {
        return false;
    }

    if ((uint32_t)type >= (uint32_t)CAN_MESSAGE_TYPE_COUNT) {
        return false;
    }

    if (destination > CAN_NODE_BROADCAST || source > CAN_NODE_BROADCAST) {
        return false;
    }

    value =
        ((uint32_t)type << CAN_ID_TYPE_SHIFT) |
        ((uint32_t)destination << CAN_ID_DESTINATION_SHIFT) |
        ((uint32_t)source << CAN_ID_SOURCE_SHIFT) |
        (uint32_t)sequence;

    if (value > CAN_EXTENDED_ID_MAX) {
        return false;
    }

    *id = value;
    return true;
}

bool can_protocol_parse_id(
    uint32_t id,
    can_message_type_t *type,
    uint8_t *destination,
    uint8_t *source,
    uint16_t *sequence)
{
    uint32_t raw_type;

    if ((type == NULL) ||
        (destination == NULL) ||
        (source == NULL) ||
        (sequence == NULL)) {
        return false;
    }

    if (id > CAN_EXTENDED_ID_MAX) {
        return false;
    }

    raw_type =
        (id >> CAN_ID_TYPE_SHIFT) &
        (uint32_t)CAN_ID_TYPE_MASK;

    if (raw_type >= (uint32_t)CAN_MESSAGE_TYPE_COUNT) {
        return false;
    }

    *type = (can_message_type_t)raw_type;

    *destination =
        (uint8_t)((id >> CAN_ID_DESTINATION_SHIFT) &
                  (uint32_t)CAN_ID_NODE_MASK);

    *source =
        (uint8_t)((id >> CAN_ID_SOURCE_SHIFT) &
                  (uint32_t)CAN_ID_NODE_MASK);

    *sequence =
        (uint16_t)(id & (uint32_t)CAN_ID_SEQUENCE_MASK);

    return true;
}

can_decode_result_t can_protocol_decode_command(
    const can_frame_t *frame,
    uint8_t self_node,
    can_command_t *command)
{
    can_message_type_t type;
    uint8_t destination;
    uint8_t source;
    uint16_t sequence;

    if ((frame == NULL) || (command == NULL)) {
        return CAN_DECODE_INVALID_ARGUMENT;
    }

    if ((self_node < CAN_NODE_MIN) ||
        (self_node > CAN_NODE_MAX)) {
        return CAN_DECODE_INVALID_ARGUMENT;
    }

    if (!frame->extended || frame->remote) {
        return CAN_DECODE_INVALID_ID;
    }

    if (frame->length > CAN_MAX_DATA_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

    if (!can_protocol_parse_id(
            frame->id,
            &type,
            &destination,
            &source,
            &sequence)) {
        return CAN_DECODE_INVALID_ID;
    }

    if ((destination != self_node) &&
        (destination != CAN_NODE_BROADCAST)) {
        return CAN_DECODE_IGNORED;
    }

    if (source != CAN_NODE_CONTROLLER) {
        return CAN_DECODE_INVALID_ID;
    }

    /*
     * STATUS, ACK and ERROR are receiver-to-controller message types and are
     * not valid commands received by an BeamControl node.
     */
    if (type > CAN_MESSAGE_PING) {
        return CAN_DECODE_UNSUPPORTED_TYPE;
    }

    /*
     * Only ENTER_SAFE is permitted at the broadcast destination.
     *
     * No response will be emitted for this result because the runtime's error
     * helpers already suppress responses to broadcast destinations.
     */
    if ((destination == CAN_NODE_BROADCAST) &&
        (type != CAN_MESSAGE_ENTER_SAFE)) {
        return CAN_DECODE_BROADCAST_NOT_ALLOWED;
    }

    memset(command, 0, sizeof(*command));

    command->type = type;
    command->destination = destination;
    command->source = source;
    command->sequence = sequence;

    switch (type) {
    case CAN_MESSAGE_ENTER_SAFE:
        return can_protocol_decode_enter_safe(frame, command);

    case CAN_MESSAGE_SET_COMBINED:
        return can_protocol_decode_set_combined(frame, command);

    case CAN_MESSAGE_SET_PHASE:
        return can_protocol_decode_set_phase(frame, command);

    case CAN_MESSAGE_SET_VGA:
        return can_protocol_decode_set_vga(frame, command);

    case CAN_MESSAGE_PING:
        return can_protocol_decode_ping(frame);

    case CAN_MESSAGE_STATUS:
    case CAN_MESSAGE_ACK:
    case CAN_MESSAGE_ERROR:
    case CAN_MESSAGE_TYPE_COUNT:
    default:
        return CAN_DECODE_UNSUPPORTED_TYPE;
    }
}

bool can_protocol_make_ack(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_message_type_t command_type,
    can_frame_t *frame)
{
    if (frame == NULL) {
        return false;
    }

    if ((uint32_t)command_type >=
        (uint32_t)CAN_MESSAGE_TYPE_COUNT) {
        return false;
    }

    can_protocol_clear_frame(frame);

    if (!can_protocol_make_id(
            CAN_MESSAGE_ACK,
            destination_node,
            source_node,
            sequence,
            &frame->id)) {
        return false;
    }

    frame->length = CAN_ACK_LENGTH;
    frame->data[0] = (uint8_t)command_type;
    frame->data[1] = (uint8_t)CAN_COMMAND_RESULT_OK;

    return true;
}

bool can_protocol_make_error(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_message_type_t command_type,
    can_command_result_t result,
    can_frame_t *frame)
{
    if (frame == NULL) {
        return false;
    }

    if ((uint32_t)command_type >=
        (uint32_t)CAN_MESSAGE_TYPE_COUNT) {
        return false;
    }

    can_protocol_clear_frame(frame);

    if (!can_protocol_make_id(
            CAN_MESSAGE_ERROR,
            destination_node,
            source_node,
            sequence,
            &frame->id)) {
        return false;
    }

    frame->length = CAN_ERROR_LENGTH;
    frame->data[0] = (uint8_t)command_type;
    frame->data[1] = (uint8_t)result;

    return true;
}

bool can_protocol_make_status(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    const can_status_payload_t *status,
    can_frame_t *frame)
{
    if ((status == NULL) || (frame == NULL)) {
        return false;
    }

    can_protocol_clear_frame(frame);

    if (!can_protocol_make_id(
            CAN_MESSAGE_STATUS,
            destination_node,
            source_node,
            sequence,
            &frame->id)) {
        return false;
    }

    /*
     * Preserve the protocol 1.0 legacy STATUS layout exactly.
     */
    frame->length = CAN_STATUS_LENGTH;
    frame->data[0] = (uint8_t)CAN_PROTOCOL_VERSION;
    frame->data[1] = status->node_id;
    frame->data[2] = status->phase_state;
    frame->data[3] = status->phase_address;
    frame->data[4] = status->attenuation_db;
    frame->data[5] = status->health_flags;
    frame->data[6] = (uint8_t)(status->rx_dropped & 0xffu);
    frame->data[7] = (uint8_t)(status->invalid_commands & 0xffu);

    return true;
}

bool can_protocol_make_protocol_info_status(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_frame_t *frame)
{
    uint16_t feature_flags = CAN_PROTOCOL_FEATURE_FLAGS;

    if (frame == NULL) {
        return false;
    }

    can_protocol_clear_frame(frame);

    if (!can_protocol_make_id(
            CAN_MESSAGE_STATUS,
            destination_node,
            source_node,
            sequence,
            &frame->id)) {
        return false;
    }

    frame->length = CAN_STATUS_LENGTH;

    frame->data[0] = CAN_STATUS_SUBTYPE_PROTOCOL_INFO;
    frame->data[1] = (uint8_t)CAN_PROTOCOL_VERSION_MAJOR;
    frame->data[2] = (uint8_t)CAN_PROTOCOL_VERSION_MINOR;
    frame->data[3] = (uint8_t)CAN_PROTOCOL_VERSION_PATCH;
    frame->data[4] = (uint8_t)(feature_flags & 0xffu);
    frame->data[5] = (uint8_t)((feature_flags >> 8) & 0xffu);
    frame->data[6] = source_node;
    frame->data[7] = 0u;

    return true;
}

bool can_protocol_is_state_changing_type(can_message_type_t type)
{
    switch (type) {
    case CAN_MESSAGE_ENTER_SAFE:
    case CAN_MESSAGE_SET_COMBINED:
    case CAN_MESSAGE_SET_PHASE:
    case CAN_MESSAGE_SET_VGA:
        return true;

    case CAN_MESSAGE_PING:
    case CAN_MESSAGE_STATUS:
    case CAN_MESSAGE_ACK:
    case CAN_MESSAGE_ERROR:
    case CAN_MESSAGE_TYPE_COUNT:
    default:
        return false;
    }
}

bool can_protocol_is_discovery_ping(const can_command_t *command)
{
    if (command == NULL) {
        return false;
    }

    return
        (command->type == CAN_MESSAGE_PING) &&
        (command->sequence == CAN_PROTOCOL_DISCOVERY_SEQUENCE) &&
        (command->destination != CAN_NODE_BROADCAST);
}

can_command_result_t can_protocol_result_from_decode(
    can_decode_result_t result)
{
    switch (result) {
    case CAN_DECODE_OK:
        return CAN_COMMAND_RESULT_OK;

    case CAN_DECODE_INVALID_LENGTH:
        return CAN_COMMAND_RESULT_INVALID_LENGTH;

    case CAN_DECODE_RESERVED_BYTES:
        return CAN_COMMAND_RESULT_RESERVED_BYTES;

    case CAN_DECODE_BROADCAST_NOT_ALLOWED:
        return CAN_COMMAND_RESULT_BROADCAST_NOT_ALLOWED;

    case CAN_DECODE_UNSUPPORTED_TYPE:
        return CAN_COMMAND_RESULT_UNSUPPORTED;

    case CAN_DECODE_IGNORED:
    case CAN_DECODE_INVALID_ARGUMENT:
    case CAN_DECODE_INVALID_ID:
    case CAN_DECODE_INVALID_PAYLOAD:
    default:
        return CAN_COMMAND_RESULT_INVALID_PAYLOAD;
    }
}
