#!/usr/bin/env bash
# Isolated exact-SHA production Dockerfiles, Nginx, backend and browser controls.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Commit the candidate before production acceptance.' >&2
  exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD)
python3 - <<'PY'
import socket
for port in (18282, 15282):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
PY
compose=(docker compose -p starlink-282 -f "$root/tools/acceptance/overview-boundaries/compose.yml")
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-282) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-282) ]]; then
  echo 'Existing starlink-282 resources found; inspect ownership before cleanup.' >&2
  exit 2
fi
export BOUNDARY_ACCEPTANCE_SOURCE_ROOT
BOUNDARY_ACCEPTANCE_SOURCE_ROOT=$(mktemp -d /tmp/starlink-282-source.XXXXXX)
export BOUNDARY_ACCEPTANCE_OUTPUT_DIR
BOUNDARY_ACCEPTANCE_OUTPUT_DIR=${BOUNDARY_ACCEPTANCE_OUTPUT_DIR:-"$root/.superpowers/sdd/overview-boundaries/$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR"
started=0
cleanup() {
  result=$?
  trap - EXIT
  cd "$root"
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/containers.log" 2>&1 || true
    "${compose[@]}" down --volumes > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-282) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-282) ]]; then result=1; fi
  fi
  rm -rf -- "$BOUNDARY_ACCEPTANCE_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$BOUNDARY_ACCEPTANCE_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
docker context show >> "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/candidate-sha.txt"
"${compose[@]}" config --quiet
"${compose[@]}" build > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/build.log" 2>&1
started=1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/start.log" 2>&1
docker image inspect "starlink-282-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-282-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/images.txt"
curl --fail --silent http://127.0.0.1:15282/api/status > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/status.json"
# Execute the archived suite/config as well as the archived application.
ln -s "$root/frontend/mission-planner/node_modules" "$BOUNDARY_ACCEPTANCE_SOURCE_ROOT/frontend/mission-planner/node_modules"
cd "$BOUNDARY_ACCEPTANCE_SOURCE_ROOT/frontend/mission-planner"
node --version > "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
node node_modules/@playwright/test/cli.js --version >> "$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
BOUNDARY_ACCEPTANCE_OUTPUT_DIR="$BOUNDARY_ACCEPTANCE_OUTPUT_DIR/browser" node node_modules/@playwright/test/cli.js test --config playwright.boundaries-acceptance.config.ts
