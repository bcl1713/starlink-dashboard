#!/usr/bin/env bash
# Task-owned real Prometheus and production Nginx controls, exact tracked inputs.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
phase=incremental cadence=5 smoke=0 check=0 replay=0
duration=600 warmup=300 viewers=1 window=1800
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) check=1; shift ;;
    --smoke) smoke=1; shift ;;
    --replay) replay=1; shift ;;
    --phase) phase=$2; shift 2 ;;
    --cadence) cadence=$2; shift 2 ;;
    --duration) duration=$2; shift 2 ;;
    --warmup) warmup=$2; shift 2 ;;
    --viewers) viewers=$2; shift 2 ;;
    --window) window=$2; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [[ "$phase" != full && "$phase" != incremental ]] || [[ "$cadence" != 1 && "$cadence" != 5 ]]; then
  echo 'phase must be full/incremental and cadence 1/5' >&2; exit 2
fi
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Acceptance requires a clean tracked worktree; commit the candidate first.' >&2
  exit 2
fi
python3 - <<'PY'
import socket
import sys
for port in (18224, 15224, 19224):
    with socket.socket() as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError as error:
            sys.exit(f'Acceptance port 127.0.0.1:{port} occupied: {error}')
PY
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-224-history) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-224-history) ]]; then
  echo 'Existing starlink-224-history resources found; inspect ownership before cleanup.' >&2
  exit 2
fi
if [[ $check == 1 ]]; then exit 0; fi
export ACCEPTANCE_CANDIDATE_SHA OVERVIEW_PROFILE_SOURCE OVERVIEW_PROFILE_MODE OVERVIEW_PROFILE_CADENCE OVERVIEW_PROFILE_SEED
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD)
OVERVIEW_PROFILE_MODE=$phase
OVERVIEW_PROFILE_CADENCE=$cadence
output=${OVERVIEW_PROFILE_OUTPUT:-"$root/.superpowers/sdd/2026-10-04-overview-history-efficiency-follow-up/evidence/$ACCEPTANCE_CANDIDATE_SHA/$phase-$cadence-$viewers"}
if [[ -d "$output" && -n $(find "$output" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
  echo "Refusing nonempty evidence directory: $output" >&2; exit 2
fi
mkdir -p "$output"
output=$(cd "$output" && pwd -P)
OVERVIEW_PROFILE_SOURCE=$(mktemp -d /tmp/starlink-224-source.XXXXXX)
OVERVIEW_PROFILE_SEED="$OVERVIEW_PROFILE_SOURCE/history.openmetrics"
compose=(docker compose -p starlink-224-history -f "$root/tools/acceptance/overview-history/compose.yml")
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$output/containers.log" 2>&1 || true
    backend=$("${compose[@]}" ps -q starlink-location)
    if [[ -n "$backend" ]]; then
      docker cp "$backend:/data/overview-history-queries.jsonl" "$output/backend-queries.jsonl" 2>/dev/null || true
      docker cp "$backend:/data/overview-history-reads.jsonl" "$output/backend-reads.jsonl" 2>/dev/null || true
    fi
    "${compose[@]}" down --volumes > "$output/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-224-history) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-224-history) ]]; then result=1; fi
    python3 - <<'PY' >> "$output/cleanup.log" 2>&1 || result=1
import socket
for port in (18224,15224,19224):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
print('Owned project containers/volumes/listeners absent.')
PY
  fi
  python3 - "$output" "$result" <<'PYUPDATE'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
path = root / 'browser/metadata.json'
if path.exists():
    data = json.loads(path.read_text())
    browser = root / 'browser/browser-cleanup.json'
    data['cleanup'] = 'passed' if sys.argv[2] == '0' and browser.exists() and json.loads(browser.read_text()).get('status') == 'passed' else 'failed'
    path.write_text(json.dumps(data, indent=2))
PYUPDATE
  rm -rf -- "$OVERVIEW_PROFILE_SOURCE"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$OVERVIEW_PROFILE_SOURCE"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$output/candidate-sha.txt"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$output/docker-runtime.txt"
docker context show >> "$output/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$output/docker-runtime.txt"
"${compose[@]}" config --quiet
"${compose[@]}" config > "$output/compose.yml"
"${compose[@]}" build > "$output/build.log" 2>&1
profile_python=${OVERVIEW_PROFILE_PYTHON:-python3}
seed_end=$(($(date +%s) - 20))
"$profile_python" "$OVERVIEW_PROFILE_SOURCE/tools/acceptance/overview_history/seed.py" --output "$OVERVIEW_PROFILE_SEED" --end "$seed_end"
# The bind source must be readable by Prometheus's nobody user.
chmod 755 "$OVERVIEW_PROFILE_SOURCE"
chmod 644 "$OVERVIEW_PROFILE_SEED"
started=1
"${compose[@]}" run --rm --no-deps --entrypoint /bin/promtool prometheus tsdb create-blocks-from openmetrics /seed/history.openmetrics /prometheus > "$output/seed.log" 2>&1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 > "$output/start.log" 2>&1
docker image inspect "starlink-224-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-224-frontend-$cadence:$ACCEPTANCE_CANDIDATE_SHA" prom/prometheus:v3.5.0 --format '{{.RepoTags}} {{.Id}}' > "$output/images.txt"
curl --fail --silent http://127.0.0.1:15224/overview > /dev/null
curl --fail --silent http://127.0.0.1:15224/api/status > "$output/status.json"
curl --fail --silent -X PUT -H 'Content-Type: application/json' -d "{\"window_seconds\":$window}" http://127.0.0.1:15224/api/overview-history/settings > "$output/settings.json"
curl --fail --silent http://127.0.0.1:15224/api/overview-history > "$output/cold-history.json"
"$profile_python" "$OVERVIEW_PROFILE_SOURCE/tools/acceptance/overview_history/seed.py" --validate-history "$output/cold-history.json" --window "$window"
curl --fail --silent http://127.0.0.1:15224/api/_acceptance/history-profile > "$output/cold-counters.json"
printf '%s\n' "$seed_end" > "$output/seed-end.txt"
if [[ $replay == 1 ]]; then
  mkdir -p "$output/replay"
  for replay_window in 300 900 1800 3600 3601; do
    for configuration in full-5 incremental-5 incremental-1; do
      mode=${configuration%-*}
      interval=${configuration##*-}
      "$profile_python" "$root/tools/profile_overview_history.py" \
        --prometheus-url http://127.0.0.1:19224 --end "$((seed_end - 150))" \
        --window "$replay_window" --cadence "$interval" --mode "$mode" \
        --samples 30 --output "$output/replay/$replay_window-$configuration.json"
    done
  done
fi
if [[ $smoke == 1 ]]; then exit 0; fi
"$profile_python" "$root/tools/acceptance/overview_history/run_browser.py" \
  --origin http://127.0.0.1:15224 --artifacts "$output/browser" \
  --cadence "$cadence" --viewers "$viewers" --window "$window" \
  --warmup-seconds "$warmup" --duration-seconds "$duration"
