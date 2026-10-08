#!/usr/bin/env bash
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$task_root"
exec timeout --kill-after=10s 120m python3 tools/acceptance/customer-briefing/production.py "$@"
