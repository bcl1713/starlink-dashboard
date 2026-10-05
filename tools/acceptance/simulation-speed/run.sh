#!/usr/bin/env bash
# Production images from an exact tracked archive; exclusive task ownership.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Acceptance requires a clean tracked worktree; commit the candidate first.' >&2
  exit 2
fi
head_sha=$(git rev-parse HEAD)
if [[ -n ${ACCEPTANCE_CANDIDATE_SHA:-} && $ACCEPTANCE_CANDIDATE_SHA != "$head_sha" ]]; then
  echo 'Acceptance candidate must equal clean checked-out HEAD.' >&2; exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA=$head_sha
if [[ ${1:-} != --check && $# != 0 ]]; then echo 'usage: run.sh [--check]' >&2; exit 2; fi
# Refuse prior projects even if their port is free; never force a takeover.
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-262) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-262) ]]; then
  echo 'Existing starlink-262 resources found; inspect ownership before cleanup.' >&2
  exit 2
fi
python3 - <<'PY'
import socket
import sys
with socket.socket() as listener:
    try:
        listener.bind(('127.0.0.1', 15262))
    except OSError as error:
        sys.exit(f'Acceptance port 127.0.0.1:15262 occupied: {error}')
PY
if [[ ${1:-} == --check ]]; then exit 0; fi
export SIMULATION_SPEED_SOURCE_ROOT
SIMULATION_SPEED_SOURCE_ROOT=$(mktemp -d /tmp/starlink-262-source.XXXXXX)
export SIMULATION_SPEED_EVIDENCE_DIR
SIMULATION_SPEED_EVIDENCE_DIR=${SIMULATION_SPEED_EVIDENCE_DIR:-"/tmp/starlink-262-evidence-$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$SIMULATION_SPEED_EVIDENCE_DIR"
export SIMULATION_ACCEPTANCE_MODE=simulation SIMULATION_MODE=true SIMULATION_BACKEND_APP=main:app
compose=(docker compose -p starlink-262 -f "$root/tools/acceptance/simulation-speed/compose.yml")
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$SIMULATION_SPEED_EVIDENCE_DIR/containers.log" 2>&1 || true
    "${compose[@]}" down --volumes > "$SIMULATION_SPEED_EVIDENCE_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-262) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-262) ]]; then result=1; fi
    python3 - <<'PY' >> "$SIMULATION_SPEED_EVIDENCE_DIR/cleanup.log" 2>&1 || result=1
import socket
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 15262))
print('No starlink-262 containers/volumes or port 15262 listeners remain.')
PY
  fi
  rm -rf -- "$SIMULATION_SPEED_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$SIMULATION_SPEED_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}} {{.SecurityOptions}}' > "$SIMULATION_SPEED_EVIDENCE_DIR/docker-runtime.txt"
docker context show >> "$SIMULATION_SPEED_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$SIMULATION_SPEED_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$SIMULATION_SPEED_EVIDENCE_DIR/candidate-sha.txt"
"${compose[@]}" config --quiet
"${compose[@]}" config > "$SIMULATION_SPEED_EVIDENCE_DIR/compose.yml"
"${compose[@]}" build > "$SIMULATION_SPEED_EVIDENCE_DIR/build.log" 2>&1
started=1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 > "$SIMULATION_SPEED_EVIDENCE_DIR/start.log" 2>&1
docker image inspect "starlink-262-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-262-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$SIMULATION_SPEED_EVIDENCE_DIR/images.txt"
"${compose[@]}" exec -T starlink-location python --version > "$SIMULATION_SPEED_EVIDENCE_DIR/backend-runtime.txt"
curl --fail --silent http://127.0.0.1:15262/overview > /dev/null
export SIMULATION_ACCEPTANCE_BASE_URL=http://127.0.0.1:15262
cd frontend/mission-planner
node --version > "$SIMULATION_SPEED_EVIDENCE_DIR/browser-runtime.txt"
npx playwright --version >> "$SIMULATION_SPEED_EVIDENCE_DIR/browser-runtime.txt"
export SIMULATION_ACCEPTANCE_OUTPUT_DIR="$SIMULATION_SPEED_EVIDENCE_DIR/browser"
npx playwright test --config playwright.simulation-acceptance.config.ts --grep-invert 'restart-idle|live mode'
"${compose[@]}" restart starlink-location > "$SIMULATION_SPEED_EVIDENCE_DIR/restart.log" 2>&1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 >> "$SIMULATION_SPEED_EVIDENCE_DIR/restart.log" 2>&1
SIMULATION_ACCEPTANCE_OUTPUT_DIR="$SIMULATION_SPEED_EVIDENCE_DIR/restart-browser" npx playwright test --config playwright.simulation-acceptance.config.ts --grep restart-idle
export SIMULATION_ACCEPTANCE_MODE=live SIMULATION_MODE=false SIMULATION_BACKEND_APP=backend_fixture:app
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 --force-recreate starlink-location > "$SIMULATION_SPEED_EVIDENCE_DIR/live-start.log" 2>&1
SIMULATION_ACCEPTANCE_OUTPUT_DIR="$SIMULATION_SPEED_EVIDENCE_DIR/live-browser" npx playwright test --config playwright.simulation-acceptance.config.ts --grep 'live mode'
