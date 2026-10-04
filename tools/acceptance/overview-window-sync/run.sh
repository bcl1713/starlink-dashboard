#!/usr/bin/env bash
# Exact tracked candidate, isolated volumes and production Dockerfiles/Nginx.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Acceptance requires a clean tracked worktree; commit the candidate first.' >&2
  exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD)
python3 - <<'PY'
import socket
import sys
for port in (18257, 15257):
    with socket.socket() as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError as error:
            sys.exit(f'Acceptance port 127.0.0.1:{port} occupied: {error}')
PY
if [[ ${1:-} == --check ]]; then exit 0; fi
if [[ $# != 0 ]]; then echo 'usage: run.sh [--check]' >&2; exit 2; fi
# Archive excludes local node_modules, test artifacts and all untracked inputs.
export OVERVIEW_ACCEPTANCE_SOURCE_ROOT
OVERVIEW_ACCEPTANCE_SOURCE_ROOT=$(mktemp -d /tmp/starlink-257-source.XXXXXX)
export OVERVIEW_ACCEPTANCE_OUTPUT_DIR
OVERVIEW_ACCEPTANCE_OUTPUT_DIR=${OVERVIEW_ACCEPTANCE_OUTPUT_DIR:-"$root/.superpowers/sdd/2026-10-04-overview-window-sync-acceptance/evidence/task5/production-$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR"
compose=(docker compose -p starlink-257 -f "$root/tools/acceptance/overview-window-sync/compose.yml")
# Never take ownership of an existing acceptance project, even on free ports.
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-257) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-257) ]]; then
  echo 'Existing starlink-257 resources found; inspect ownership before cleanup.' >&2
  rmdir "$OVERVIEW_ACCEPTANCE_SOURCE_ROOT"
  exit 2
fi
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/containers.log" 2>&1 || true
    "${compose[@]}" down --volumes > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-257) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-257) ]]; then result=1; fi
    python3 - <<'PY' >> "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/cleanup.log" 2>&1 || result=1
import socket
for port in (18257, 15257):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
print('No task containers/volumes or listeners remain on 18257/15257.')
PY
  fi
  rm -rf -- "$OVERVIEW_ACCEPTANCE_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$OVERVIEW_ACCEPTANCE_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
docker context show >> "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/docker-runtime.txt"
"${compose[@]}" config --quiet
"${compose[@]}" config > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/compose.yml"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/candidate-sha.txt"
"${compose[@]}" build > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/build.log" 2>&1
started=1
"${compose[@]}" up --no-build --detach --wait --wait-timeout 180 > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/start.log" 2>&1
docker image inspect "starlink-257-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-257-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/images.txt"
# Nginx itself must serve the SPA and the backend API on the same origin.
curl --fail --silent http://127.0.0.1:15257/overview > /dev/null
curl --fail --silent http://127.0.0.1:15257/api/status > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/status.json"
export OVERVIEW_ACCEPTANCE_BASE_URL=http://127.0.0.1:15257
cd frontend/mission-planner
node --version > "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npm --version >> "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npx playwright --version >> "$OVERVIEW_ACCEPTANCE_OUTPUT_DIR/browser-runtime.txt"
npx playwright test --config playwright.window-acceptance.config.ts
