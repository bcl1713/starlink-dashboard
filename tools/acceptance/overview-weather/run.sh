#!/usr/bin/env bash
# Exact tracked candidate, isolated volumes and production Dockerfiles/Nginx.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
export WEATHER_ACCEPTANCE_PROJECT=${WEATHER_ACCEPTANCE_PROJECT:-starlink-144-weather}
export WEATHER_ACCEPTANCE_FRONTEND_PORT=${WEATHER_ACCEPTANCE_FRONTEND_PORT:-15278}
export WEATHER_ACCEPTANCE_BACKEND_PORT=${WEATHER_ACCEPTANCE_BACKEND_PORT:-18278}
export WEATHER_ACCEPTANCE_CAPTURE_DIR=${WEATHER_ACCEPTANCE_CAPTURE_DIR:-$root/tools/acceptance/overview-weather}
export WEATHER_ACCEPTANCE_MODE=${WEATHER_ACCEPTANCE_MODE:-production}
if [[ ${1:-} == --check ]]; then
  python3 -m py_compile "$root/tools/acceptance/overview-weather/"*.py
  bash -n "$0"
  exit 0
fi
if [[ $# != 1 || ! $1 =~ ^[a-f0-9]{40}$ ]]; then
  echo 'usage: run.sh --check | exact 40-hex committed SHA' >&2; exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA=$1
if [[ $ACCEPTANCE_CANDIDATE_SHA != $(git rev-parse HEAD) || -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Acceptance requires the clean tracked HEAD candidate.' >&2; exit 2
fi
python3 - <<'PORTS'
import os, socket
for port in (int(os.environ["WEATHER_ACCEPTANCE_BACKEND_PORT"]), int(os.environ["WEATHER_ACCEPTANCE_FRONTEND_PORT"])):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
PORTS
# Archive excludes local node_modules, test artifacts and all untracked inputs.
export WEATHER_ACCEPTANCE_SOURCE_ROOT
WEATHER_ACCEPTANCE_SOURCE_ROOT=$(mktemp -d /tmp/starlink-${WEATHER_ACCEPTANCE_PROJECT}-source.XXXXXX)
export WEATHER_ACCEPTANCE_OUTPUT_DIR
WEATHER_ACCEPTANCE_OUTPUT_DIR=${WEATHER_ACCEPTANCE_OUTPUT_DIR:-"$root/.superpowers/sdd/2026-10-05-overview-weather-overlay/evidence/production-$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$WEATHER_ACCEPTANCE_OUTPUT_DIR"
export WEATHER_ACCEPTANCE_CONTROL_DIR="$WEATHER_ACCEPTANCE_OUTPUT_DIR/control"
mkdir -p "$WEATHER_ACCEPTANCE_CONTROL_DIR"
chmod 0777 "$WEATHER_ACCEPTANCE_CONTROL_DIR"
export WEATHER_ACCEPTANCE_CONTROL_PATH="$WEATHER_ACCEPTANCE_CONTROL_DIR/control.json"
printf '{}\n' > "$WEATHER_ACCEPTANCE_CONTROL_PATH"
chmod 0666 "$WEATHER_ACCEPTANCE_CONTROL_PATH"

compose=(docker compose -p "$WEATHER_ACCEPTANCE_PROJECT" -f "$root/tools/acceptance/overview-weather/compose.yml")
# Never take ownership of an existing acceptance project, even on free ports.
if [[ -n $(docker ps -aq --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker volume ls -q --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker network ls -q --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") ]]; then
  echo "Existing $WEATHER_ACCEPTANCE_PROJECT resources found; inspect ownership before cleanup." >&2
  rmdir "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
  exit 2
fi
python3 - <<'OWNER'
import json, os
from pathlib import Path
out=Path(os.environ['WEATHER_ACCEPTANCE_OUTPUT_DIR'])
(out/'runtime-owner.json').write_text(json.dumps({'project':os.environ['WEATHER_ACCEPTANCE_PROJECT'],'owner_pid':os.getppid(),'process_group':os.getpgid(os.getppid()),'source_root':os.environ['WEATHER_ACCEPTANCE_SOURCE_ROOT'],'ports':[int(os.environ['WEATHER_ACCEPTANCE_FRONTEND_PORT']),int(os.environ['WEATHER_ACCEPTANCE_BACKEND_PORT'])],'private_volumes':['missions','settings','satellites','coverage','routes','simulation-routes','pois','metrics']}))
OWNER
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/containers.log" 2>&1 || true
    docker stats --no-stream $(docker ps -q --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/resources.txt" 2>&1 || true
    "${compose[@]}" down --volumes --remove-orphans > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker volume ls -q --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") || -n $(docker network ls -q --filter "label=com.docker.compose.project=$WEATHER_ACCEPTANCE_PROJECT") ]]; then result=1; fi
    python3 - <<'PY' >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
import os, socket
for port in (int(os.environ["WEATHER_ACCEPTANCE_BACKEND_PORT"]), int(os.environ["WEATHER_ACCEPTANCE_FRONTEND_PORT"])):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
print('No task containers/networks/volumes or listeners remain.')
PY
  fi
  rm -rf -- "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
  python3 - "$result" <<'CLEANUP'
import json, os, sys
from pathlib import Path
(Path(os.environ['WEATHER_ACCEPTANCE_OUTPUT_DIR'])/'cleanup.json').write_text(json.dumps({'status':'passed' if sys.argv[1]=='0' else 'failed','result':int(sys.argv[1]),'project':os.environ['WEATHER_ACCEPTANCE_PROJECT']}))
CLEANUP
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
docker context show >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
"${compose[@]}" config --quiet
"${compose[@]}" config > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/compose.yml"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/candidate-sha.txt"
"${compose[@]}" build > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/build.log" 2>&1
started=1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/start.log" 2>&1
docker image inspect "$WEATHER_ACCEPTANCE_PROJECT-backend:$ACCEPTANCE_CANDIDATE_SHA" "$WEATHER_ACCEPTANCE_PROJECT-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/images.txt"
# Nginx itself must serve the SPA and the backend API on the same origin.
curl --fail --silent http://127.0.0.1:$WEATHER_ACCEPTANCE_FRONTEND_PORT/overview > /dev/null
curl --fail --silent http://127.0.0.1:$WEATHER_ACCEPTANCE_FRONTEND_PORT/api/status > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/status.json"
export WEATHER_ACCEPTANCE_BASE_URL=http://127.0.0.1:$WEATHER_ACCEPTANCE_FRONTEND_PORT
cd frontend/mission-planner
node --version > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npm --version >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npx playwright --version >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
playwright=(npx playwright test --config playwright.weather-acceptance.config.ts)
if [[ -n ${WEATHER_ACCEPTANCE_GREP:-} ]]; then playwright+=(--grep "$WEATHER_ACCEPTANCE_GREP"); fi
WEATHER_ACCEPTANCE_OUTPUT_DIR="$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser" "${playwright[@]}"
