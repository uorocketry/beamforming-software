#include "can_protocol.h"

#include <stddef.h>
#include <string.h>

_Static_assert(CAN_MESSAGE_TYPE_COUNT == 8,
               "The CAN ID allocates exactly three bits to message type.");

_Static_assert(CAN_RF_CHANNEL_COUNT == 4,
               "BeamControl protocol requires exactly four RF channels.");

static void can_protocol_clear_frame(can_frame_t *frame)
{
    memset(frame, 0, sizeof(*frame));
    frame->extended = true;
    frame->remote = false;
}

static can_decode_result_t can_protocol_decode_enter_safe(
    const can_frame_t *frame,
    can_command_t *command)
{
    if (frame->length != CAN_ENTER_SAFE_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

    command->channel = frame->data[0];
    if (command->channel > CAN_RF_CHANNEL_MAX) {
        return CAN_DECODE_INVALID_PAYLOAD;
    }

    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_combined(
    const can_frame_t *frame,
    can_command_t *command)
{
    if (frame->length == CAN_SET_COMBINED_INDIVIDUAL_LENGTH) {
        command->channel = frame->data[1];
        if (command->channel > CAN_RF_CHANNEL_MAX
            || frame->data[2] > CAN_VGA_ATTENUATION_MAX_DB) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }

        command->phase_states[command->channel] = frame->data[0];
        command->attenuation_db[command->channel] = frame->data[2];
        command->bulk_update = false;
        return CAN_DECODE_OK;
    }

    if (frame->length != CAN_SET_COMBINED_BULK_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

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

    command->bulk_update = true;
    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_phase(
    const can_frame_t *frame,
    can_command_t *command)
{
    if (frame->length == CAN_SET_PHASE_INDIVIDUAL_LENGTH) {
        command->channel = frame->data[1];
        if (command->channel > CAN_RF_CHANNEL_MAX) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }

        command->phase_states[command->channel] = frame->data[0];
        command->bulk_update = false;
        return CAN_DECODE_OK;
    }

    if (frame->length != CAN_SET_PHASE_BULK_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

    memcpy(command->phase_states, frame->data, CAN_RF_CHANNEL_COUNT);
    command->bulk_update = true;
    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_set_vga(
    const can_frame_t *frame,
    can_command_t *command)
{
    if (frame->length == CAN_SET_VGA_INDIVIDUAL_LENGTH) {
        command->channel = frame->data[1];
        if (command->channel > CAN_RF_CHANNEL_MAX
            || frame->data[0] > CAN_VGA_ATTENUATION_MAX_DB) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }

        command->attenuation_db[command->channel] = frame->data[0];
        command->bulk_update = false;
        return CAN_DECODE_OK;
    }

    if (frame->length != CAN_SET_VGA_BULK_LENGTH) {
        return CAN_DECODE_INVALID_LENGTH;
    }

    memcpy(command->attenuation_db, frame->data, CAN_RF_CHANNEL_COUNT);
    for (uint8_t channel = 0u; channel < CAN_RF_CHANNEL_COUNT; ++channel) {
        if (command->attenuation_db[channel] > CAN_VGA_ATTENUATION_MAX_DB) {
            return CAN_DECODE_INVALID_PAYLOAD;
        }
    }

    command->bulk_update = true;
    return CAN_DECODE_OK;
}

static can_decode_result_t can_protocol_decode_ping(
    const can_frame_t *frame)
{
    return frame->length == CAN_PING_LENGTH
        ? CAN_DECODE_OK
        : CAN_DECODE_INVALID_LENGTH;
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
     * not valid commands received by a BeamControl node.
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

    frame->length = CAN_STATUS_LENGTH;
    frame->data[0] = (uint8_t)CAN_PROTOCOL_VERSION_MAJOR;
    frame->data[1] = (uint8_t)CAN_PROTOCOL_VERSION_MINOR;
    frame->data[2] = (uint8_t)CAN_PROTOCOL_VERSION_PATCH;
    frame->data[3] = status->node_id;
    frame->data[4] = status->health_flags;
    frame->data[5] = (uint8_t)(status->rx_dropped & 0xffu);
    frame->data[6] = (uint8_t)(status->tx_dropped & 0xffu);
    frame->data[7] = (uint8_t)(status->invalid_commands & 0xffu);

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

can_command_result_t can_protocol_result_from_decode(
    can_decode_result_t result)
{
    switch (result) {
    case CAN_DECODE_OK:
        return CAN_COMMAND_RESULT_OK;

    case CAN_DECODE_INVALID_LENGTH:
        return CAN_COMMAND_RESULT_INVALID_LENGTH;

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
