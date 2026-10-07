#!/usr/bin/env bash
# Smoke-test the Portainer profile with only task-scoped Docker resources.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose_file="$repo_root/deployment/portainer-ghcr-compose.yml"
project="starlink-ghcr-smoke-$RANDOM-$RANDOM"
network="${project}-proxy"
# Match the immutable sha-* contract used by the GHCR publishing workflow.
if ! candidate_sha=$(git -C "$repo_root" rev-parse --verify HEAD) ||
    [[ ! $candidate_sha =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'Expected a full 40-character lowercase commit SHA from git' >&2
  exit 1
fi
image_tag="sha-${candidate_sha}"
data_dir=$(mktemp -d "${TMPDIR:-/tmp}/${project}.XXXXXX")

cleanup() {
  docker compose --project-name "$project" --file "$compose_file" down \
    --volumes --remove-orphans >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  # Prometheus creates files as its container user. Restore
  # directory permissions from an isolated image before deleting the task path.
  docker run --rm --user 0 --entrypoint /bin/sh -v "$data_dir":/data \
    "ghcr.io/bcl1713/starlink-dashboard/prometheus:${image_tag}" \
    -c 'chmod -R a+rwx /data' >/dev/null 2>&1 || true
  rm -rf "$data_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Record ownership before creating Docker resources.
printf '%s\n' "pid=$$" "pgid=$(ps -o pgid= -p $$)" \
  "project=$project" "network=$network" "temporary_path=$data_dir" \
  "image_tag=$image_tag" > "$data_dir/ownership.txt"

mkdir -p \
  "$data_dir/app" \
  "$data_dir/routes/routes" \
  "$data_dir/routes/sim_routes" \
  "$data_dir/prometheus"
# The images run as non-root users. These isolated test paths are intentionally
# writable by all service users and are removed by cleanup.
chmod -R a+rwx "$data_dir"
export STARLINK_IMAGE_TAG="$image_tag"
export STARLINK_PROXY_NETWORK="$network"
export STARLINK_APP_DATA_PATH="$data_dir/app"
export STARLINK_ROUTE_DATA_PATH="$data_dir/routes"
export STARLINK_PROMETHEUS_DATA_PATH="$data_dir/prometheus"

docker network create "$network" >/dev/null

docker build --build-arg "ACCEPTANCE_CANDIDATE_SHA=${candidate_sha}" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/starlink-location:${image_tag}" \
  "$repo_root/backend/starlink-location"
docker build --build-arg "ACCEPTANCE_CANDIDATE_SHA=${candidate_sha}" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/mission-planner:${image_tag}" \
  "$repo_root/frontend/mission-planner"
docker build --build-arg "ACCEPTANCE_CANDIDATE_SHA=${candidate_sha}" \
  --file "$repo_root/backend/starlink-location/Dockerfile.gfs" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/gfs-worker:${image_tag}" \
  "$repo_root/backend/starlink-location"
docker build --file "$repo_root/deployment/prometheus/Dockerfile" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/prometheus:${image_tag}" "$repo_root"

# This renders without a repository .env file and starts every service.
docker compose --project-name "$project" --file "$compose_file" config --quiet
docker compose --project-name "$project" --file "$compose_file" up --detach

probe() {
  local url=$1
  for _ in $(seq 1 90); do
    if docker run --rm --network "$network" curlimages/curl:8.12.1 \
      --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# All names below are aliases on the external proxy network. The Mission
# Planner probes exercise its documented same-origin dashboard and API routes.
probe http://starlink-location:8000/health
probe http://prometheus:9090/-/ready
probe http://mission-planner/
probe http://mission-planner/api/v2/missions

# API health remains usable when optional weather is unavailable. Verify the
# private worker's held owner lock and fresh heartbeat separately, without
# requiring NOAA access or exposing a worker port.
probe_worker() {
  for _ in $(seq 1 15); do
    if docker compose --project-name "$project" --file "$compose_file" \
      exec -T --user 1000:1000 starlink-location python -c \
      'import time; from pathlib import Path; from app.services.aviation_weather.gfs.ipc import GfsMailbox; assert GfsMailbox(Path("/app/data/gfs-mailbox"), None).healthy(int(time.time() * 1000))'; then
      return 0
    fi
    sleep 2
  done
  return 1
}
probe_worker
