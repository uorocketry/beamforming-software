#include "can_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static can_frame_t frame_for(
    can_message_type_t type,
    uint8_t destination,
    uint8_t source,
    uint16_t sequence,
    const uint8_t *data,
    uint8_t length)
{
    can_frame_t frame = {0};
    assert(can_protocol_make_id(type, destination, source, sequence, &frame.id));
    frame.extended = true;
    frame.remote = false;
    frame.length = length;
    if (data != NULL && length > 0u) {
        memcpy(frame.data, data, length);
    }
    return frame;
}

static void test_identifier_round_trip(void)
{
    uint32_t id = 0u;
    assert(can_protocol_make_id(
        CAN_MESSAGE_SET_PHASE,
        1u,
        CAN_NODE_CONTROLLER,
        0x1234u,
        &id));
    assert(id == 0x08201234u);

    can_message_type_t type = CAN_MESSAGE_ERROR;
    uint8_t destination = 0u;
    uint8_t source = 0u;
    uint16_t sequence = 0u;
    assert(can_protocol_parse_id(id, &type, &destination, &source, &sequence));
    assert(type == CAN_MESSAGE_SET_PHASE);
    assert(destination == 1u);
    assert(source == CAN_NODE_CONTROLLER);
    assert(sequence == 0x1234u);
}

static void test_identifier_rejects_invalid_fields(void)
{
    uint32_t id = 0u;
    assert(!can_protocol_make_id(
        (can_message_type_t)CAN_MESSAGE_TYPE_COUNT,
        1u,
        0u,
        0u,
        &id));
    assert(!can_protocol_make_id(CAN_MESSAGE_PING, 32u, 0u, 0u, &id));
    assert(!can_protocol_make_id(CAN_MESSAGE_PING, 1u, 32u, 0u, &id));
    assert(!can_protocol_make_id(CAN_MESSAGE_PING, 1u, 0u, 0u, NULL));
}

static void test_safe_command_has_highest_command_arbitration_priority(void)
{
    uint32_t safe_id = 0u;
    uint32_t combined_id = 0u;
    uint32_t phase_id = 0u;
    uint32_t vga_id = 0u;

    assert(can_protocol_make_id(CAN_MESSAGE_ENTER_SAFE, 1u, 0u, 1u, &safe_id));
    assert(can_protocol_make_id(CAN_MESSAGE_SET_COMBINED, 1u, 0u, 1u, &combined_id));
    assert(can_protocol_make_id(CAN_MESSAGE_SET_PHASE, 1u, 0u, 1u, &phase_id));
    assert(can_protocol_make_id(CAN_MESSAGE_SET_VGA, 1u, 0u, 1u, &vga_id));

    assert(safe_id < combined_id);
    assert(combined_id < phase_id);
    assert(phase_id < vga_id);
}

static void test_decode_bulk_commands(void)
{
    can_command_t command = {0};

    const uint8_t phase_payload[] = {146u, 128u, 64u, 0u};
    can_frame_t frame = frame_for(
        CAN_MESSAGE_SET_PHASE,
        1u,
        CAN_NODE_CONTROLLER,
        7u,
        phase_payload,
        sizeof(phase_payload));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(command.type == CAN_MESSAGE_SET_PHASE);
    assert(command.source == CAN_NODE_CONTROLLER);
    assert(command.destination == 1u);
    assert(command.sequence == 7u);
    assert(memcmp(command.phase_states, phase_payload, CAN_RF_CHANNEL_COUNT) == 0);

    const uint8_t vga_payload[] = {0u, 8u, 12u, 23u};
    frame = frame_for(
        CAN_MESSAGE_SET_VGA,
        1u,
        CAN_NODE_CONTROLLER,
        8u,
        vga_payload,
        sizeof(vga_payload));
    memset(&command, 0, sizeof(command));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(memcmp(command.attenuation_db, vga_payload, CAN_RF_CHANNEL_COUNT) == 0);

    const uint8_t combined_payload[] = {
        10u, 20u, 30u, 40u,
        1u, 2u, 3u, 4u,
    };
    frame = frame_for(
        CAN_MESSAGE_SET_COMBINED,
        1u,
        CAN_NODE_CONTROLLER,
        9u,
        combined_payload,
        sizeof(combined_payload));
    memset(&command, 0, sizeof(command));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(memcmp(command.phase_states, combined_payload, CAN_RF_CHANNEL_COUNT) == 0);
    assert(memcmp(
        command.attenuation_db,
        &combined_payload[CAN_RF_CHANNEL_COUNT],
        CAN_RF_CHANNEL_COUNT) == 0);
}

static void test_broadcast_accepts_only_enter_safe(void)
{
    can_command_t command = {0};
    const uint8_t combined_payload[] = {
        10u, 20u, 30u, 40u,
        1u, 2u, 3u, 4u,
    };
    const can_frame_t combined = frame_for(
        CAN_MESSAGE_SET_COMBINED,
        CAN_NODE_BROADCAST,
        CAN_NODE_CONTROLLER,
        8u,
        combined_payload,
        sizeof(combined_payload));
    assert(can_protocol_decode_command(&combined, 5u, &command)
        == CAN_DECODE_BROADCAST_NOT_ALLOWED);

    const uint8_t phase_payload[] = {128u, 64u, 32u, 16u};
    const can_frame_t phase = frame_for(
        CAN_MESSAGE_SET_PHASE,
        CAN_NODE_BROADCAST,
        CAN_NODE_CONTROLLER,
        9u,
        phase_payload,
        sizeof(phase_payload));
    assert(can_protocol_decode_command(&phase, 5u, &command)
        == CAN_DECODE_BROADCAST_NOT_ALLOWED);

    const can_frame_t ping = frame_for(
        CAN_MESSAGE_PING,
        CAN_NODE_BROADCAST,
        CAN_NODE_CONTROLLER,
        10u,
        NULL,
        0u);
    assert(can_protocol_decode_command(&ping, 5u, &command)
        == CAN_DECODE_BROADCAST_NOT_ALLOWED);

    const uint8_t safe_payload[] = {0u};
    const can_frame_t safe = frame_for(
        CAN_MESSAGE_ENTER_SAFE,
        CAN_NODE_BROADCAST,
        CAN_NODE_CONTROLLER,
        11u,
        safe_payload,
        sizeof(safe_payload));
    assert(can_protocol_decode_command(&safe, 5u, &command) == CAN_DECODE_OK);
    assert(command.safe_channel == 0u);
}

static void test_decode_ignores_other_nodes_and_non_commands(void)
{
    can_command_t command = {0};
    can_frame_t frame = frame_for(
        CAN_MESSAGE_PING,
        2u,
        CAN_NODE_CONTROLLER,
        1u,
        NULL,
        0u);
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_IGNORED);

    frame.extended = false;
    frame.id = 0x123u;
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_INVALID_ID);

    frame = frame_for(CAN_MESSAGE_PING, 1u, CAN_NODE_CONTROLLER, 1u, NULL, 0u);
    frame.remote = true;
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_INVALID_ID);

    frame = frame_for(CAN_MESSAGE_STATUS, 1u, CAN_NODE_CONTROLLER, 1u, NULL, 0u);
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_UNSUPPORTED_TYPE);
}

static void test_decode_validates_lengths_and_payloads(void)
{
    can_command_t command = {0};

    const uint8_t short_phase[] = {1u, 2u, 3u};
    can_frame_t frame = frame_for(
        CAN_MESSAGE_SET_PHASE,
        1u,
        CAN_NODE_CONTROLLER,
        1u,
        short_phase,
        sizeof(short_phase));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_INVALID_LENGTH);

    const uint8_t bad_vga[] = {0u, 8u, 24u, 23u};
    frame = frame_for(
        CAN_MESSAGE_SET_VGA,
        1u,
        CAN_NODE_CONTROLLER,
        2u,
        bad_vga,
        sizeof(bad_vga));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_INVALID_PAYLOAD);

    const uint8_t short_combined[] = {1u, 2u, 3u, 4u, 5u, 6u, 7u};
    frame = frame_for(
        CAN_MESSAGE_SET_COMBINED,
        1u,
        CAN_NODE_CONTROLLER,
        3u,
        short_combined,
        sizeof(short_combined));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_INVALID_LENGTH);

    const uint8_t reserved_phase[] = {1u, 2u, 3u, 4u, 0u, 0u, 0u, 1u};
    frame = frame_for(
        CAN_MESSAGE_SET_PHASE,
        1u,
        CAN_NODE_CONTROLLER,
        4u,
        reserved_phase,
        sizeof(reserved_phase));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_RESERVED_BYTES);

    const uint8_t nonzero[] = {1u};
    frame = frame_for(
        CAN_MESSAGE_PING,
        1u,
        CAN_NODE_CONTROLLER,
        5u,
        nonzero,
        sizeof(nonzero));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_RESERVED_BYTES);

    frame = frame_for(CAN_MESSAGE_PING, 1u, 2u, 6u, NULL, 0u);
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_INVALID_ID);
}

static void test_safe_and_ping_commands(void)
{
    can_command_t command = {0};
    const uint8_t safe_payload[] = {3u};
    can_frame_t frame = frame_for(
        CAN_MESSAGE_ENTER_SAFE,
        1u,
        CAN_NODE_CONTROLLER,
        9u,
        safe_payload,
        sizeof(safe_payload));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(command.safe_channel == 3u);

    const uint8_t invalid_safe[] = {4u};
    frame = frame_for(
        CAN_MESSAGE_ENTER_SAFE,
        1u,
        CAN_NODE_CONTROLLER,
        10u,
        invalid_safe,
        sizeof(invalid_safe));
    assert(can_protocol_decode_command(&frame, 1u, &command)
        == CAN_DECODE_INVALID_PAYLOAD);

    frame = frame_for(CAN_MESSAGE_PING, 1u, CAN_NODE_CONTROLLER, 11u, NULL, 0u);
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(command.type == CAN_MESSAGE_PING);
}

static void test_response_builders(void)
{
    can_frame_t response = {0};
    assert(can_protocol_make_ack(1u, 0u, 42u, CAN_MESSAGE_SET_PHASE, &response));
    assert(response.extended);
    assert(!response.remote);
    assert(response.length == 2u);
    assert(response.data[0] == CAN_MESSAGE_SET_PHASE);
    assert(response.data[1] == CAN_COMMAND_RESULT_OK);

    can_message_type_t type = CAN_MESSAGE_SET_PHASE;
    uint8_t destination = 0u;
    uint8_t source = 0u;
    uint16_t sequence = 0u;
    assert(can_protocol_parse_id(response.id, &type, &destination, &source, &sequence));
    assert(type == CAN_MESSAGE_ACK);
    assert(destination == 0u);
    assert(source == 1u);
    assert(sequence == 42u);

    assert(can_protocol_make_error(
        1u,
        0u,
        43u,
        CAN_MESSAGE_SET_VGA,
        CAN_COMMAND_RESULT_INVALID_PAYLOAD,
        &response));
    assert(response.length == 2u);
    assert(response.data[0] == CAN_MESSAGE_SET_VGA);
    assert(response.data[1] == CAN_COMMAND_RESULT_INVALID_PAYLOAD);

    const can_status_payload_t status = {
        .node_id = 1u,
        .phase_state = 146u,
        .phase_address = 1u,
        .attenuation_db = 23u,
        .health_flags = CAN_HEALTH_CLOCK_FALLBACK,
        .rx_dropped = 300u,
        .invalid_commands = 2u,
    };
    assert(can_protocol_make_status(1u, 0u, 44u, &status, &response));
    assert(response.length == 8u);
    assert(response.data[0] == CAN_PROTOCOL_VERSION_MAJOR);
    assert(response.data[1] == 1u);
    assert(response.data[2] == 146u);
    assert(response.data[3] == 1u);
    assert(response.data[4] == 23u);
    assert(response.data[5] == CAN_HEALTH_CLOCK_FALLBACK);
    assert(response.data[6] == 44u);
    assert(response.data[7] == 2u);

    assert(can_protocol_make_protocol_info_status(1u, 0u, 45u, &response));
    assert(response.data[0] == CAN_STATUS_SUBTYPE_PROTOCOL_INFO);
    assert(response.data[1] == CAN_PROTOCOL_VERSION_MAJOR);
    assert(response.data[2] == CAN_PROTOCOL_VERSION_MINOR);
    assert(response.data[3] == CAN_PROTOCOL_VERSION_PATCH);
    assert(response.data[4] == (CAN_PROTOCOL_FEATURE_FLAGS & 0xffu));
    assert(response.data[5] == (CAN_PROTOCOL_FEATURE_FLAGS >> 8u));
}

int main(void)
{
    test_identifier_round_trip();
    test_identifier_rejects_invalid_fields();
    test_safe_command_has_highest_command_arbitration_priority();
    test_decode_bulk_commands();
    test_broadcast_accepts_only_enter_safe();
    test_decode_ignores_other_nodes_and_non_commands();
    test_decode_validates_lengths_and_payloads();
    test_safe_and_ping_commands();
    test_response_builders();
    puts("CAN protocol tests passed");
    return 0;
}
