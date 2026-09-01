SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PYTHON ?= python3

UV := $(CURDIR)/.tools/bin/uv
ARM_TOOLCHAIN := $(CURDIR)/.tools/arm-gnu-toolchain
OPENCM3_DIR := $(CURDIR)/stm32/.deps/libopencm3
STM32_SANITIZER_FLAGS := \
	-std=c2x -Wall -Wextra -Werror -pedantic -O1 -g \
	-fsanitize=address,undefined -fno-omit-frame-pointer

override UV_CACHE_DIR := $(CURDIR)/.tools/uv-cache
override UV_PYTHON_INSTALL_DIR := $(CURDIR)/.tools/uv-python
override UV_PROJECT_ENVIRONMENT := $(CURDIR)/pi/.venv

export PATH := $(ARM_TOOLCHAIN)/bin:$(PATH)
export UV_CACHE_DIR UV_PYTHON_INSTALL_DIR UV_PROJECT_ENVIRONMENT

.PHONY: help doctor quickstart setup setup-safety tools toolchain libopencm3 libopencm3-build
.PHONY: pi-sync pi-test pi-lint pi-format pi-build pi-bundle pi-bundle-smoke pi-command-smoke
.PHONY: stm32-test stm32-sanitize stm32-static stm32-verify firmware firmware-check firmware-size
.PHONY: protocol-check simulation-test simulation-up simulation-down test check clean distclean

help:
	@printf '%s\n' \
		'BeamControl build and development commands' \
		'' \
		'Setup:' \
		'  make setup              Fetch pinned tools and synchronize dependencies' \
		'  make doctor             Diagnose required and optional environment capabilities' \
		'  make quickstart         Run setup, doctor, and the host test suite' \
		'' \
		'Verification:' \
		'  make test               Run Python, native firmware, and protocol tests' \
		'  make check              Run lint, tests, and one representative firmware build' \
		'  make pi-lint            Run Ruff, formatting, and mypy checks' \
		'  make simulation-test    Run Docker + Renode end-to-end simulation' \
		'  make stm32-sanitize     Run native STM32 tests with ASan/UBSan' \
		'  make stm32-static       Run cppcheck on production firmware' \
		'  make stm32-verify       Run sanitizer, cppcheck, and firmware build' \
		'' \
		'Firmware:' \
		'  make firmware NODE=1    Build one receiver-board image with CAN node ID 1' \
		'  make firmware-size NODE=1  Show linked firmware size' \
		'' \
		'Pi:' \
		'  make pi-build           Build the beamcontrol Python wheel' \
		'  make pi-bundle          Build the offline Pi bundle (aarch64 only)' \
		'  make pi-bundle-smoke    Build and offline-install smoke-test the Pi bundle' \
		'' \
		'Cleanup:' \
		'  make clean              Remove generated build artifacts' \
		'  make distclean          Remove all repo-local tools, dependencies, and environments'

doctor:
	$(PYTHON) tools/doctor.py

quickstart:
	$(MAKE) setup
	$(MAKE) doctor
	$(MAKE) test

setup-safety:
	@$(PYTHON) tools/check_dev_setup.py

## One-shot: fetch all tools + deps and sync the Python environment.
setup: setup-safety tools libopencm3 pi-sync

## Fetch pinned uv + ARM toolchain into .tools/ (gitignored).
tools: $(UV) toolchain

$(UV):
	$(PYTHON) tools/bootstrap_dev.py

toolchain:
	$(PYTHON) tools/fetch_arm_toolchain.py

## Fetch pinned libopencm3 source into stm32/.deps/ (gitignored, SHA256-verified).
libopencm3:
	$(PYTHON) tools/fetch_libopencm3.py

libopencm3-build: libopencm3 toolchain
	$(MAKE) -C $(OPENCM3_DIR) TARGETS=stm32/f0

## Pi (Python) targets.
pi-sync: $(UV)
	$(UV) sync --project pi --frozen

pi-test: $(UV)
	$(UV) run --project pi --frozen pytest pi/tests tools/tests

pi-command-smoke: $(UV)
	$(UV) run --project pi --frozen python tools/smoke_beamctl_commands.py

pi-lint: $(UV)
	$(UV) run --project pi --frozen ruff check pi tools simulation/tests
	$(UV) run --project pi --frozen ruff format --check pi tools simulation/tests
	$(UV) run --project pi --frozen mypy pi/src/beamcontrol

pi-format: $(UV)
	$(UV) run --project pi ruff check --fix pi tools simulation/tests
	$(UV) run --project pi ruff format pi tools simulation/tests

pi-build: $(UV)
	$(UV) build --project pi --wheel

pi-bundle: $(UV)
	$(PYTHON) tools/build_pi_bundle.py

pi-bundle-smoke: pi-bundle
	@set -euo pipefail; \
	revision="$$(git rev-parse --short HEAD)"; \
	bundle="build/beamcontrol-pi-$${revision}.tar.gz"; \
	test -f "$$bundle"; \
	$(PYTHON) tools/smoke_pi_bundle.py "$$bundle"

## Firmware targets. NODE is intentionally required to avoid duplicate CAN IDs.
stm32-test:
	$(MAKE) -C stm32/tests clean test

stm32-sanitize:
	@set -euo pipefail; \
	trap '$(MAKE) -C stm32/tests clean >/dev/null' EXIT; \
	$(MAKE) -C stm32/tests clean test CFLAGS='$(STM32_SANITIZER_FLAGS)'

stm32-static:
	@command -v cppcheck >/dev/null 2>&1 || { \
		echo 'error: cppcheck is required; install it or run `make doctor`' >&2; \
		exit 2; \
	}
	cppcheck \
		--enable=warning,style,performance,portability \
		--error-exitcode=1 \
		--std=c23 \
		--suppress=missingIncludeSystem \
		--suppress=unusedFunction \
		-DSTM32F0 \
		-DSTM32F072R8T6 \
		-DBEAMFORMER_NODE_ID=1 \
		-Istm32/app/include \
		stm32/app/src

stm32-verify: stm32-sanitize stm32-static firmware-check

firmware:
	@if [[ -z "$(NODE)" ]]; then \
		echo 'error: NODE is required; use `make firmware NODE=<1..30>`' >&2; \
		exit 2; \
	fi
	@if ! [[ "$(NODE)" =~ ^([1-9]|[12][0-9]|30)$$ ]]; then \
		echo 'error: NODE must be an integer from 1 through 30' >&2; \
		exit 2; \
	fi
	$(MAKE) toolchain libopencm3-build
	$(MAKE) -C stm32/app \
		OPENCM3_DIR=$(OPENCM3_DIR) \
		CAN_NODE_ID=$(NODE)

firmware-check:
	$(MAKE) firmware NODE=1

firmware-size: firmware
	arm-none-eabi-size stm32/app/build/beamcontrol.elf

## Protocol contract (Python <-> C drift check).
protocol-check: $(UV)
	$(UV) run --project pi \
		python tools/generate-protocol-vectors.py --check
	$(UV) run --project pi --frozen pytest pi/tests/contract

## Docker + Renode functional simulation.
simulation-test:
	./simulation/run.sh

simulation-up:
	$(MAKE) firmware NODE=1
	docker compose -f simulation/compose.yml up --build

simulation-down:
	docker compose -f simulation/compose.yml down --volumes --remove-orphans

## Aggregate targets.
test: pi-test stm32-test protocol-check

check: pi-lint test firmware-check

clean:
	$(MAKE) -C stm32/tests clean
	$(MAKE) -C stm32/app clean
	rm -rf pi/dist build

distclean: clean
	rm -rf .tools stm32/.deps pi/.venv
