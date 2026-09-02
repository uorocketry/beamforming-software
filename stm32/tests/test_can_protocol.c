#include "can/protocol.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static can_frame_t command_frame(can_message_type_t type, const uint8_t *data, uint8_t length)
{
    can_frame_t frame = {.extended = true, .length = length};
    assert(can_protocol_make_id(type, 3u, 0u, 42u, &frame.id));
    if (length != 0u) {
        memcpy(frame.data, data, length);
    }
    return frame;
}

static void test_ids(void)
{
    uint32_t id;
    assert(can_protocol_make_id(CAN_MESSAGE_SET_PHASE, 3u, 0u, 42u, &id));
    assert(id == 0x0860002au);
    can_message_type_t type;
    uint8_t destination;
    uint8_t source;
    uint16_t sequence;
    assert(can_protocol_parse_id(id, &type, &destination, &source, &sequence));
    assert(type == CAN_MESSAGE_SET_PHASE);
    assert(destination == 3u && source == 0u && sequence == 42u);
}

static void test_single_chain_commands(void)
{
    can_command_t command;
    const uint8_t phase[] = {128u};
    can_frame_t frame = command_frame(CAN_MESSAGE_SET_PHASE, phase, sizeof(phase));
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_OK);
    assert(command.phase_state == 128u);

    const uint8_t vga[] = {8u};
    frame = command_frame(CAN_MESSAGE_SET_VGA, vga, sizeof(vga));
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_OK);
    assert(command.attenuation_db == 8u);

    const uint8_t combined[] = {64u, 12u};
    frame = command_frame(CAN_MESSAGE_SET_COMBINED, combined, sizeof(combined));
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_OK);
    assert(command.phase_state == 64u && command.attenuation_db == 12u);

    frame = command_frame(CAN_MESSAGE_ENTER_SAFE, NULL, 0u);
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_OK);
}

static void test_invalid_payloads(void)
{
    can_command_t command;
    const uint8_t too_long[] = {128u, 0u};
    can_frame_t frame = command_frame(CAN_MESSAGE_SET_PHASE, too_long, sizeof(too_long));
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_INVALID_LENGTH);

    const uint8_t bad_attenuation[] = {24u};
    frame = command_frame(CAN_MESSAGE_SET_VGA, bad_attenuation, sizeof(bad_attenuation));
    assert(can_protocol_decode_command(&frame, 3u, &command) == CAN_DECODE_INVALID_PAYLOAD);
}

static void test_status_version(void)
{
    const can_status_payload_t status = {.node_id = 3u, .health_flags = 1u};
    can_frame_t frame;
    assert(can_protocol_make_status(3u, 0u, 42u, &status, &frame));
    assert(frame.length == 8u);
    assert(frame.data[0] == 3u && frame.data[1] == 0u && frame.data[2] == 0u);
    assert(frame.data[3] == 3u);
}

int main(void)
{
    test_ids();
    test_single_chain_commands();
    test_invalid_payloads();
    test_status_version();
    puts("CAN protocol tests passed");
    return 0;
}
