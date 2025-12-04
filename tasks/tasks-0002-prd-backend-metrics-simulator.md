# Tasks: Backend Metrics Exporter and Simulator

Based on PRD-0002: Backend Metrics Exporter and Simulator

## Relevant Files

### Application Code

- `backend/starlink-location/main.py` - FastAPI application entry point
  (refactored from app.py)
- `backend/starlink-location/config.yaml` - Default YAML configuration file
- `backend/starlink-location/requirements.txt` - Python dependencies (update
  existing)

### Core Utilities

- `backend/starlink-location/app/__init__.py` - App package initialization
- `backend/starlink-location/app/core/__init__.py` - Core utilities package
- `backend/starlink-location/app/core/config.py` - Configuration loader and
  validator
- `backend/starlink-location/app/core/logging.py` - Structured logging setup
- `backend/starlink-location/app/core/metrics.py` - Prometheus metrics registry
  and definitions

### Data Models

- `backend/starlink-location/app/models/__init__.py` - Models package
- `backend/starlink-location/app/models/telemetry.py` - Pydantic telemetry data
  models
- `backend/starlink-location/app/models/config.py` - Pydantic configuration
  models

### API Endpoints

- `backend/starlink-location/app/api/__init__.py` - API package
- `backend/starlink-location/app/api/health.py` - Health check endpoint handler
- `backend/starlink-location/app/api/metrics.py` - Prometheus metrics endpoint
  handler
- `backend/starlink-location/app/api/status.py` - JSON status endpoint handler
- `backend/starlink-location/app/api/config.py` - Configuration management
  endpoint handler

### Simulation Engine

- `backend/starlink-location/app/simulation/__init__.py` - Simulation package
- `backend/starlink-location/app/simulation/route.py` - Synthetic route
  generator
- `backend/starlink-location/app/simulation/position.py` - Position simulator
  (lat/lon/alt/speed/heading)
- `backend/starlink-location/app/simulation/network.py` - Network metrics
  simulator (latency/throughput/packet loss)
- `backend/starlink-location/app/simulation/obstructions.py` - Obstruction
  simulator
- `backend/starlink-location/app/simulation/coordinator.py` - Simulation
  orchestration and background updates

### Tests

- `backend/starlink-location/pytest.ini` - Pytest configuration
- `backend/starlink-location/tests/__init__.py` - Tests package
- `backend/starlink-location/tests/conftest.py` - Shared test fixtures
- `backend/starlink-location/tests/unit/__init__.py` - Unit tests package
- `backend/starlink-location/tests/unit/test_config.py` - Configuration tests
- `backend/starlink-location/tests/unit/test_route.py` - Route generator tests
- `backend/starlink-location/tests/unit/test_position.py` - Position simulator
  tests
- `backend/starlink-location/tests/unit/test_network.py` - Network simulator
  tests
- `backend/starlink-location/tests/unit/test_obstructions.py` - Obstruction
  simulator tests
- `backend/starlink-location/tests/unit/test_metrics.py` - Metrics formatting
  tests
- `backend/starlink-location/tests/integration/__init__.py` - Integration tests
  package
- `backend/starlink-location/tests/integration/test_health.py` - Health endpoint
  tests
- `backend/starlink-location/tests/integration/test_metrics_endpoint.py` -
  Metrics endpoint tests
- `backend/starlink-location/tests/integration/test_status.py` - Status endpoint
  tests
- `backend/starlink-location/tests/integration/test_config_api.py` - Config API
  tests
- `backend/starlink-location/tests/integration/test_simulation_e2e.py` -
  End-to-end simulation tests

### Docker & Configuration

- `backend/starlink-location/Dockerfile` - Update to copy new project structure
- `monitoring/prometheus/prometheus.yml` - Update scrape interval to 1 second
- `.env` - Add any new environment variables (if needed)

### Notes

- Tests are organized into `unit/` and `integration/` directories under `tests/`
- Use `pytest` to run tests: `pytest tests/` (runs all) or `pytest tests/unit/`
  (unit only)
- Use `pytest --cov=app --cov-report=html` to generate coverage reports
- Integration tests will use FastAPI's `TestClient` for endpoint testing
- All async code should be tested with `pytest-asyncio`

## Tasks

- [x] 1.0 Set up project structure and dependencies
  - [x] 1.1 Create directory structure (app/, app/api/, app/simulation/,
        app/models/, app/core/, tests/unit/, tests/integration/)
  - [x] 1.2 Create `__init__.py` files for all Python packages
  - [x] 1.3 Update `requirements.txt` with new dependencies (pydantic, PyYAML,
        pytest, pytest-asyncio, numpy, httpx)
  - [x] 1.4 Rename `app.py` to `main.py` and prepare for modular refactoring
  - [x] 1.5 Create `pytest.ini` configuration file

- [x] 2.0 Implement configuration management system
  - [x] 2.1 Create Pydantic configuration models in `app/models/config.py`
        (SimulationConfig, RouteConfig, NetworkConfig, etc.)
  - [x] 2.2 Implement YAML config loader with validation in `app/core/config.py`
  - [x] 2.3 Create default `config.yaml` with sensible defaults for all
        simulation parameters
  - [x] 2.4 Add environment variable override support using Pydantic settings
  - [x] 2.5 Implement configuration validation with clear error messages for
        invalid values

- [x] 3.0 Build simulation engine for telemetry generation
  - [x] 3.1 Create Pydantic telemetry data models in `app/models/telemetry.py`
        (TelemetryData, PositionData, NetworkData, etc.)
  - [x] 3.2 Implement synthetic route generator in `app/simulation/route.py`
        (support at least one pattern: circular or straight line)
  - [x] 3.3 Implement position simulator in `app/simulation/position.py` with
        realistic movement, speed (knots), and heading calculations
  - [x] 3.4 Implement network metrics simulator in `app/simulation/network.py`
        with realistic latency (20-80ms typical, spikes to 200ms+), throughput
        (50-200 Mbps down, 10-40 Mbps up), and packet loss (0-5%)
  - [x] 3.5 Implement obstruction simulator in `app/simulation/obstructions.py`
        with time-based variation and correlation to network degradation
  - [x] 3.6 Add environmental factors to telemetry (signal quality, uptime
        tracking)
  - [x] 3.7 Create simulation coordinator in `app/simulation/coordinator.py` to
        orchestrate all simulators and manage state

- [x] 4.0 Implement API endpoints and Prometheus metrics exporter
  - [x] 4.1 Define all Prometheus gauge metrics in `app/core/metrics.py`
        (position, network, status, obstructions per PRD FR-2.2)
  - [x] 4.2 Implement `/health` endpoint in `app/api/health.py` with status,
        uptime, and mode information
  - [x] 4.3 Implement `/metrics` endpoint in `app/api/metrics.py` returning
        Prometheus-formatted metrics with correct Content-Type
  - [x] 4.4 Implement `/api/status` endpoint in `app/api/status.py` returning
        JSON telemetry with human-readable fields and ISO 8601 timestamp
  - [x] 4.5 Implement `/api/config` endpoint in `app/api/config.py` with GET
        (retrieve config) and POST/PUT (update config) support
  - [x] 4.6 Create FastAPI app in `main.py`, register all API routers, and
        configure CORS if needed
  - [x] 4.7 Add OpenAPI/Swagger documentation with descriptions for all
        endpoints (FastAPI auto-generates this)

- [x] 5.0 Add logging, error handling, and background task management
  - [x] 5.1 Implement structured logging system in `app/core/logging.py` with
        JSON format and configurable log levels
  - [x] 5.2 Add FastAPI exception handlers in `main.py` for consistent error
        responses (400, 500 with JSON error messages)
  - [x] 5.3 Implement graceful degradation in simulation coordinator (use last
        known good values on errors)
  - [x] 5.4 Create background task in `main.py` that updates simulation and
        Prometheus metrics every 1 second
  - [x] 5.5 Add FastAPI startup event handler to initialize simulator and
        shutdown handler for cleanup

- [x] 6.0 Write comprehensive test suite (unit and integration tests)
  - [x] 6.1 Set up pytest configuration in `pytest.ini` and create test fixtures
        in `tests/conftest.py`
  - [x] 6.2 Write unit tests for configuration loading, validation, and YAML
        parsing in `tests/unit/test_config.py`
  - [x] 6.3 Write unit tests for route generator in `tests/unit/test_route.py`
  - [x] 6.4 Write unit tests for position simulator in
        `tests/unit/test_position.py` (verify realistic values, speed/heading
        calculations)
  - [x] 6.5 Write unit tests for network simulator in
        `tests/unit/test_network.py` (verify ranges, occasional spikes)
  - [x] 6.6 Write unit tests for obstruction simulator in
        `tests/unit/test_obstructions.py` (verify correlation with network
        performance)
  - [x] 6.7 Write unit tests for Prometheus metrics formatting in
        `tests/unit/test_metrics.py`
  - [x] 6.8 Write integration test for `/health` endpoint in
        `tests/integration/test_health.py`
  - [x] 6.9 Write integration test for `/metrics` endpoint in
        `tests/integration/test_metrics_endpoint.py` with Prometheus format
        validation
  - [x] 6.10 Write integration test for `/api/status` endpoint in
        `tests/integration/test_status.py`
  - [x] 6.11 Write integration test for `/api/config` endpoint (GET/POST) in
        `tests/integration/test_config_api.py`
  - [x] 6.12 Write end-to-end simulation test in
        `tests/integration/test_simulation_e2e.py` to verify metrics update over
        time
  - [x] 6.13 Run `pytest --cov=app --cov-report=html` and verify >80% coverage
        for core simulation logic

- [x] 7.0 Update Docker configuration and validate end-to-end integration
  - [x] 7.1 Update `Dockerfile` to copy new project structure (main.py, app/,
        config.yaml)
  - [x] 7.2 Update `monitoring/prometheus/prometheus.yml` to set scrape_interval
        to 1s for starlink-location job
  - [x] 7.3 Ensure `config.yaml` is included in Docker image or mounted as
        volume
  - [x] 7.4 Test service startup with `docker compose build --no-cache` and
        `docker compose up -d`
  - [x] 7.5 Verify all API endpoints are accessible:
        `curl <http://localhost:8000/health`,> `/metrics`, `/api/status`,
        `/api/config`
  - [x] 7.6 Verify Prometheus successfully scrapes metrics by checking
        Prometheus UI at <http://localhost:9090>
  - [x] 7.7 Monitor logs with `docker compose logs -f starlink-location` and
        verify no errors during 10-minute test run
  - [x] 7.8 Update project README or CLAUDE.md with any new environment
        variables, configuration options, or usage instructions
