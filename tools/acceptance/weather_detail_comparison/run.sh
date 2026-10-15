#!/usr/bin/env bash
# Saved source replay in the native, exact-candidate production application.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ ${1:-} == --check ]]; then
  python3 -m py_compile tools/acceptance/weather_detail_comparison/*.py
  bash -n "$0"
  bash tools/acceptance/overview-weather/run.sh --check
  exit 0
fi
if [[ $# != 1 || ! $1 =~ ^[a-f0-9]{40}$ ]]; then
  echo 'usage: run.sh --check | exact 40-hex clean HEAD' >&2; exit 2
fi
export WEATHER_ACCEPTANCE_MODE=comparison
export WEATHER_ACCEPTANCE_PROJECT=starlink-288-weather-comparison
export WEATHER_ACCEPTANCE_FRONTEND_PORT=15288
export WEATHER_ACCEPTANCE_BACKEND_PORT=18288
export WEATHER_ACCEPTANCE_CAPTURE_DIR=${WEATHER_ACCEPTANCE_CAPTURE_DIR:?saved capture directory required}
export WEATHER_ACCEPTANCE_OUTPUT_DIR=${WEATHER_ACCEPTANCE_OUTPUT_DIR:-"$root/.superpowers/sdd/issue-288-weather-detail/evidence/$1"}
task_python=${WEATHER_COMPARISON_PYTHON:-python3}
PYTHONPATH="$root/tools" "$task_python" -c 'import sys; from pathlib import Path; from acceptance.weather_detail_comparison.model import load_capture; load_capture(Path(sys.argv[1])/"capture.json")' "$WEATHER_ACCEPTANCE_CAPTURE_DIR"
exec env PYTHONPATH="$root/tools" "$task_python" -m acceptance.weather_detail_comparison.owned --timeout 1700 --evidence "$WEATHER_ACCEPTANCE_OUTPUT_DIR" -- bash "$root/tools/acceptance/overview-weather/run.sh" "$1"
