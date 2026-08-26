#!/usr/bin/env bash
# Smoke-test the Portainer profile with only task-scoped Docker resources.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose_file="$repo_root/deployment/portainer-ghcr-compose.yml"
project="starlink-ghcr-smoke-$RANDOM-$RANDOM"
network="${project}-proxy"
# Match the immutable sha-* contract used by the GHCR publishing workflow.
image_tag="sha-$(git -C "$repo_root" rev-parse HEAD)"
data_dir=$(mktemp -d "${TMPDIR:-/tmp}/${project}.XXXXXX")

cleanup() {
  docker compose --project-name "$project" --file "$compose_file" down \
    --remove-orphans >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  # Grafana and Prometheus create files as their container users. Restore
  # directory permissions from an isolated image before deleting the task path.
  docker run --rm --user 0 --entrypoint /bin/sh -v "$data_dir":/data \
    "ghcr.io/bcl1713/starlink-dashboard/grafana:${image_tag}" \
    -c 'chmod -R a+rwx /data' >/dev/null 2>&1 || true
  rm -rf "$data_dir"
}
trap cleanup EXIT

mkdir -p \
  "$data_dir/app" \
  "$data_dir/routes/routes" \
  "$data_dir/routes/sim_routes" \
  "$data_dir/prometheus" \
  "$data_dir/grafana"
# The images run as non-root users. These isolated test paths are intentionally
# writable by all service users and are removed by cleanup.
chmod -R a+rwx "$data_dir"
docker network create "$network" >/dev/null

docker build --tag "ghcr.io/bcl1713/starlink-dashboard/starlink-location:${image_tag}" \
  "$repo_root/backend/starlink-location"
docker build --tag "ghcr.io/bcl1713/starlink-dashboard/mission-planner:${image_tag}" \
  "$repo_root/frontend/mission-planner"
docker build --file "$repo_root/deployment/prometheus/Dockerfile" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/prometheus:${image_tag}" "$repo_root"
docker build --file "$repo_root/deployment/grafana/Dockerfile" \
  --tag "ghcr.io/bcl1713/starlink-dashboard/grafana:${image_tag}" "$repo_root"

export STARLINK_IMAGE_TAG="$image_tag"
export STARLINK_PROXY_NETWORK="$network"
export GRAFANA_ADMIN_PASSWORD="smoke-test-only-password"
export STARLINK_APP_DATA_PATH="$data_dir/app"
export STARLINK_ROUTE_DATA_PATH="$data_dir/routes"
export STARLINK_PROMETHEUS_DATA_PATH="$data_dir/prometheus"
export STARLINK_GRAFANA_DATA_PATH="$data_dir/grafana"

# This renders without a repository .env file and starts every service.
docker compose --project-name "$project" --file "$compose_file" config --quiet
docker compose --project-name "$project" --file "$compose_file" up --detach
docker compose --project-name "$project" --file "$compose_file" exec -T grafana env \
  | grep -Fx 'GF_PLUGINS_PREINSTALL=grafana-clock-panel,yesoreyeram-infinity-datasource@3.11.1'

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
probe http://grafana:3000/api/health
probe http://mission-planner/
probe http://mission-planner/api/v2/missions
