#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$root"
exec timeout --kill-after=10s 30m uv run --with-requirements backend/starlink-location/requirements.txt python3 tools/acceptance/itinerary-planning/runner.py "$@"
