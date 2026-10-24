#!/usr/bin/env bash
# Task-owned production images, real Nginx/API/Prometheus, no live provider.
set -euo pipefail
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo 'Commit the tracked acceptance candidate before running.' >&2
  exit 2
fi
export ACCEPTANCE_CANDIDATE_SHA ADSB_SOURCE_ROOT ADSB_EVIDENCE_DIR
export ADSB_ACCEPTANCE_PROJECT ADSB_ACCEPTANCE_PORT ADSB_ACCEPTANCE_IMAGE_PREFIX
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD)
ADSB_ACCEPTANCE_PROJECT=${ADSB_ACCEPTANCE_PROJECT:-"starlink-adsb-${ACCEPTANCE_CANDIDATE_SHA:0:12}-$$"}
ADSB_ACCEPTANCE_PORT=${ADSB_ACCEPTANCE_PORT:-15244}
ADSB_ACCEPTANCE_IMAGE_PREFIX=${ADSB_ACCEPTANCE_IMAGE_PREFIX:-$ADSB_ACCEPTANCE_PROJECT}
if [[ ! $ADSB_ACCEPTANCE_PROJECT =~ ^[a-z0-9][a-z0-9_-]+$ || ! $ADSB_ACCEPTANCE_PORT =~ ^[0-9]+$ ]] || (( ADSB_ACCEPTANCE_PORT < 1024 || ADSB_ACCEPTANCE_PORT > 65535 )); then
  echo 'Use a private Compose project and an unprivileged valid port.' >&2
  exit 2
fi
ADSB_SOURCE_ROOT=$(mktemp -d /tmp/starlink-adsb-source.XXXXXX)
ADSB_EVIDENCE_DIR=${ADSB_EVIDENCE_DIR:-"/tmp/$ADSB_ACCEPTANCE_PROJECT-evidence"}
compose=(docker compose -p "$ADSB_ACCEPTANCE_PROJECT" -f "$root/tools/acceptance/adsb/compose.yml")
started=0
remaining_resources() {
  docker ps -aq --filter "label=com.docker.compose.project=$ADSB_ACCEPTANCE_PROJECT" || return
  docker network ls -q --filter "label=com.docker.compose.project=$ADSB_ACCEPTANCE_PROJECT" || return
  docker volume ls -q --filter "label=com.docker.compose.project=$ADSB_ACCEPTANCE_PROJECT" || return
}
cleanup() {
  result=$?
  trap - EXIT INT TERM
  if [[ $started == 1 ]]; then
    timeout --kill-after=10s 30s "${compose[@]}" logs --no-color > "$ADSB_EVIDENCE_DIR/containers.log" 2>&1 || true
    timeout --kill-after=10s 60s "${compose[@]}" down --volumes > "$ADSB_EVIDENCE_DIR/cleanup.log" 2>&1 || result=1
    if ! remaining_resources > "$ADSB_EVIDENCE_DIR/remaining-resources.txt" || [[ -s $ADSB_EVIDENCE_DIR/remaining-resources.txt ]]; then result=1; fi
  fi
  rm -rf -- "$ADSB_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$ADSB_EVIDENCE_DIR"
# Record ownership before builds, private containers or volumes can be started.
python3 - "$$" "$(ps -o pgid= -p "$$" | tr -d ' ')" <<'PY'
import json, os, sys
from pathlib import Path
project = os.environ['ADSB_ACCEPTANCE_PROJECT']
Path(os.environ['ADSB_EVIDENCE_DIR'], 'owner.json').write_text(json.dumps({
    'pid': int(sys.argv[1]), 'pgid': int(sys.argv[2]), 'project': project,
    'source': os.environ['ADSB_SOURCE_ROOT'], 'port': os.environ['ADSB_ACCEPTANCE_PORT'],
    'image_prefix': os.environ['ADSB_ACCEPTANCE_IMAGE_PREFIX'],
    'volumes': [project+'_'+name for name in ('settings','missions','satellites','orbital','coverage','routes','simulation-routes','pois','metrics')],
}, indent=2))
PY
remaining_resources > "$ADSB_EVIDENCE_DIR/preexisting-resources.txt"
if [[ -s $ADSB_EVIDENCE_DIR/preexisting-resources.txt ]]; then
  echo "Existing $ADSB_ACCEPTANCE_PROJECT resources found; do not take ownership." >&2
  exit 2
fi
python3 - <<'PY'
import os, socket
with socket.socket() as listener:
    listener.bind(('127.0.0.1', int(os.environ['ADSB_ACCEPTANCE_PORT'])))
PY
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$ADSB_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
docker context show >> "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$ADSB_EVIDENCE_DIR/candidate-sha.txt"
"${compose[@]}" config --quiet
timeout --kill-after=10s "${ADSB_ACCEPTANCE_BUILD_TIMEOUT:-1800}s" "${compose[@]}" build > "$ADSB_EVIDENCE_DIR/build.log" 2>&1
started=1
timeout --kill-after=10s 240s "${compose[@]}" up --detach --no-build --wait --wait-timeout 180 > "$ADSB_EVIDENCE_DIR/start.log" 2>&1
docker image inspect "$ADSB_ACCEPTANCE_IMAGE_PREFIX-backend:$ACCEPTANCE_CANDIDATE_SHA" "$ADSB_ACCEPTANCE_IMAGE_PREFIX-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$ADSB_EVIDENCE_DIR/images.txt"
timeout --kill-after=10s 180s node tools/acceptance/adsb/production.mjs
# Restart with provider failure proves settings persist while contacts do not.
export ADSB_ACCEPTANCE_FAIL=1
timeout --kill-after=10s 240s "${compose[@]}" up --detach --no-build --force-recreate --no-deps --wait --wait-timeout 180 starlink-location > "$ADSB_EVIDENCE_DIR/restart.log" 2>&1
timeout --kill-after=10s 30s python3 - <<'PY'
import json
import os
from pathlib import Path
import urllib.request
evidence = Path(os.environ['ADSB_EVIDENCE_DIR'])
port = os.environ['ADSB_ACCEPTANCE_PORT']
for endpoint in ('settings', 'traffic'):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/overview-adsb/{endpoint}', timeout=10) as response:
        value = json.load(response)
    evidence.joinpath(f'restarted-{endpoint}.json').write_text(json.dumps(value, indent=2))
    if endpoint == 'settings':
        assert value == json.loads(evidence.joinpath('production-settings.json').read_text())
    else:
        assert value['contacts'] == []
print('Actual Nginx restart: settings preserved, live cache empty.')
PY
