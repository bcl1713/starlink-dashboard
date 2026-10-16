#!/usr/bin/env bash
# Keep the actor's Docker endpoint, proxy, and CA configuration intact.
set -euo pipefail
exec python3 "$(dirname "$0")/runner.py" "$@"
