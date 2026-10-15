# Route Timing Troubleshooting

This guide covers common issues when working with the route timing feature and
how to resolve them.

## Timing Data Not Detected

**Symptoms:**

- Route uploaded successfully but `has_timing_data: false`

**Solutions:**

1. Verify timing format: `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
2. Check timezone: Must end with `Z` (UTC)
3. Place the timing marker in a waypoint Placemark description
4. Check regex pattern matches your format

**Test extraction:**

```bash
# Check if timing was detected in route
curl http://localhost:8000/api/routes/ROUTE_ID | jq '.has_timing_data'
```

## ETA Calculations Returning Zeros

**Symptoms:**

- `eta_seconds: 0` or `distance_meters: 0`

**Solutions:**

1. Verify route is activated: `GET /api/routes/active`
2. Check current position is valid
3. Verify waypoint indices are within route bounds
4. Check if route has timing data for that segment

## Simulator Not Respecting Timing Speeds

**Symptoms:**

- Simulator moving at different speeds than expected

**Solutions:**

1. Verify route has timing data: `GET /api/routes/active/timing`
2. Check that route is activated (not just loaded)
3. Distinguish paced simulation replay from live telemetry timing. Check the
   selected mode and the mission clock before comparing UTC arrivals.
4. If a rebuild is required, follow the
   [development workflow](../development/workflow.md) using an isolated task
   Compose project. Do not stop shared services.

## High ETA Calculation Times

**Symptoms:**

- Dashboard queries slow, timeouts in API

**Solutions:**

1. Check cache hit rate: `GET /api/routes/metrics/eta-cache`
2. Clean expired cache: `POST /api/routes/cache/cleanup`
3. For high-volume queries, enable caching (default 5-second TTL)
