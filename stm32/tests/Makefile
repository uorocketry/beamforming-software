CC ?= cc
CFLAGS ?= -std=c2x -Wall -Wextra -Werror -pedantic -O2
CPPFLAGS += -I../app/include -I../../protocol/generated

TARGETS := test_rf_commands test_rf_plan test_diagnostic_record test_can_protocol test_can_rx_queue test_can_tx_queue test_build_info test_protocol_vectors

.PHONY: all test test_invalid_node_config clean

all: $(TARGETS)

test_rf_commands: test_rf_commands.c ../app/src/rf/commands.c ../app/include/rf/commands.h ../app/include/rf/limits.h ../app/include/rf/phase_states_2_4ghz.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_rf_plan: test_rf_plan.c ../app/src/rf/plan.c ../app/src/rf/commands.c ../app/include/rf/plan.h ../app/include/can/protocol.h ../app/include/rf/commands.h ../app/include/rf/limits.h ../app/include/rf/phase_states_2_4ghz.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_diagnostic_record: test_diagnostic_record.c ../app/src/platform/diagnostic_record.c ../app/include/platform/diagnostic_record.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_can_protocol: test_can_protocol.c ../app/src/can/protocol.c ../app/include/can/protocol.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_can_rx_queue: test_can_rx_queue.c ../app/src/can/rx_queue.c ../app/include/can/rx_queue.h ../app/include/can/protocol.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_can_tx_queue: test_can_tx_queue.c ../app/src/can/tx_queue.c ../app/include/can/tx_queue.h ../app/include/can/protocol.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test_build_info: test_build_info.c ../app/src/platform/build_info.c ../app/include/platform/build_info.h ../app/include/platform/firmware_config.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -DFIRMWARE_REVISION=\"test-revision\" -DBEAMFORMER_NODE_ID=7 $(filter %.c,$^) -o $@

test_protocol_vectors: test_protocol_vectors.c ../app/src/can/protocol.c ../app/include/can/protocol.h ../../protocol/generated/protocol_vectors.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(filter %.c,$^) -o $@

test: $(TARGETS) test_invalid_node_config
	./test_rf_commands
	./test_rf_plan
	./test_diagnostic_record
	./test_can_protocol
	./test_can_rx_queue
	./test_can_tx_queue
	./test_build_info
	./test_protocol_vectors

test_invalid_node_config:
	@if printf '#include "platform/firmware_config.h"\n' \
		| $(CC) $(CPPFLAGS) -DBEAMFORMER_NODE_ID=31 -x c -fsyntax-only - >/dev/null 2>&1; then \
		echo "invalid node configuration unexpectedly compiled"; \
		exit 1; \
	else \
		echo "invalid node configuration rejected"; \
	fi

clean:
	rm -f $(TARGETS)
