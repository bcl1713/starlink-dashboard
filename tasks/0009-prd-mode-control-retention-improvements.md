# PRD: Mode Control and Data Retention Improvements

## Introduction/Overview

Currently, the Starlink dashboard system automatically falls back to simulation
mode when it cannot connect to a live Starlink dish (main.py:66-79). This
behavior is problematic when users want to review historical data without
generating new simulated data that pollutes the metrics. Additionally, the
current 15-day Prometheus retention period is insufficient for long-term
analysis.

This feature will:

1. Remove automatic failover from live mode to simulation mode
2. Enforce explicit mode selection (live or simulation) via configuration
3. Define clear behavior when live mode cannot connect to hardware (start
   successfully but serve empty/null metrics)
4. Extend Prometheus data retention to 1 year with full-resolution storage
5. Provide storage estimation for the increased retention period

**Goal:** Enable users to confidently review historical data without risk of
simulation data contamination, and support long-term metric analysis through
extended data retention.

## Goals

1. Eliminate automatic mode switching behavior to prevent data contamination
2. Provide explicit, predictable mode control through configuration
3. Allow dashboard access for historical review without triggering data
   generation in live mode when hardware is unavailable
4. Extend metric retention to 1 year for long-term analysis
5. Maintain backward compatibility with existing `.env` configuration approach
6. Preserve existing Prometheus data when extending retention period

## User Stories

1. **As a boat operator**, I want to review my Starlink performance from
   previous voyages without simulation data appearing in my metrics, so that I
   can accurately analyze real-world performance.

2. **As a developer**, I want to clearly see when the system is in live mode but
   disconnected versus running in simulation mode, so that I can diagnose issues
   quickly without confusion.

3. **As a system administrator**, I want to know the storage requirements for
   1-year retention before deploying, so that I can provision appropriate disk
   space.

4. **As a data analyst**, I want access to a full year of metrics at 1-second
   resolution, so that I can perform seasonal or long-term trend analysis.

5. **As a user**, I want the system to start successfully in live mode even when
   the dish is temporarily unavailable, so that I can review historical data in
   Grafana without new simulated data being generated.

## Functional Requirements

### Mode Control

1. The system MUST support two explicit operating modes set via the
   `STARLINK_MODE` environment variable: `live` and `simulation`.

2. When `STARLINK_MODE=live`:
   - The backend MUST attempt to connect to the Starlink dish on startup
   - If connection fails, the backend MUST start successfully anyway (no
     fallback to simulation)
   - The backend MUST serve empty/null metrics when not connected (HTTP 200 with
     null values)
   - The backend MUST NOT automatically switch to simulation mode under any
     circumstances
   - The backend SHOULD log clear error messages indicating connection failure
   - The `/health` endpoint MUST report `mode: "live"` and indicate connection
     status (connected: true/false)

3. When `STARLINK_MODE=simulation`:
   - The backend MUST start the simulation data generator immediately on startup
   - The backend MUST serve simulated metrics continuously
   - The `/health` endpoint MUST report `mode: "simulation"`
   - The existing Grafana simulation mode banner MUST continue to display (no
     changes required)

4. When `STARLINK_MODE` is not set or is invalid:
   - The system MUST fail to start with a clear error message
   - The error message MUST explain valid options: `live` or `simulation`

5. The `SIMULATION_MODE` environment variable (backward compatibility):
   - If `STARLINK_MODE` is set, it MUST take precedence over `SIMULATION_MODE`
   - If only `SIMULATION_MODE` is set: `true` maps to `simulation`, `false` maps
     to `live`
   - A deprecation warning SHOULD be logged when `SIMULATION_MODE` is used
     without `STARLINK_MODE`

6. Mode switching MUST require a service restart (no dynamic switching support).

7. The automatic fallback code in main.py:66-79 MUST be removed entirely.

### Live Mode Connection Handling

8. When in live mode with no dish connection at startup:
   - The system MUST start successfully (do not crash or exit)
   - All metric endpoints MUST return HTTP 200 status codes
   - All metric values MUST be null, zero, or marked as unavailable in Prometheus
     format
   - Prometheus metrics MUST NOT be populated with simulated or default values
   - The system MUST log the connection failure clearly

9. Live mode connection retry strategy:
   - The system MUST attempt to connect to the dish once at startup
   - If connection fails, no automatic retry attempts are required
   - The system MAY implement periodic reconnection attempts in a future
     enhancement, but this is NOT required for this PRD

10. When connection is established in live mode (if implementing optional retry):
    - The system MUST begin populating metrics immediately
    - A log message MUST indicate successful connection
    - The `/health` endpoint MUST update to reflect active connection status

11. If connection is lost after being established in live mode (if implementing
    optional retry):
    - The system MUST log the disconnection
    - The system MUST revert to serving empty/null metrics
    - The system MAY attempt to reconnect automatically

### Prometheus Retention

12. Prometheus data retention MUST be configurable via the
    `PROMETHEUS_RETENTION` environment variable.

13. The system MUST support a retention period of `1y` (1 year) when configured.

14. All metrics MUST be stored at full 1-second resolution for the entire
    retention period (no downsampling).

15. Changing retention from 15d to 1y MUST preserve all existing data
    automatically (Prometheus handles this natively).

16. The PRD implementation MUST include a storage estimation calculation based
    on:
    - Number of metrics currently exposed by the backend
    - 1-second scrape interval
    - 1-year retention period (31,536,000 seconds)
    - Prometheus storage overhead and compression

17. The `.env.example` file MUST be updated to show `PROMETHEUS_RETENTION=1y` as
    the recommended default, with a comment explaining estimated storage
    requirements.

### Documentation Updates

18. `CLAUDE.md` MUST be updated to:
    - Remove all references to automatic failover behavior
    - Document the new explicit mode control requirement
    - Explain live mode behavior when dish is unavailable (starts successfully,
      serves empty metrics)
    - Update Prometheus retention information to reflect 1-year default
    - Include storage size estimates for 1-year retention
    - Update the "Automatic Fallback" section to explain the new behavior

19. `.env.example` MUST be updated to:
    - Show explicit `STARLINK_MODE` configuration as required
    - Include comments about live mode connection behavior
    - Show `PROMETHEUS_RETENTION=1y` as the default
    - Include storage size estimate in comments
    - Mark `SIMULATION_MODE` as deprecated (but still supported)

20. Health check endpoint documentation MUST be updated to reflect the new
    `dish_connected` field in live mode.

## Non-Goals (Out of Scope)

1. **Dynamic mode switching:** Users will not be able to switch between live and
   simulation modes without restarting the service.

2. **Grafana UI changes:** No changes to the Grafana simulation mode banner or
   dashboard indicators are required (existing banner is sufficient).

3. **Data downsampling:** No automatic downsampling or tiered retention is
   included (all data kept at 1-second resolution).

4. **Sophisticated retry logic:** Complex exponential backoff or configurable
   retry intervals are not required. Connection is attempted once at startup.

5. **Historical data migration:** No special migration process is needed
   (changing retention period automatically preserves existing data).

6. **Multi-dish support:** Live mode will continue to support only a single
   Starlink dish connection.

7. **Prometheus alerting:** Alert rules for live mode disconnection scenarios
   are deferred to a future enhancement.

8. **Mock gRPC testing:** Connection state testing should align with existing
   test patterns in the project (unit and integration tests already exist).

## Design Considerations

### Health Endpoint Response

The `/health` endpoint should be enhanced to provide connection status
information in live mode:

```json
{
  "status": "healthy",
  "mode": "live",
  "mode_description": "Real Starlink terminal data",
  "dish_connected": false,
  "message": "Live mode: waiting for dish connection"
}
```

When connected:

```json
{
  "status": "healthy",
  "mode": "live",
  "mode_description": "Real Starlink terminal data",
  "dish_connected": true,
  "message": "Live mode: connected to dish"
}
```

### Configuration File Updates

`.env.example` should be updated to include:

```bash
# Operating mode (REQUIRED): 'live' or 'simulation'
# - live: Connect to real Starlink terminal, serve empty metrics if unavailable
#         (no automatic fallback to simulation)
# - simulation: Generate realistic test data automatically
STARLINK_MODE=simulation

# Deprecated: Use STARLINK_MODE instead
# SIMULATION_MODE=true

# Prometheus data retention
# Examples: 15d (15 days), 1y (1 year)
# Note: 1-year retention at 1-second intervals requires approximately XXX GB storage
# (Calculation: ~XX metrics × 31.5M seconds × ~1.5 bytes/sample + overhead)
PROMETHEUS_RETENTION=1y

# Starlink dish network configuration (for live mode)
STARLINK_DISH_HOST=192.168.100.1
STARLINK_DISH_PORT=9200
```

### CLAUDE.md Updates

The "Automatic Fallback" section in CLAUDE.md should be replaced with:

```markdown
**No Automatic Failback:** If the system is configured for live mode but cannot
connect to the dish on startup, it will NOT automatically switch to simulation
mode. Instead, it will:

- Start successfully and remain in live mode
- Serve empty/null metrics until connection is established
- Log connection errors clearly
- Allow Grafana to display historical data without generating new simulated data

This ensures simulation data never pollutes live data collection.
```

## Technical Considerations

### Backend Changes

1. **Startup Logic (main.py):** Remove the try/except fallback block at
   main.py:66-79 that switches to simulation mode on connection failure.

2. **LiveCoordinator:** Modify to handle connection failure gracefully without
   raising exceptions that trigger fallback.

3. **Metric Serving:** Ensure metric endpoints return valid Prometheus format
   with null/zero values when in disconnected live mode.

4. **Health Endpoint:** Add `dish_connected` boolean field to `/health` response
   when in live mode.

### Prometheus Configuration

1. **Retention Settings:** Update Prometheus startup configuration to read from
   `PROMETHEUS_RETENTION` environment variable (default to `1y`).

2. **Storage Volume:** Ensure the Docker volume for Prometheus data is not
   constrained by size limits in docker-compose.yml.

### Storage Estimation

The implementation should calculate and document expected storage requirements:

1. Count current metrics exposed at `/metrics` endpoint
2. Calculate: `metric_count × 31,536,000 seconds × 1.5 bytes (avg with
   compression) + 20% overhead`
3. Document this calculation in CLAUDE.md and .env.example

**Estimated storage (to be calculated during implementation):**

- Metrics count: ~XX (needs to be determined)
- Storage per metric per year: ~47 MB (31.5M seconds × 1.5 bytes)
- Total estimated: (metric_count × 47 MB × 1.2 overhead factor)

## Success Metrics

1. **No Unintended Mode Switches:** Zero instances of the system automatically
   switching from live to simulation mode after this change.

2. **Clear Status Reporting:** Health endpoint accurately reports mode and
   connection status 100% of the time.

3. **Data Integrity:** No simulated data appears in Prometheus when reviewing
   historical metrics in live mode with no active connection.

4. **Storage Accuracy:** Actual Prometheus storage usage for 1-year retention
   matches estimates within ±20%.

5. **Documentation Clarity:** Users can configure mode and retention without
   referring to external resources (measured by lack of related support
   questions).

6. **Backward Compatibility:** Existing configurations using `SIMULATION_MODE`
   continue to work correctly with deprecation warnings.

## Testing Requirements

Testing should align with existing patterns in the project. Based on the test
files found:

1. **Unit Tests:**
   - Update `test_live_coordinator.py` to verify graceful connection failure
     (serve null metrics instead of raising exceptions)
   - Add tests for health endpoint with `dish_connected` field
   - Test configuration validation for `STARLINK_MODE` values

2. **Integration Tests:**
   - Update `test_health.py` to verify live mode health response with
     connection status
   - Verify metrics endpoint returns valid Prometheus format with null values in
     disconnected live mode
   - Test backward compatibility of `SIMULATION_MODE` environment variable

3. **Manual Testing:**
   - Verify system starts successfully in live mode without dish connection
   - Verify Grafana can display historical data in disconnected live mode
     without new data appearing
   - Verify storage estimation matches actual usage after 1 week of operation

## Open Questions

**RESOLVED:**

1. ~~Retry strategy~~ - Connection attempted once at startup only, no automatic
   retries
2. ~~Prometheus alerting~~ - Deferred to future enhancement
3. ~~Data migration~~ - No migration needed, Prometheus preserves data
   automatically
4. ~~Testing approach~~ - Follow existing test patterns (unit + integration)

**REMAINING:**

1. **Storage Estimation:** The exact number of metrics needs to be counted from
   the `/metrics` endpoint to calculate precise storage requirements. Should
   this be done manually or automated as part of implementation?

---

**Document Version:** 1.0
**Created:** 2025-10-28
**Next Steps:** Approve PRD and proceed with implementation
