#!/usr/bin/env bash
set -euo pipefail

rm -f /results/renode.log
renode --disable-gui --console -p /simulation/renode/node.resc 2>&1 \
    | tee /results/renode.log
