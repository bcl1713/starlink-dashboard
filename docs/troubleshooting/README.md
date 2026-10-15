# Troubleshooting

These checks describe the current repository-managed Compose profile. Use the
documentation and configuration matching your checked-out release; current `dev`
may include features added after v1.0.0.

## First checks

Run from your installation directory; adjust URLs for configured host ports:

```bash
docker compose ps
docker compose logs --tail=200 starlink-location
docker compose logs --tail=100 prometheus mission-planner gfs-worker
curl --fail --max-time 10 http://localhost:8000/health
curl --fail --max-time 10 http://localhost:5173/api/status
curl --fail --max-time 10 http://localhost:9090/-/ready
```

Backend startup can take time; its healthcheck has a 90-second startup period.
Prometheus waits for backend health. A running backend HTTP server does not
prove dish connectivity; live health includes a separate `dish_connected` flag.

## Services fail to start

Validate configuration with `./scripts/compose.sh config --quiet`. Ensure `.env`
exists, the configured host ports are free, and Docker uses the intended daemon.
Preserve `DOCKER_HOST` and active context; in managed environments follow
[cloud Docker discovery](../development/cloud-docker.md).

Use `./scripts/compose.sh up -d --build` when updating source or baked-in
config. The wrapper supplies the commit SHA required by builds. After editing
`.env`, use `./scripts/compose.sh up -d` to recreate services; `restart` keeps
the old environment. Inspect logs before repeatedly rebuilding.

If port 8000 or 9090 conflicts, change `STARLINK_LOCATION_PORT` or
`PROMETHEUS_PORT` in `.env`. The frontend's 5173 mapping is in Compose. Internal
backend/Prometheus ports remain 8000/9090.

## Dashboard loads but API requests fail

Mission Planner at <http://localhost:5173> proxies `/api/...` to the backend.
Compare `http://localhost:5173/api/status` with the direct backend status URL. A
failed proxied call with a healthy direct backend points to frontend/proxy
configuration. The frontend is a static Nginx image; rebuild after changing its
build arguments or Nginx config. The backend retains legacy `/ui/routes` and
`/ui/pois` pages; prefer the maintained route and POI screens in Mission
Planner.

## Missing telemetry or history

See [live connectivity](connectivity/live-mode.md) and
[metrics monitoring](metrics-monitoring.md). Simulation can deliberately freeze
at replay completion, and live dish loss does not trigger simulation fallback.
Check mode and freshness before interpreting a stationary position.

## Data and resource problems

See [data recovery checks](data-issues.md),
[storage layout](../setup/configuration/storage-configuration.md), and
[performance tuning](../setup/configuration/performance-tuning.md). Do not reset
JSON files, remove volumes, or run Docker prune as a first troubleshooting step.
Preserve evidence and backups before repair.

For a support report include the checked-out commit/tag, service status,
sanitized logs, mode, and failing request/response. Do not publish credentials
or sensitive mission content.
