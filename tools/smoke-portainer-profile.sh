#!/usr/bin/env bash
# Smoke-test the Portainer profile without touching a Portainer-managed stack.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose_file="$repo_root/deployment/portainer-ghcr-compose.yml"
project="starlink-ghcr-smoke-$RANDOM-$RANDOM"
network="${project}-proxy"
image_tag="smoke-${project}"
volumes=(
  missions satellites sat-coverage route sim-route poi prometheus grafana
)

cleanup() {
  docker compose --project-name "$project" --file "$compose_file" down \
    --remove-orphans >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  for volume in "${volumes[@]}"; do
    docker volume rm "${project}-${volume}" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

for volume in "${volumes[@]}"; do
  docker volume create "${project}-${volume}" >/dev/null
done
docker network create "$network" >/dev/null

docker build --tag "ghcr.io/bcl1713/starlink-dashboard/starlink-location:${image_tag}" \
  "$repo_root/backend/starlink-location"
docker build --tag "ghcr.io/bcl1713/starlink-dashboard/mission-planner:${image_tag}" \
  "$repo_root/frontend/mission-planner"

export STARLINK_IMAGE_TAG="$image_tag"
export STARLINK_PROXY_NETWORK="$network"
export GRAFANA_ADMIN_PASSWORD="smoke-test-only-password"
export STARLINK_MISSIONS_VOLUME="${project}-missions"
export STARLINK_SATELLITES_VOLUME="${project}-satellites"
export STARLINK_SAT_COVERAGE_VOLUME="${project}-sat-coverage"
export STARLINK_ROUTE_VOLUME="${project}-route"
export STARLINK_SIM_ROUTE_VOLUME="${project}-sim-route"
export STARLINK_POI_VOLUME="${project}-poi"
export STARLINK_PROMETHEUS_VOLUME="${project}-prometheus"
export STARLINK_GRAFANA_VOLUME="${project}-grafana"

# This exercises a clean profile render without a repository .env file.
docker compose --project-name "$project" --file "$compose_file" config --quiet
docker compose --project-name "$project" --file "$compose_file" up --detach
docker compose --project-name "$project" --file "$compose_file" exec -T grafana env \
  | grep -Fx 'GF_PLUGINS_PREINSTALL=grafana-clock-panel,yesoreyeram-infinity-datasource@3.11.1'

probe() {
  local url=$1
  for _ in $(seq 1 30); do
    if docker run --rm --network "$network" curlimages/curl:8.12.1 \
      --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

probe http://starlink-location:8000/health
probe http://prometheus:9090/-/ready
probe http://starlink-location:8000/api/v2/missions
