#!/usr/bin/env bash
set -euo pipefail
exec timeout --kill-after=10s 45m python3 "$(dirname "$0")/generate.py" "$@"
