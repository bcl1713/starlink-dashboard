#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
export PYTHONPATH="$repo_root/tools${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m acceptance.platform.runner "$@"
