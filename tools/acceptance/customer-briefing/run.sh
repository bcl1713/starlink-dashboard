#!/usr/bin/env bash
set -euo pipefail
runner_dir=$(cd "$(dirname "$0")" && pwd)
exec timeout --kill-after=10s 45m uv run --python 3.11 \
  --with-requirements "$runner_dir/../../../backend/starlink-location/requirements.txt" \
  python "$runner_dir/generate.py" "$@"
