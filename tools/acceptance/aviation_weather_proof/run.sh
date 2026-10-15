#!/usr/bin/env bash
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
export PYTHONPATH="$root/tools${PYTHONPATH:+:$PYTHONPATH}"
# Stable actor-wide admission survives worktree/planning-workspace deletion.
lock_dir="${XDG_CACHE_HOME:-$HOME/.cache}/starlink-acceptance"
mkdir -p -m 700 "$lock_dir"
export AVIATION_PROOF_OUTER_DEADLINE=$((EPOCHSECONDS + 1200))
# Parent retains the shared scientific lock until all exact owned cleanup ends.
exec timeout --kill-after=10s 20m flock --no-fork "$lock_dir/scientific-decoder.lock" python3 -m acceptance.aviation_weather_proof.runner "$@"
