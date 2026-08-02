/* Protocol contract test: the C firmware must agree with the shared protocol
 * vectors. Compiles protocol/generated/protocol_vectors.h against can_protocol.c
 * so the generated header is real, compilable C AND matches the firmware.
 *
 * Build:  make -C stm32/tests test
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "can_protocol.h"
#include "protocol_vectors.h"

static void test_id_vectors(void)
{
    for (uint32_t i = 0u; i < PROTOCOL_ID_VECTORS_COUNT; ++i) {
        const protocol_id_vector_t *v = &PROTOCOL_ID_VECTORS[i];
        uint32_t id = 0u;

        assert(can_protocol_make_id(
            (can_message_type_t)v->type,
            v->destination,
            v->source,
            v->sequence,
            &id));
        assert(id == v->extended_id);

        can_message_type_t type = CAN_MESSAGE_ERROR;
        uint8_t destination = 0u;
        uint8_t source = 0u;
        uint16_t sequence = 0u;
        assert(can_protocol_parse_id(
            v->extended_id, &type, &destination, &source, &sequence));
        assert((uint8_t)type == v->type);
        assert(destination == v->destination);
        assert(source == v->source);
        assert(sequence == v->sequence);
    }
    printf("ok %u id vectors\n", PROTOCOL_ID_VECTORS_COUNT);
}

static void test_command_vectors(void)
{
    const uint8_t self = 3u;

    for (uint32_t i = 0u; i < PROTOCOL_COMMAND_VECTORS_COUNT; ++i) {
        const protocol_command_vector_t *v = &PROTOCOL_COMMAND_VECTORS[i];
        can_frame_t frame;
        memset(&frame, 0, sizeof(frame));
        frame.extended = true;
        frame.remote = false;
        frame.length = v->length;
        memcpy(frame.data, v->data, v->length);
        assert(can_protocol_make_id(
            (can_message_type_t)v->type,
            v->destination,
            v->source,
            v->sequence,
            &frame.id));

        can_command_t command;
        memset(&command, 0, sizeof(command));
        const can_decode_result_t decode =
            can_protocol_decode_command(&frame, self, &command);
        const can_command_result_t result = can_protocol_result_from_decode(decode);

        if (v->valid) {
            assert(result == CAN_COMMAND_RESULT_OK);
        } else {
            assert(result == (can_command_result_t)v->result);
        }
    }
    printf("ok %u command vectors\n", PROTOCOL_COMMAND_VECTORS_COUNT);
}

int main(void)
{
    test_id_vectors();
    test_command_vectors();
    puts("CAN protocol contract tests passed");
    return 0;
}
