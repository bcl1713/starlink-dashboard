# Task List: Live Starlink Terminal Integration

Generated from: `0006-prd-live-terminal-integration.md`

## Relevant Files

### New Files to Create

- `backend/starlink-location/app/live/__init__.py` - Live mode module initialization ✓ CREATED
- `backend/starlink-location/app/live/client.py` - Starlink gRPC client wrapper ✓ CREATED
- `backend/starlink-location/app/live/coordinator.py` - LiveCoordinator class implementation
- `backend/starlink-location/tests/unit/test_live_coordinator.py` - Unit tests for LiveCoordinator
- `backend/starlink-location/tests/unit/test_starlink_client.py` - Unit tests for Starlink client ✓ CREATED
- `backend/starlink-location/tests/integration/test_live_mode.py` - Integration tests for live mode

### Existing Files to Modify

- `backend/starlink-location/requirements.txt` - Add gRPC and Starlink client dependencies ✓ MODIFIED
- `backend/starlink-location/app/models/config.py` - Add HeadingTrackerConfig model ✓ MODIFIED
- `backend/starlink-location/app/core/config.py` - Load heading tracker configuration ✓ MODIFIED
- `backend/starlink-location/tests/unit/test_config.py` - Unit tests for HeadingTrackerConfig ✓ MODIFIED
- `backend/starlink-location/app/core/metrics.py` - Add mode visibility metric (starlink_mode_info)
- `backend/starlink-location/app/api/health.py` - Include current mode in health endpoint response
- `backend/starlink-location/main.py` - Conditional coordinator instantiation based on mode
- `docker-compose.yml` - Add network configuration for dish access
- `.env` - Document STARLINK_MODE environment variable
- `CLAUDE.md` - Update with live mode instructions and configuration

### Notes

- Unit tests should be placed alongside the code files they are testing
- Use `python -m pytest backend/starlink-location/tests/` to run all tests
- Use `python -m pytest backend/starlink-location/tests/unit/test_live_coordinator.py -v` to run specific test files
- Mock gRPC responses in unit tests to avoid requiring real hardware
- Integration tests can be run with `pytest -m integration` when hardware is available

## Tasks

- [x] 1.0 Add Starlink gRPC client dependencies and integration
  - [x] 1.1 Research starlink-grpc-tools library structure and identify key modules needed
  - [x] 1.2 Add `grpcio>=1.50.0` to requirements.txt
  - [x] 1.3 Add `grpcio-tools>=1.50.0` to requirements.txt for protobuf compilation
  - [x] 1.4 Add starlink-grpc-tools as a dependency (investigate PyPI availability or git installation)
  - [x] 1.5 Test dependency installation in virtual environment: `pip install -r requirements.txt`
  - [x] 1.6 Create `app/live/__init__.py` module
  - [x] 1.7 Create `app/live/client.py` with StarlinkClient class wrapper for gRPC communication
  - [x] 1.8 Implement basic connection test method in StarlinkClient to verify dish reachability
  - [x] 1.9 Write unit tests for StarlinkClient in `tests/unit/test_starlink_client.py` using mocked gRPC responses

- [x] 2.0 Add heading tracker configuration to config models
  - [x] 2.1 Add HeadingTrackerConfig model to `app/models/config.py` with min_distance_meters and max_age_seconds fields
  - [x] 2.2 Add heading_tracker field to SimulationConfig model with HeadingTrackerConfig default
  - [x] 2.3 Update `app/core/config.py` to load heading tracker config from YAML and environment variables
  - [x] 2.4 Write unit tests for HeadingTrackerConfig in existing config test files

- [ ] 3.0 Create LiveCoordinator class for real terminal data collection
  - [ ] 3.1 Create `app/live/coordinator.py` file
  - [ ] 3.2 Define LiveCoordinator class that mirrors SimulationCoordinator interface (same public methods)
  - [ ] 3.3 Add `__init__` method that accepts SimulationConfig and initializes StarlinkClient
  - [ ] 3.4 Initialize HeadingTracker service in LiveCoordinator with configurable parameters from config
  - [ ] 3.5 Implement `update()` method that polls gRPC API and returns TelemetryData
  - [ ] 3.6 Extract GPS position (latitude, longitude, altitude) from Starlink API response
  - [ ] 3.7 Extract network metrics (latency, throughput up/down) from API response
  - [ ] 3.8 Extract obstruction percentage and other status data from API response
  - [ ] 3.9 Call HeadingTracker.update() with GPS position to calculate heading
  - [ ] 3.10 Build and return TelemetryData object with all collected metrics
  - [ ] 3.11 Implement `get_current_telemetry()` method to return last telemetry without updating
  - [ ] 3.12 Implement `reset()` method to reset heading tracker and connection state
  - [ ] 3.13 Implement `get_uptime_seconds()` method tracking time since LiveCoordinator started
  - [ ] 3.14 Add error handling with graceful degradation (return last known good telemetry on transient errors)
  - [ ] 3.15 Write unit tests in `tests/unit/test_live_coordinator.py` using mocked StarlinkClient

- [ ] 4.0 Add mode visibility features (metrics, health endpoint, logging)
  - [ ] 4.1 Create `starlink_mode_info` Gauge metric in `app/core/metrics.py` with mode label
  - [ ] 4.2 Update `set_service_info()` in metrics.py to set starlink_mode_info metric
  - [ ] 4.3 Modify `app/api/health.py` to include current mode in JSON response (e.g., {"status": "healthy", "mode": "live"})
  - [ ] 4.4 Update startup logging in main.py to prominently log active mode with INFO level
  - [ ] 4.5 Add mode change logging at WARNING level for use when fallback occurs
  - [ ] 4.6 Update unit tests to verify mode visibility in health endpoint and metrics

- [ ] 5.0 Implement automatic fallback logic and connection management
  - [ ] 5.1 Add `is_connected()` method to StarlinkClient to check connection health
  - [ ] 5.2 Add `test_connection()` method to StarlinkClient with timeout parameter (default 5 seconds)
  - [ ] 5.3 Implement retry logic in LiveCoordinator that attempts connection for 30 seconds before giving up
  - [ ] 5.4 Add fallback mechanism in main.py: if LiveCoordinator connection fails, instantiate SimulationCoordinator instead
  - [ ] 5.5 Log connection failure at WARNING level with details (error type, timeout, retries attempted)
  - [ ] 5.6 Log fallback event at WARNING level: "Failed to connect to Starlink dish, falling back to simulation mode"
  - [ ] 5.7 Handle mid-operation connection loss in LiveCoordinator: detect gRPC errors and log appropriately
  - [ ] 5.8 For mid-operation failures, return last known good telemetry to avoid metric gaps
  - [ ] 5.9 Add connection state tracking (connected, disconnected, retrying) for observability
  - [ ] 5.10 Write integration tests in `tests/integration/test_live_mode.py` to verify fallback behavior

- [ ] 6.0 Update application startup to conditionally instantiate coordinators
  - [ ] 6.1 Import LiveCoordinator at the top of main.py
  - [ ] 6.2 Modify `startup_event()` in main.py to check config mode before instantiating coordinator
  - [ ] 6.3 Add conditional logic: if mode == "live", attempt to create LiveCoordinator
  - [ ] 6.4 Add conditional logic: if mode == "simulation", create SimulationCoordinator
  - [ ] 6.5 Wrap LiveCoordinator instantiation in try-except to handle connection failures
  - [ ] 6.6 On LiveCoordinator connection failure, log warning and fall back to SimulationCoordinator
  - [ ] 6.7 Update mode logging to reflect actual active mode (not just configured mode)
  - [ ] 6.8 Ensure _coordinator variable works polymorphically with both coordinator types
  - [ ] 6.9 Test startup with STARLINK_MODE=live environment variable
  - [ ] 6.10 Test startup with STARLINK_MODE=simulation environment variable
  - [ ] 6.11 Verify that background update loop works identically with both coordinators

- [ ] 7.0 Configure Docker networking for dish access
  - [ ] 7.1 Research Docker network modes: host vs bridge with extra_hosts
  - [ ] 7.2 Add `network_mode: host` option to starlink-location service in docker-compose.yml (Linux-friendly approach)
  - [ ] 7.3 Alternatively, add `extra_hosts: - "dish.starlink:192.168.100.1"` for cross-platform compatibility
  - [ ] 7.4 Document both networking approaches in comments within docker-compose.yml
  - [ ] 7.5 Update .env file to document STARLINK_MODE variable with description
  - [ ] 7.6 Add STARLINK_DISH_HOST and STARLINK_DISH_PORT environment variables for flexibility (defaults: 192.168.100.1:9200)
  - [ ] 7.7 Update StarlinkClient to use environment variables for host/port configuration
  - [ ] 7.8 Test Docker container connectivity to host network: `docker compose exec starlink-location curl http://192.168.100.1`
  - [ ] 7.9 Update CLAUDE.md with live mode setup instructions and networking requirements
  - [ ] 7.10 Test full stack startup with live mode configuration

## Testing Checklist (for tomorrow's hardware test)

Based on PRD success criteria:

- [ ] **Live position visible on map**: Start system with real dish, verify GPS coordinates appear on Grafana geomap and update in real-time
- [ ] **Real metrics updating**: Confirm latency, throughput, and obstruction metrics show actual dish data (not simulated patterns)
- [ ] **Fallback works**: Disconnect dish network cable, verify system logs fallback warning and continues with simulation
- [ ] **Heading calculation**: Move terminal (e.g., walk with dish), verify heading degrees update correctly in Grafana
