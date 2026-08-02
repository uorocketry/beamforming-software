#!/bin/sh
set -eu

if ! ip link show dev vcan0 >/dev/null 2>&1; then
    ip link add dev vcan0 type vcan
fi
ip link set dev vcan0 up
exec sleep infinity
