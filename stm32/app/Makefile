BUILD_DIR := build
PROJECT := beamcontrol
DEVICE := stm32f072r8t6

OPENCM3_DIR ?= ../.deps/libopencm3
OPENCM3_DEFS := -DSTM32F0

CFILES := \
	src/main.c \
	src/can/bus.c \
	src/can/filter.c \
	src/can/protocol.c \
	src/can/runtime.c \
	src/can/rx_queue.c \
	src/can/tx_queue.c \
	src/rf/commands.c \
	src/rf/execute.c \
	src/rf/phase_shifter.c \
	src/rf/plan.c \
	src/rf/vga.c \
	src/platform/build_info.c \
	src/platform/clock.c \
	src/platform/diagnostic_record.c \
	src/platform/retained_diagnostics.c \
	src/platform/faults.c \
	src/platform/spi_guard.c \
	src/platform/timebase.c \
	src/platform/watchdog.c

INCLUDES += -Iinclude
CSTD := -std=c2x
OPT ?= -Os

GIT_REVISION ?= $(shell git rev-parse --verify HEAD 2>/dev/null || printf unknown)
VALID_CAN_NODE_IDS := 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30

NODE_REQUIRED_GOALS := $(filter-out clean,$(MAKECMDGOALS))
ifeq ($(strip $(MAKECMDGOALS)),)
NODE_REQUIRED_GOALS := all
endif

ifneq ($(strip $(NODE_REQUIRED_GOALS)),)
ifndef CAN_NODE_ID
$(error CAN_NODE_ID is required; use the repository target `make firmware NODE=<1..30>`)
endif
ifeq ($(filter $(CAN_NODE_ID),$(VALID_CAN_NODE_IDS)),)
$(error CAN_NODE_ID must be an integer from 1 through 30)
endif
endif

CPPFLAGS += -DFIRMWARE_REVISION=\"$(GIT_REVISION)\"
CPPFLAGS += -DBEAMFORMER_NODE_ID=$(CAN_NODE_ID)
CFLAGS += -Wall -Wextra -Werror -Wdouble-promotion -fstack-usage
LDFLAGS += -Wl,-Map=$(BUILD_DIR)/$(PROJECT).map

include $(OPENCM3_DIR)/mk/genlink-config.mk
include ../rules.mk
include $(OPENCM3_DIR)/mk/genlink-rules.mk

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

all: $(BUILD_DIR) $(PROJECT).elf $(PROJECT).bin
	mv $(PROJECT).elf $(BUILD_DIR)/
	mv $(PROJECT).bin $(BUILD_DIR)/

# Command-line preprocessor values are not part of Make's normal dependency
# graph. Keep a content-addressed stamp so node or revision changes rebuild
# every object instead of silently reusing a differently configured image.
BUILD_CONFIG_STAMP := $(BUILD_DIR)/.firmware-config

.PHONY: FORCE
FORCE:

$(BUILD_CONFIG_STAMP): FORCE | $(BUILD_DIR)
	@expected="node=$(CAN_NODE_ID) revision=$(GIT_REVISION)"; \
	current=$$(cat "$@" 2>/dev/null || true); \
	if [ "$$current" != "$$expected" ]; then \
		printf '%s\n' "$$expected" > "$@"; \
	fi

$(OBJS): $(BUILD_CONFIG_STAMP)
