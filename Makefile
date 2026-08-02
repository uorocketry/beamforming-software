SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PYTHON ?= python3

UV := $(CURDIR)/.tools/bin/uv
ARM_TOOLCHAIN := $(CURDIR)/.tools/arm-gnu-toolchain
OPENCM3_DIR := $(CURDIR)/stm32/.deps/libopencm3

override UV_CACHE_DIR := $(CURDIR)/.tools/uv-cache
override UV_PYTHON_INSTALL_DIR := $(CURDIR)/.tools/uv-python
override UV_PROJECT_ENVIRONMENT := $(CURDIR)/pi/.venv

export PATH := $(ARM_TOOLCHAIN)/bin:$(PATH)
export UV_CACHE_DIR UV_PYTHON_INSTALL_DIR UV_PROJECT_ENVIRONMENT

.PHONY: help doctor quickstart setup setup-safety tools toolchain libopencm3 libopencm3-build
.PHONY: pi-sync pi-test pi-lint pi-format pi-build pi-bundle pi-bundle-smoke
.PHONY: stm32-test firmware firmware-check firmware-size
.PHONY: protocol-check test check clean distclean

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

pi-lint: $(UV)
	$(UV) run --project pi --frozen ruff check pi tools stm32/scripts
	$(UV) run --project pi --frozen ruff format --check pi tools stm32/scripts
	$(UV) run --project pi --frozen mypy pi/src/beamcontrol

pi-format: $(UV)
	$(UV) run --project pi ruff check --fix pi tools stm32/scripts
	$(UV) run --project pi ruff format pi tools stm32/scripts

pi-build: $(UV)
	$(UV) build --project pi --wheel

pi-bundle: $(UV)
	$(PYTHON) tools/build_pi_bundle.py

pi-bundle-smoke: pi-bundle
	@set -euo pipefail; \
	bundles=(build/beamcontrol-pi-*.tar.gz); \
	test "$${#bundles[@]}" -eq 1; \
	python311="$$($(UV) python find 3.11)"; \
	"$$python311" tools/smoke_pi_bundle.py "$${bundles[0]}"

## Firmware targets. NODE is intentionally required to avoid duplicate CAN IDs.
stm32-test:
	$(MAKE) -C stm32/tests clean test

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

## Aggregate targets.
test: pi-test stm32-test protocol-check

check: pi-lint test firmware-check

clean:
	$(MAKE) -C stm32/tests clean
	$(MAKE) -C stm32/app clean
	rm -rf pi/dist build

distclean: clean
	rm -rf .tools stm32/.deps pi/.venv
