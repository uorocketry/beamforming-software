#include "can/protocol.h"

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

typedef struct decode_case {
    can_message_type_t type;
    uint8_t destination;
    uint8_t source;
    uint16_t sequence;
    uint8_t data[CAN_MAX_DATA_LENGTH];
    uint8_t length;
    uint8_t self_node;
    can_decode_result_t expected;
} decode_case_t;

static can_decode_result_t decode_case(
    const decode_case_t *test,
    can_command_t *command)
{
    const can_frame_t frame = frame_for(
        test->type,
        test->destination,
        test->source,
        test->sequence,
        test->data,
        test->length);
    return can_protocol_decode_command(&frame, test->self_node, command);
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
    assert(command.bulk_update);
    assert(memcmp(command.phase_states, phase_payload, RF_CHANNEL_COUNT) == 0);

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
    assert(command.bulk_update);
    assert(memcmp(command.attenuation_db, vga_payload, RF_CHANNEL_COUNT) == 0);

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
    assert(command.bulk_update);
    assert(memcmp(command.phase_states, combined_payload, RF_CHANNEL_COUNT) == 0);
    assert(memcmp(
        command.attenuation_db,
        &combined_payload[RF_CHANNEL_COUNT],
        RF_CHANNEL_COUNT) == 0);
}


static void test_decode_individual_commands(void)
{
    can_command_t command = {0};

    const uint8_t phase_payload[] = {146u, 2u};
    can_frame_t frame = frame_for(
        CAN_MESSAGE_SET_PHASE,
        1u,
        CAN_NODE_CONTROLLER,
        10u,
        phase_payload,
        sizeof(phase_payload));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(!command.bulk_update);
    assert(command.channel == 2u);
    assert(command.phase_states[2] == 146u);

    const uint8_t vga_payload[] = {8u, 1u};
    frame = frame_for(
        CAN_MESSAGE_SET_VGA,
        1u,
        CAN_NODE_CONTROLLER,
        11u,
        vga_payload,
        sizeof(vga_payload));
    memset(&command, 0, sizeof(command));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(!command.bulk_update);
    assert(command.channel == 1u);
    assert(command.attenuation_db[1] == 8u);

    const uint8_t combined_payload[] = {64u, 3u, 12u};
    frame = frame_for(
        CAN_MESSAGE_SET_COMBINED,
        1u,
        CAN_NODE_CONTROLLER,
        12u,
        combined_payload,
        sizeof(combined_payload));
    memset(&command, 0, sizeof(command));
    assert(can_protocol_decode_command(&frame, 1u, &command) == CAN_DECODE_OK);
    assert(!command.bulk_update);
    assert(command.channel == 3u);
    assert(command.phase_states[3] == 64u);
    assert(command.attenuation_db[3] == 12u);
}

static void test_broadcast_accepts_only_enter_safe(void)
{
    const decode_case_t cases[] = {
        {CAN_MESSAGE_SET_COMBINED, CAN_NODE_BROADCAST, CAN_NODE_CONTROLLER, 8u,
         {10u, 20u, 30u, 40u, 1u, 2u, 3u, 4u}, 8u, 5u,
         CAN_DECODE_BROADCAST_NOT_ALLOWED},
        {CAN_MESSAGE_SET_PHASE, CAN_NODE_BROADCAST, CAN_NODE_CONTROLLER, 9u,
         {128u, 64u, 32u, 16u}, 4u, 5u, CAN_DECODE_BROADCAST_NOT_ALLOWED},
        {CAN_MESSAGE_PING, CAN_NODE_BROADCAST, CAN_NODE_CONTROLLER, 10u,
         {0u}, 0u, 5u, CAN_DECODE_BROADCAST_NOT_ALLOWED},
        {CAN_MESSAGE_ENTER_SAFE, CAN_NODE_BROADCAST, CAN_NODE_CONTROLLER, 11u,
         {0u}, 1u, 5u, CAN_DECODE_OK},
    };

    can_command_t command = {0};
    for (size_t i = 0u; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        assert(decode_case(&cases[i], &command) == cases[i].expected);
    }
    assert(command.channel == 0u);
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
    const decode_case_t invalid[] = {
        {CAN_MESSAGE_SET_PHASE, 1u, CAN_NODE_CONTROLLER, 1u,
         {1u, 2u, 3u}, 3u, 1u, CAN_DECODE_INVALID_LENGTH},
        {CAN_MESSAGE_SET_VGA, 1u, CAN_NODE_CONTROLLER, 2u,
         {0u, 8u, 24u, 23u}, 4u, 1u, CAN_DECODE_INVALID_PAYLOAD},
        {CAN_MESSAGE_SET_COMBINED, 1u, CAN_NODE_CONTROLLER, 3u,
         {1u, 2u, 3u, 4u, 5u, 6u, 7u}, 7u, 1u, CAN_DECODE_INVALID_LENGTH},
        {CAN_MESSAGE_SET_PHASE, 1u, CAN_NODE_CONTROLLER, 4u,
         {1u, 2u, 3u, 4u, 0u}, 5u, 1u, CAN_DECODE_INVALID_LENGTH},
        {CAN_MESSAGE_PING, 1u, CAN_NODE_CONTROLLER, 5u,
         {1u}, 1u, 1u, CAN_DECODE_INVALID_LENGTH},
        {CAN_MESSAGE_PING, 1u, 2u, 6u,
         {0u}, 0u, 1u, CAN_DECODE_INVALID_ID},
    };

    can_command_t command = {0};
    for (size_t i = 0u; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        assert(decode_case(&invalid[i], &command) == invalid[i].expected);
    }

    /* A two-byte individual frame padded to four bytes is a bulk frame. */
    const decode_case_t bulk = {
        CAN_MESSAGE_SET_PHASE, 1u, CAN_NODE_CONTROLLER, 4u,
        {128u, 2u, 0u, 0u}, 4u, 1u, CAN_DECODE_OK,
    };
    assert(decode_case(&bulk, &command) == CAN_DECODE_OK);
    assert(command.bulk_update);
    assert(command.phase_states[0] == 128u);
    assert(command.phase_states[1] == 2u);
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
    assert(command.channel == 3u);

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
        .health_flags = CAN_HEALTH_CLOCK_FALLBACK,
        .rx_dropped = 3u,
        .tx_dropped = 4u,
        .invalid_commands = 2u,
    };
    assert(can_protocol_make_status(1u, 0u, 44u, &status, &response));
    assert(response.length == 8u);
    assert(response.data[0] == CAN_PROTOCOL_VERSION_MAJOR);
    assert(response.data[1] == CAN_PROTOCOL_VERSION_MINOR);
    assert(response.data[2] == CAN_PROTOCOL_VERSION_PATCH);
    assert(response.data[3] == 1u);
    assert(response.data[4] == CAN_HEALTH_CLOCK_FALLBACK);
    assert(response.data[5] == 3u);
    assert(response.data[6] == 4u);
    assert(response.data[7] == 2u);
}

int main(void)
{
    test_identifier_round_trip();
    test_identifier_rejects_invalid_fields();
    test_safe_command_has_highest_command_arbitration_priority();
    test_decode_bulk_commands();
    test_decode_individual_commands();
    test_broadcast_accepts_only_enter_safe();
    test_decode_ignores_other_nodes_and_non_commands();
    test_decode_validates_lengths_and_payloads();
    test_safe_and_ping_commands();
    test_response_builders();
    puts("CAN protocol tests passed");
    return 0;
}
