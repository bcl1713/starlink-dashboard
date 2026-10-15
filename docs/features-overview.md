# Features Overview

The maintained [feature catalog](features/overview.md) describes current
monitoring, navigation, mission planning, weather, traffic, and system features.
See [release notes](release-notes.md) for the v1.0.0 baseline and later `dev`
changes. Early phase/session counts are historical, not release status.

## Repository Structure

- `backend/starlink-location/`: FastAPI service, simulation, planning, exports,
  GFS processing, and backend tests
- `frontend/mission-planner/`: React Mission Planner and native Overview globe
- `monitoring/prometheus/`: scrape configuration and alert rules
- `tools/`: verification and isolated acceptance runners
- `scripts/`: Compose and development helpers
- `docs/`: operator, API, architecture, and contributor guides
- `docker-compose.yml`: backend, frontend, Prometheus, and GFS worker
- `.env.example`: deployment configuration defaults

Start with [setup](setup/quick-start.md) or the [documentation index](index.md).
Resource use depends on enabled layers, mission size, and metrics retention;
historical estimates are not measured performance guarantees.
