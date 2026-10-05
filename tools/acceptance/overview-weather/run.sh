#!/usr/bin/env bash
# Exact tracked candidate, isolated volumes and production Dockerfiles/Nginx.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
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
import socket
for port in (18278, 15278):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
PORTS
# Archive excludes local node_modules, test artifacts and all untracked inputs.
export WEATHER_ACCEPTANCE_SOURCE_ROOT
WEATHER_ACCEPTANCE_SOURCE_ROOT=$(mktemp -d /tmp/starlink-144-weather-source.XXXXXX)
export WEATHER_ACCEPTANCE_OUTPUT_DIR
WEATHER_ACCEPTANCE_OUTPUT_DIR=${WEATHER_ACCEPTANCE_OUTPUT_DIR:-"$root/.superpowers/sdd/2026-10-05-overview-weather-overlay/evidence/production-$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$WEATHER_ACCEPTANCE_OUTPUT_DIR"
export WEATHER_ACCEPTANCE_CONTROL_DIR="$WEATHER_ACCEPTANCE_OUTPUT_DIR/control"
mkdir -p "$WEATHER_ACCEPTANCE_CONTROL_DIR"
chmod 0777 "$WEATHER_ACCEPTANCE_CONTROL_DIR"
export WEATHER_ACCEPTANCE_CONTROL_PATH="$WEATHER_ACCEPTANCE_CONTROL_DIR/control.json"
printf '{}\n' > "$WEATHER_ACCEPTANCE_CONTROL_PATH"
chmod 0666 "$WEATHER_ACCEPTANCE_CONTROL_PATH"

compose=(docker compose -p starlink-144-weather -f "$root/tools/acceptance/overview-weather/compose.yml")
# Never take ownership of an existing acceptance project, even on free ports.
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-144-weather) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-144-weather) ]]; then
  echo 'Existing starlink-144-weather resources found; inspect ownership before cleanup.' >&2
  rmdir "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
  exit 2
fi
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/containers.log" 2>&1 || true
    docker stats --no-stream > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/resources.txt" 2>&1 || true
    "${compose[@]}" down --volumes > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-144-weather) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-144-weather) ]]; then result=1; fi
    python3 - <<'PY' >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
import socket
for port in (18278, 15278):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
print('No task containers/volumes or listeners remain on 18278/15278.')
PY
  fi
  rm -rf -- "$WEATHER_ACCEPTANCE_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
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
docker image inspect "starlink-144-weather-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-144-weather-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/images.txt"
# Nginx itself must serve the SPA and the backend API on the same origin.
curl --fail --silent http://127.0.0.1:15278/overview > /dev/null
curl --fail --silent http://127.0.0.1:15278/api/status > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/status.json"
export WEATHER_ACCEPTANCE_BASE_URL=http://127.0.0.1:15278
cd frontend/mission-planner
node --version > "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npm --version >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npx playwright --version >> "$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
WEATHER_ACCEPTANCE_OUTPUT_DIR="$WEATHER_ACCEPTANCE_OUTPUT_DIR/browser" npx playwright test --config playwright.weather-acceptance.config.ts
