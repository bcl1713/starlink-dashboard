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
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD)
ADSB_SOURCE_ROOT=$(mktemp -d /tmp/starlink-244-source.XXXXXX)
ADSB_EVIDENCE_DIR=${ADSB_EVIDENCE_DIR:-"$root/.superpowers/sdd/2026-10-03-overview-adsb-aircraft-layer/production-$ACCEPTANCE_CANDIDATE_SHA"}
mkdir -p "$ADSB_EVIDENCE_DIR"
compose=(docker compose -p starlink-244 -f "$root/tools/acceptance/adsb/compose.yml")
if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-244) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-244) ]]; then
  echo 'Existing starlink-244 resources found; do not take ownership.' >&2
  rmdir "$ADSB_SOURCE_ROOT"
  exit 2
fi
python3 - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 15244))
PY
started=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ $started == 1 ]]; then
    "${compose[@]}" logs --no-color > "$ADSB_EVIDENCE_DIR/containers.log" 2>&1 || true
    "${compose[@]}" down --volumes > "$ADSB_EVIDENCE_DIR/cleanup.log" 2>&1 || result=1
    if [[ -n $(docker ps -aq --filter label=com.docker.compose.project=starlink-244) || -n $(docker volume ls -q --filter label=com.docker.compose.project=starlink-244) ]]; then result=1; fi
  fi
  rm -rf -- "$ADSB_SOURCE_ROOT"
  exit "$result"
}
trap cleanup EXIT
git archive "$ACCEPTANCE_CANDIDATE_SHA" | tar -x -C "$ADSB_SOURCE_ROOT"
docker info --format '{{.ServerVersion}} {{.Driver}}' > "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
docker context show >> "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "${DOCKER_HOST:-<context endpoint>}" >> "$ADSB_EVIDENCE_DIR/docker-runtime.txt"
printf '%s\n' "$ACCEPTANCE_CANDIDATE_SHA" > "$ADSB_EVIDENCE_DIR/candidate-sha.txt"
"${compose[@]}" config --quiet
"${compose[@]}" build > "$ADSB_EVIDENCE_DIR/build.log" 2>&1
started=1
"${compose[@]}" up --detach --no-build --wait --wait-timeout 180 > "$ADSB_EVIDENCE_DIR/start.log" 2>&1
docker image inspect "starlink-244-backend:$ACCEPTANCE_CANDIDATE_SHA" "starlink-244-frontend:$ACCEPTANCE_CANDIDATE_SHA" --format '{{.RepoTags}} {{.Id}}' > "$ADSB_EVIDENCE_DIR/images.txt"
node tools/acceptance/adsb/production.mjs
# Restart with provider failure proves settings persist while contacts do not.
export ADSB_ACCEPTANCE_FAIL=1
"${compose[@]}" up --detach --no-build --force-recreate --no-deps --wait --wait-timeout 180 starlink-location > "$ADSB_EVIDENCE_DIR/restart.log" 2>&1
python3 - <<'PY'
import json
import os
from pathlib import Path
import urllib.request
evidence = Path(os.environ['ADSB_EVIDENCE_DIR'])
for endpoint in ('settings', 'traffic'):
    with urllib.request.urlopen(f'http://127.0.0.1:15244/api/overview-adsb/{endpoint}') as response:
        value = json.load(response)
    evidence.joinpath(f'restarted-{endpoint}.json').write_text(json.dumps(value, indent=2))
    if endpoint == 'settings':
        assert value == json.loads(evidence.joinpath('production-settings.json').read_text())
    else:
        assert value['contacts'] == []
print('Actual Nginx restart: settings preserved, live cache empty.')
PY
