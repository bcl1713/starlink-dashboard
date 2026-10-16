# Configuration

Copy `.env.example` to `.env` before using the local Compose stack. The example
and checked-out Compose file define supported defaults; backend model fields are
defined in `backend/starlink-location/app/models/config.py`.

## Simulation mode

`STARLINK_MODE=simulation` is the default. No dish is required. See
[simulation configuration](configuration/simulation-mode.md), including paced
mission-leg replay.

## Live mode

Set `STARLINK_MODE=live`, `STARLINK_DISH_HOST`, and `STARLINK_DISH_PORT` in
`.env`, then recreate the backend. Live mode stays live when the dish is
unreachable; it does not switch to simulated telemetry. See
[live setup](configuration/live-mode/setup.md).

## Settings references

- [Environment variables](configuration/environment-variables.md)
- [Network configuration](configuration/network-configuration.md)
- [Storage and retention](configuration/storage-configuration.md)
- [Performance tuning](configuration/performance-tuning.md)
- [Logging](configuration/logging-configuration.md)
- [Upload limits](configuration/mission-package-upload-limits.md)

Operational clocks and dashboard preferences are configured in Mission Planner
and persisted in backend settings. They are not environment clock variables.
After `.env` changes use `./scripts/compose.sh up -d`; after code or baked-in
`config.yaml` changes use `./scripts/compose.sh up -d --build`.
