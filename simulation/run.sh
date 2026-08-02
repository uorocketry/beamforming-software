#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose -f "$ROOT/simulation/compose.yml")

cleanup() {
    "${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
make -C "$ROOT" firmware NODE=1
set +e
"${COMPOSE[@]}" up --build --abort-on-container-exit --exit-code-from e2e
compose_status=$?
set -e

e2e_id=$("${COMPOSE[@]}" ps --all -q e2e)
e2e_state="missing"
if [ -n "$e2e_id" ]; then
    e2e_state=$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' "$e2e_id")
fi

if [ "$compose_status" -ne 0 ] || [ "$e2e_state" != "exited:0" ]; then
    printf 'simulation failed: compose=%s e2e=%s\n' "$compose_status" "$e2e_state" >&2
    exit 1
fi
