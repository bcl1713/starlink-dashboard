#!/usr/bin/env bash
# Exact committed production candidate; fixture-only source transport, native browser.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ $# != 2 || ! $1 =~ ^[a-f0-9]{40}$ || ! -x $2 ]]; then
  echo 'usage: run.sh exact-SHA provisioned-browser-executable' >&2; exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA=$1
export AVIATION_ACCEPTANCE_BROWSER=$2
if [[ $1 != $(git rev-parse HEAD) || -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Acceptance requires clean committed HEAD' >&2; exit 2
fi
export WEATHER_ACCEPTANCE_PROJECT=starlink-290-catalog
export WEATHER_ACCEPTANCE_FRONTEND_PORT=15291
export WEATHER_ACCEPTANCE_BACKEND_PORT=18291
export WEATHER_ACCEPTANCE_MODE=aviation
export WEATHER_ACCEPTANCE_SOURCE_ROOT
WEATHER_ACCEPTANCE_SOURCE_ROOT=$(mktemp -d /tmp/starlink-290-catalog-source.XXXXXX)
export WEATHER_ACCEPTANCE_OUTPUT_DIR=${WEATHER_ACCEPTANCE_OUTPUT_DIR:-$root/test-results/aviation-weather-$1}
export WEATHER_ACCEPTANCE_CONTROL_DIR=$WEATHER_ACCEPTANCE_OUTPUT_DIR/control
export WEATHER_ACCEPTANCE_CONTROL_PATH=$WEATHER_ACCEPTANCE_CONTROL_DIR/control.json
export WEATHER_ACCEPTANCE_CAPTURE_DIR=$WEATHER_ACCEPTANCE_OUTPUT_DIR/capture
export WEATHER_ACCEPTANCE_BASE_URL=http://127.0.0.1:15291
mkdir -p "$WEATHER_ACCEPTANCE_CONTROL_DIR" "$WEATHER_ACCEPTANCE_CAPTURE_DIR"
compose=(docker compose -p "$WEATHER_ACCEPTANCE_PROJECT" -f "$root/tools/acceptance/overview-weather/compose.yml" -f "$root/tools/acceptance/aviation-weather/compose.yml")
owned=0
cleanup() {
  result=$?
  trap - EXIT INT TERM
  if [[ $owned == 1 ]]; then
    "${compose[@]}" logs --no-color > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/containers.log" 2>&1 || true
    "${compose[@]}" down --volumes --remove-orphans > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
    for kind in containers networks volumes; do
      case "$kind" in
        containers) remaining=$(docker ps -aq --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT");;
        networks) remaining=$(docker network ls -q --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT");;
        volumes) remaining=$(docker volume ls -q --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT");;
      esac
      if [[ -n $remaining ]]; then printf '%s remaining: %s\n' "$kind" "$remaining" >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log"; result=1; fi
    done
  fi
  rm -rf -- "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
  python3 - "$result" <<'PY'
import json,os,socket,sys,time
from pathlib import Path
clear=False
for attempt in range(65):
    try:
        for port in (15291,18291):
            with socket.socket() as s:s.bind(('127.0.0.1',port))
        clear=True;break
    except OSError:time.sleep(1)
result=int(sys.argv[1]) if clear else 1
(Path(os.environ['WEATHER_ACCEPTANCE_OUTPUT_DIR'])/'cleanup.json').write_text(json.dumps({'result':result,'ports_free':clear,'project':os.environ['WEATHER_ACCEPTANCE_PROJECT']}))
sys.exit(result)
PY
  exit "$?"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 - <<'PY'
import json,os,socket
from pathlib import Path
for port in (15291,18291):
    with socket.socket() as s:s.bind(('127.0.0.1',port))
(Path(os.environ['WEATHER_ACCEPTANCE_OUTPUT_DIR'])/'runtime-owner.json').write_text(json.dumps({'pid':os.getppid(),'process_group':os.getpgid(os.getppid()),'project':os.environ['WEATHER_ACCEPTANCE_PROJECT'],'source_root':os.environ['WEATHER_ACCEPTANCE_SOURCE_ROOT'],'ports':[15291,18291],'private_volumes':['missions','settings','satellites','coverage','routes','simulation-routes','pois','metrics']}))
PY
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker volume ls -q --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker network ls -q --filter label=com.docker.compose.project="$WEATHER_ACCEPTANCE_PROJECT") ]]; then
  echo 'Existing task project; refusing to take ownership' >&2; exit 2
fi
git archive "$1" | tar -x -C "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
python3 "$WEATHER_ACCEPTANCE_SOURCE_ROOT/tools/acceptance/aviation-weather/generate_fixtures.py" "$WEATHER_ACCEPTANCE_CAPTURE_DIR"
printf '{}\n' > "$WEATHER_ACCEPTANCE_CONTROL_PATH"
chmod 0777 "$WEATHER_ACCEPTANCE_CONTROL_DIR"
chmod 0666 "$WEATHER_ACCEPTANCE_CONTROL_PATH"
"${compose[@]}" config > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/compose.yml"
printf '%s\n' "$1" > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/candidate-sha.txt"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-context}" >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
timeout --kill-after=10s 20m "${compose[@]}" build --no-cache > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/build.log" 2>&1
owned=1
timeout --kill-after=10s 5m "${compose[@]}" up -d --no-build --wait --wait-timeout 180 > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/start.log" 2>&1
docker image inspect "$WEATHER_ACCEPTANCE_PROJECT-backend:$1" "$WEATHER_ACCEPTANCE_PROJECT-frontend:$1" --format '{{.RepoTags}} {{.Id}}' > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/images.txt"
curl --fail --silent --max-time 10 http://127.0.0.1:15291/api/status > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/status.json"
cd frontend/mission-planner
timeout --kill-after=10s 10m npx playwright test --config playwright.aviation-acceptance.config.ts
