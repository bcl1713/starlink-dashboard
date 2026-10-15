# Simulation mode setup

Set `STARLINK_MODE=simulation` in `.env` and run
`./scripts/compose.sh up -d starlink-location`. No dish is required.

Without an active route, bundled `config.yaml` defines a circular route starting
at latitude 70.0, longitude 179.95 with 100 km radius. Position configuration
uses 450–550 knots and 100–10,000 meters altitude. These are synthetic values,
not live measurements. Uploaded active routes and paced mission replay change
the movement behavior; see [paced replay](../simulation-mode.md).

To change ordinary simulation settings, use actual top-level and nested fields
from `backend/starlink-location/config.yaml`, for example:

```dotenv
STARLINK_UPDATE_INTERVAL_SECONDS=2.0
STARLINK_ROUTE_LATITUDE_START=51.5074
STARLINK_ROUTE_LONGITUDE_START=-0.1278
STARLINK_POSITION_SPEED_MIN_KNOTS=450
STARLINK_POSITION_SPEED_MAX_KNOTS=500
```

Recreate the backend after `.env` changes. Source YAML edits need an image
rebuild. There is no `simulation:` YAML section or `position_smoothing` field.
Keep minimum/maximum pairs valid. Verify with `/health`, `/api/status`, and
`/metrics`; do not compare against hard-coded sample coordinates.
