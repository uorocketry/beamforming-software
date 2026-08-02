#ifndef CAN_PROTOCOL_H
#define CAN_PROTOCOL_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Protocol versioning
 *
 * CAN_PROTOCOL_VERSION is retained because the legacy STATUS payload places
 * the major protocol version in byte 0.
 */
#define CAN_PROTOCOL_VERSION_MAJOR 1u
#define CAN_PROTOCOL_VERSION_MINOR 1u
#define CAN_PROTOCOL_VERSION_PATCH 0u
#define CAN_PROTOCOL_VERSION CAN_PROTOCOL_VERSION_MAJOR

/*
 * A PING carrying sequence 0xffff requests both:
 *
 *   1. The legacy STATUS frame.
 *   2. A STATUS/PROTOCOL_INFO frame.
 *
 * Other message types retain their normal sequence semantics, including
 * sequence 0xffff, for backward compatibility with protocol 1.0 controllers.
 */
#define CAN_PROTOCOL_DISCOVERY_SEQUENCE 0xffffu

#define CAN_EXTENDED_ID_MAX 0x1fffffffu

#define CAN_NODE_CONTROLLER 0u
#define CAN_NODE_MIN 1u
#define CAN_NODE_MAX 30u
#define CAN_NODE_BROADCAST 31u

#define CAN_MAX_DATA_LENGTH 8u

#define CAN_ID_TYPE_SHIFT 26u
#define CAN_ID_DESTINATION_SHIFT 21u
#define CAN_ID_SOURCE_SHIFT 16u

#define CAN_ID_TYPE_MASK 0x07u
#define CAN_ID_NODE_MASK 0x1fu
#define CAN_ID_SEQUENCE_MASK 0xffffu

/*
 * BeamControl has four physical RF channels.
 *
 * Keep CAN_PHASE_ADDRESS_MAX as a compatibility alias so existing code in
 * can_control.c does not need to change.
 */
#define CAN_RF_CHANNEL_MIN 0u
#define CAN_RF_CHANNEL_MAX 3u
#define CAN_RF_CHANNEL_COUNT 4u
#define CAN_PHASE_ADDRESS_MAX CAN_RF_CHANNEL_MAX

#define CAN_VGA_ATTENUATION_MAX_DB 23u

/*
 * Number of semantically used payload bytes for each command.
 *
 * DLC rules:
 *
 * - DLC must be at least the corresponding USED_LENGTH.
 * - DLC may be larger, up to 8.
 * - Every transmitted byte after USED_LENGTH must be zero.
 *
 * This keeps existing short-DLC protocol 1.0 messages valid while allowing
 * fixed-width, zero-padded frames.
 */
#define CAN_ENTER_SAFE_USED_LENGTH 1u
#define CAN_SET_COMBINED_USED_LENGTH 3u
#define CAN_SET_PHASE_USED_LENGTH 2u
#define CAN_SET_VGA_USED_LENGTH 1u
#define CAN_PING_USED_LENGTH 0u

#define CAN_ACK_LENGTH 2u
#define CAN_ERROR_LENGTH 2u
#define CAN_STATUS_LENGTH 8u

/*
 * Legacy STATUS byte 0 contains CAN_PROTOCOL_VERSION, currently 0x01.
 *
 * Values 0xf0 through 0xff are reserved for explicitly subtyped STATUS
 * messages. Protocol 1.1 defines 0xf0 as PROTOCOL_INFO.
 */
#define CAN_STATUS_SUBTYPE_PROTOCOL_INFO 0xf0u

typedef enum can_protocol_feature {
    /*
     * Commands containing a phase/channel address accept only channels 0-3.
     */
    CAN_PROTOCOL_FEATURE_STRICT_CHANNELS =
        1u << 0,

    /*
     * Broadcast destination 31 accepts ENTER_SAFE only.
     */
    CAN_PROTOCOL_FEATURE_ENTER_SAFE_ONLY_BROADCAST =
        1u << 1,

    /*
     * Payload bytes beyond the command's used length must be zero.
     */
    CAN_PROTOCOL_FEATURE_RESERVED_ZERO_VALIDATION =
        1u << 2,

    /*
     * Successfully completed state-changing commands are replay-cached.
     */
    CAN_PROTOCOL_FEATURE_DUPLICATE_REPLAY =
        1u << 3,

    /*
     * PING sequence 0xffff produces PROTOCOL_INFO.
     */
    CAN_PROTOCOL_FEATURE_PROTOCOL_INFO =
        1u << 4,

    /*
     * Phase-changing operations use the existing safe three-step transition.
     */
    CAN_PROTOCOL_FEATURE_SAFE_TRANSITIONS =
        1u << 5,

    /*
     * Unicast state-changing commands produce ACK or ERROR.
     */
    CAN_PROTOCOL_FEATURE_TERMINAL_RESPONSE =
        1u << 6,

    /*
     * STATUS values 0xf0-0xff are interpreted as explicit subtypes.
     */
    CAN_PROTOCOL_FEATURE_STATUS_SUBTYPES =
        1u << 7
} can_protocol_feature_t;

#define CAN_PROTOCOL_FEATURE_FLAGS                         \
    ((uint16_t)(CAN_PROTOCOL_FEATURE_STRICT_CHANNELS |     \
                CAN_PROTOCOL_FEATURE_ENTER_SAFE_ONLY_BROADCAST | \
                CAN_PROTOCOL_FEATURE_RESERVED_ZERO_VALIDATION |  \
                CAN_PROTOCOL_FEATURE_DUPLICATE_REPLAY |          \
                CAN_PROTOCOL_FEATURE_PROTOCOL_INFO |             \
                CAN_PROTOCOL_FEATURE_SAFE_TRANSITIONS |          \
                CAN_PROTOCOL_FEATURE_TERMINAL_RESPONSE |         \
                CAN_PROTOCOL_FEATURE_STATUS_SUBTYPES))

typedef enum can_message_type {
    CAN_MESSAGE_ENTER_SAFE = 0,
    CAN_MESSAGE_SET_COMBINED = 1,
    CAN_MESSAGE_SET_PHASE = 2,
    CAN_MESSAGE_SET_VGA = 3,
    CAN_MESSAGE_PING = 4,
    CAN_MESSAGE_STATUS = 5,
    CAN_MESSAGE_ACK = 6,
    CAN_MESSAGE_ERROR = 7,
    CAN_MESSAGE_TYPE_COUNT = 8
} can_message_type_t;

typedef enum can_decode_result {
    CAN_DECODE_OK = 0,
    CAN_DECODE_IGNORED = 1,
    CAN_DECODE_INVALID_ARGUMENT = 2,
    CAN_DECODE_INVALID_ID = 3,
    CAN_DECODE_INVALID_LENGTH = 4,
    CAN_DECODE_INVALID_PAYLOAD = 5,
    CAN_DECODE_UNSUPPORTED_TYPE = 6,

    /*
     * Added in protocol 1.1. Append-only: existing numeric values above stay
     * unchanged.
     */
    CAN_DECODE_RESERVED_BYTES = 7,
    CAN_DECODE_BROADCAST_NOT_ALLOWED = 8
} can_decode_result_t;

typedef enum can_command_result {
    CAN_COMMAND_RESULT_OK = 0,
    CAN_COMMAND_RESULT_INVALID_LENGTH = 1,
    CAN_COMMAND_RESULT_INVALID_PAYLOAD = 2,
    CAN_COMMAND_RESULT_UNSUPPORTED = 3,
    CAN_COMMAND_RESULT_HARDWARE = 4,
    CAN_COMMAND_RESULT_BUSY = 5,

    /*
     * Added in protocol 1.1.
     */
    CAN_COMMAND_RESULT_RESERVED_BYTES = 6,
    CAN_COMMAND_RESULT_SEQUENCE_REUSE = 7,
    CAN_COMMAND_RESULT_BROADCAST_NOT_ALLOWED = 8
} can_command_result_t;

typedef enum can_health_flag {
    CAN_HEALTH_NONE = 0,
    CAN_HEALTH_CLOCK_FALLBACK = 1u << 0,
    CAN_HEALTH_RX_DROPPED = 1u << 1,
    CAN_HEALTH_INVALID_COMMAND = 1u << 2,
    CAN_HEALTH_SAFE_LOCKOUT = 1u << 3,
    CAN_HEALTH_BUS_OFF = 1u << 4,
    CAN_HEALTH_TX_DROPPED = 1u << 5
} can_health_flag_t;

typedef struct can_frame {
    uint32_t id;
    bool extended;
    bool remote;
    uint8_t length;
    uint8_t data[CAN_MAX_DATA_LENGTH];
} can_frame_t;

typedef struct can_command {
    can_message_type_t type;
    uint8_t destination;
    uint8_t source;
    uint16_t sequence;

    uint8_t phase_state;
    uint8_t phase_address;
    uint8_t attenuation_db;
} can_command_t;

typedef struct can_status_payload {
    uint8_t node_id;
    uint8_t phase_state;
    uint8_t phase_address;
    uint8_t attenuation_db;
    uint8_t health_flags;
    uint16_t rx_dropped;
    uint16_t invalid_commands;
} can_status_payload_t;

/*
 * STATUS/PROTOCOL_INFO wire payload:
 *
 * Byte 0: 0xf0, CAN_STATUS_SUBTYPE_PROTOCOL_INFO
 * Byte 1: protocol major
 * Byte 2: protocol minor
 * Byte 3: protocol patch
 * Byte 4: feature flags bits 7:0
 * Byte 5: feature flags bits 15:8
 * Byte 6: source/node ID
 * Byte 7: reserved, zero
 */
typedef struct can_protocol_info_payload {
    uint8_t major;
    uint8_t minor;
    uint8_t patch;
    uint16_t feature_flags;
    uint8_t node_id;
} can_protocol_info_payload_t;

bool can_protocol_make_id(
    can_message_type_t type,
    uint8_t destination,
    uint8_t source,
    uint16_t sequence,
    uint32_t *id);

bool can_protocol_parse_id(
    uint32_t id,
    can_message_type_t *type,
    uint8_t *destination,
    uint8_t *source,
    uint16_t *sequence);

can_decode_result_t can_protocol_decode_command(
    const can_frame_t *frame,
    uint8_t self_node,
    can_command_t *command);

bool can_protocol_make_ack(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_message_type_t command_type,
    can_frame_t *frame);

bool can_protocol_make_error(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_message_type_t command_type,
    can_command_result_t result,
    can_frame_t *frame);

bool can_protocol_make_status(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    const can_status_payload_t *status,
    can_frame_t *frame);

bool can_protocol_make_protocol_info_status(
    uint8_t source_node,
    uint8_t destination_node,
    uint16_t sequence,
    can_frame_t *frame);

bool can_protocol_is_state_changing_type(can_message_type_t type);

bool can_protocol_is_discovery_ping(const can_command_t *command);

can_command_result_t can_protocol_result_from_decode(
    can_decode_result_t result);

#endif
