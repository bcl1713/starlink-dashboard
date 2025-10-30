# Task List: Mode Control and Data Retention Improvements

Generated from: `0009-prd-mode-control-retention-improvements.md`

## Relevant Files

- `backend/starlink-location/main.py` - Application startup logic with automatic fallback code (lines 66-79) that needs to be removed
- `backend/starlink-location/app/live/coordinator.py` - LiveCoordinator class that currently raises exceptions on connection failure (line 60)
- `backend/starlink-location/app/live/client.py` - StarlinkClient that immediately connects in `__init__` (line 71)
- `backend/starlink-location/app/api/health.py` - Health endpoint that needs `dish_connected` field added
- `backend/starlink-location/app/core/config.py` - Configuration validation and loading (handles STARLINK_MODE and SIMULATION_MODE)
- `backend/starlink-location/app/models/config.py` - SimulationConfig model definition
- `docker-compose.yml` - Prometheus service configuration for retention settings (line 46)
- `.env.example` - Environment variable documentation template
- `CLAUDE.md` - Project documentation with mode behavior descriptions
- `backend/starlink-location/tests/unit/test_live_coordinator.py` - Unit tests for LiveCoordinator connection handling
- `backend/starlink-location/tests/integration/test_health.py` - Integration tests for health endpoint

### Notes

- Use `pytest backend/starlink-location/tests/` to run all tests
- Use `pytest backend/starlink-location/tests/unit/test_live_coordinator.py` to run specific unit tests
- The backend uses FastAPI framework with Python asyncio
- Tests use pytest with mocking via unittest.mock
- All configuration changes should maintain backward compatibility with `SIMULATION_MODE` environment variable

## Tasks

- [x] 1.0 Remove automatic fallback behavior from live mode to simulation mode
  - [x] 1.1 Open `backend/starlink-location/main.py` and locate the startup_event() function (around line 34)
  - [x] 1.2 Find the code block at lines 57-79 that handles live mode initialization with try/except fallback
  - [x] 1.3 Remove the entire try/except block (lines 60-79) and replace with simple initialization that doesn't catch exceptions
  - [x] 1.4 Update the code to initialize LiveCoordinator directly without fallback: `_coordinator = LiveCoordinator(_simulation_config)`
  - [x] 1.5 Keep the success logging (lines 62, 64) but remove all fallback logging (lines 67-79)
  - [x] 1.6 Ensure `set_service_info(version="0.2.0", mode="live")` is called after successful initialization
  - [x] 1.7 Save the file and verify syntax with `python -m py_compile backend/starlink-location/main.py`

- [x] 2.0 Implement graceful connection handling in LiveCoordinator
  - [x] 2.1 Open `backend/starlink-location/app/live/client.py` and find the StarlinkClient `__init__` method (around line 40)
  - [x] 2.2 Comment out or remove the immediate `self.connect()` call at line 71 (we'll make connection optional)
  - [x] 2.3 Add a new optional parameter `connect_immediately: bool = False` to the `__init__` signature at line 40
  - [x] 2.4 Add conditional connection logic: `if connect_immediately: self.connect()` at the end of `__init__`
  - [x] 2.5 Update the `connect()` method (line 81) to return False instead of raising exceptions on failure
  - [x] 2.6 Wrap the raise statement at line 107 in an if statement: only raise if `connect_immediately` was True, otherwise just return False
  - [x] 2.7 Open `backend/starlink-location/app/live/coordinator.py` and find the LiveCoordinator `__init__` method (around line 23)
  - [x] 2.8 Modify line 40 to pass `connect_immediately=False`: `self.client = StarlinkClient(connect_immediately=False)`
  - [x] 2.9 Replace lines 58-61 (initial telemetry collection that raises exceptions) with a try/except block
  - [x] 2.10 In the try block, attempt to connect: `if self.client.connect(): self._last_valid_telemetry = self._collect_telemetry()`
  - [x] 2.11 In the except block, log a warning (not error) and set `self._last_valid_telemetry = None`
  - [x] 2.12 Add a new method `is_connected()` to LiveCoordinator that returns `self.client.is_connected()` if client exists
  - [x] 2.13 Store the connection status as an instance variable `self._connection_status: bool` and update it during initialization and updates
  - [x] 2.14 Save both files and verify syntax with `python -m py_compile backend/starlink-location/app/live/client.py backend/starlink-location/app/live/coordinator.py`

- [x] 3.0 Enhance health endpoint with connection status reporting
  - [x] 3.1 Open `backend/starlink-location/app/api/health.py` and locate the `health()` endpoint function (around line 43)
  - [x] 3.2 After line 118 where `actual_mode` is determined, add a check: `if actual_mode == "live":`
  - [x] 3.3 Inside the if block, call `dish_connected = _coordinator.is_connected()` to get connection status
  - [x] 3.4 Create a descriptive message based on connection status:
    - If connected: `message = "Live mode: connected to dish"`
    - If not connected: `message = "Live mode: waiting for dish connection"`
  - [x] 3.5 Update the response dictionary at line 121 to include two new fields:
    - Add `"dish_connected": dish_connected` (only for live mode)
    - Add `"message": message` (for all modes, but especially important for live)
  - [x] 3.6 For simulation mode, set `message = "Simulation mode: generating test data"`
  - [x] 3.7 Ensure the response structure matches the PRD example (see PRD lines 202-222)
  - [x] 3.8 Save the file and verify syntax with `python -m py_compile backend/starlink-location/app/api/health.py`

- [x] 4.0 Update Prometheus configuration for 1-year retention
  - [x] 4.1 Open `docker-compose.yml` and locate the prometheus service configuration (around line 34)
  - [x] 4.2 Find the command section at line 44 that includes the retention time flag
  - [x] 4.3 Verify that line 46 already uses the environment variable: `'--storage.tsdb.retention.time=${PROMETHEUS_RETENTION}'`
  - [x] 4.4 No changes needed to docker-compose.yml (it already supports configurable retention via env var)
  - [x] 4.5 Open `.env.example` and locate the PROMETHEUS_RETENTION setting (around line 28)
  - [x] 4.6 Change the default value from `15d` to `1y`
  - [x] 4.7 Add a detailed comment above the setting explaining storage implications (will be calculated in next task)
  - [x] 4.8 Add a note that says "Storage estimation: see calculation in CLAUDE.md"
  - [x] 4.9 Update the inline comment to show example: `# Valid units: y, w, d, h, m, s (e.g., 1y, 15d, 7d)`
  - [x] 4.10 Save `.env.example`

- [x] 5.0 Calculate storage requirements and update documentation
  - [x] 5.1 Start the backend service locally: `cd backend/starlink-location && docker compose up -d starlink-location`
  - [x] 5.2 Wait for startup (about 5 seconds), then fetch the metrics endpoint: `curl -s http://localhost:8000/metrics > /tmp/metrics.txt`
  - [x] 5.3 Count the number of unique metric names: `grep "^starlink_" /tmp/metrics.txt | grep -v "^#" | cut -d'{' -f1 | cut -d' ' -f1 | sort -u | wc -l`
  - [x] 5.4 Record the metric count (let's call it N)
  - [x] 5.5 Calculate storage: `Storage_GB = (N × 31,536,000 seconds × 1.5 bytes × 1.2 overhead) / 1,073,741,824`
  - [x] 5.6 Open `CLAUDE.md` and find the "Configuration" section with PROMETHEUS_RETENTION (around line 19)
  - [x] 5.7 Update the comment for PROMETHEUS_RETENTION to include the calculated storage estimate
  - [x] 5.8 Add a new section after the configuration block titled "## Storage Requirements"
  - [x] 5.9 Document the calculation in this new section:
    - Number of metrics: N (counted from /metrics endpoint)
    - Scrape interval: 1 second
    - Retention period: 1 year (31,536,000 seconds)
    - Estimated storage per metric: ~47 MB (with compression)
    - Total estimated storage: ~X GB (N × 47 MB × 1.2 overhead)
  - [x] 5.10 Find the "Automatic Fallback" section in CLAUDE.md (search for "Automatic Fallback")
  - [x] 5.11 Replace the entire "Automatic Fallback" section with the new text from PRD (see PRD lines 253-264)
  - [x] 5.12 Update the "Operating Modes" section to remove any references to automatic fallback
  - [x] 5.13 In the "Live Mode" subsection, add a note about the new behavior: "If the dish is unavailable, the service starts successfully but serves empty metrics"
  - [x] 5.14 Open `.env.example` and update the PROMETHEUS_RETENTION comment with the calculated storage value
  - [x] 5.15 Add the storage calculation formula to the comment for reference
  - [x] 5.16 Update the STARLINK_MODE comments to emphasize no automatic fallback occurs
  - [x] 5.17 Add a deprecation notice to the SIMULATION_MODE comment: "# DEPRECATED: Use STARLINK_MODE instead (backward compatible)"
  - [x] 5.18 Save both files

- [x] 6.0 Update tests to reflect new behavior
  - [x] 6.1 Open `backend/starlink-location/tests/unit/test_live_coordinator.py`
  - [x] 6.2 Find the test that expects connection failure to raise exceptions (around line 79: "Should raise to trigger fallback")
  - [x] 6.3 Update this test to expect graceful initialization instead of exception
  - [x] 6.4 Rename the test to `test_initialization_without_dish_connection_succeeds`
  - [x] 6.5 Modify the test to verify that LiveCoordinator initializes successfully even when client.connect() fails
  - [x] 6.6 Add assertion to check `coordinator.is_connected() == False` after initialization with failed connection
  - [x] 6.7 Add a new test `test_update_returns_empty_metrics_when_disconnected` to verify empty metric behavior
  - [x] 6.8 In the new test, mock the client to be disconnected and verify update() returns TelemetryData with null/zero values
  - [x] 6.9 Update the test at line 179 `test_update_fails_without_fallback` to expect empty metrics instead of exception
  - [x] 6.10 Open `backend/starlink-location/tests/integration/test_health.py`
  - [x] 6.11 Add a new test `test_health_endpoint_with_live_mode_disconnected` that mocks LiveCoordinator with is_connected() returning False
  - [x] 6.12 In this test, verify the response includes `dish_connected: false` and appropriate message
  - [x] 6.13 Add another test `test_health_endpoint_with_live_mode_connected` that mocks is_connected() returning True
  - [x] 6.14 Verify this response includes `dish_connected: true` and success message
  - [x] 6.15 Run unit tests: `pytest backend/starlink-location/tests/unit/test_live_coordinator.py -v`
  - [x] 6.16 Run integration tests: `pytest backend/starlink-location/tests/integration/test_health.py -v`
  - [x] 6.17 Fix any failing tests by adjusting mock expectations or test logic
  - [x] 6.18 Run full test suite: `pytest backend/starlink-location/tests/ -v` and ensure all tests pass
