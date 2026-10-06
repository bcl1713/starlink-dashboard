#!/usr/bin/env bash
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
export PYTHONPATH="$root/tools${PYTHONPATH:+:$PYTHONPATH}"
# Parent retains the shared scientific lock until all exact owned cleanup ends.
exec timeout --kill-after=10s 20m flock --no-fork "$root/.superpowers/sdd/2026-10-06-aviation-weather-local-proofs/scientific-decoder.lock" python3 -m acceptance.aviation_weather_proof.runner "$@"
