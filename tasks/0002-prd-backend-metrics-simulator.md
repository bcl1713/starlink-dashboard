# PRD-0002: Backend Metrics Exporter and Simulator

## 1. Introduction/Overview

This feature implements the core backend service for the Starlink Dashboard
monitoring system. The backend will serve as a FastAPI-based metrics exporter
that exposes Starlink telemetry data in Prometheus format. It will operate
primarily in simulation mode during development, generating realistic telemetry
data that mimics real Starlink terminal behavior including position tracking,
network performance metrics, obstructions, and environmental factors.

**Problem Statement:** The monitoring system needs a reliable backend that can
provide Starlink telemetry data for visualization in Grafana, with the ability
to develop and test without requiring access to physical Starlink hardware.

**Goal:** Build a production-ready FastAPI backend that exposes comprehensive
Starlink metrics via Prometheus format and provides realistic simulation
capabilities for offline development and testing.

## 2. Goals

1. **Implement FastAPI Backend Service:** Create a containerized Python backend
   that runs reliably in Docker
1. **Expose Prometheus Metrics:** Implement `/metrics` endpoint with full metric
   set as defined in project documentation
1. **Build Comprehensive Simulator:** Generate realistic telemetry data
   including position, network stats, obstructions, and environmental factors
1. **Provide RESTful API:** Expose health, status, and configuration endpoints
   for monitoring and control
1. **Enable High-Frequency Updates:** Update metrics every 1 second for
   real-time dashboard responsiveness
1. **Ensure Testability:** Achieve comprehensive test coverage with both unit
   and integration tests
1. **Support Graceful Operations:** Handle errors without service disruption
   using fallback values

## 3. User Stories

### US-1: Developer Testing Without Hardware

**As a** developer working on dashboard features **I want** the backend to
generate realistic Starlink data in simulation mode **So that** I can develop
and test without access to physical Starlink hardware

**Acceptance Criteria:**

- Simulation mode is enabled by default via configuration
- Generated data matches expected ranges and behaviors of real Starlink
  terminals
- Metrics update every 1 second with realistic variations

### US-2: Prometheus Integration

**As a** DevOps engineer setting up monitoring **I want** the backend to expose
metrics in Prometheus format **So that** Prometheus can scrape and store
telemetry data for visualization

**Acceptance Criteria:**

- `/metrics` endpoint returns valid Prometheus format
- All required metrics are exposed (position, network, status, obstructions)
- Prometheus successfully scrapes metrics without errors

### US-3: Service Health Monitoring

**As a** system administrator **I want** to check the health status of the
backend service **So that** I can ensure the monitoring system is operational

**Acceptance Criteria:**

- `/health` endpoint returns 200 OK when service is healthy
- Health check includes basic system status information
- Endpoint responds within 100ms

### US-4: Runtime Configuration

**As a** developer or operator **I want** to view and modify simulator
configuration at runtime **So that** I can test different scenarios without
restarting the service

**Acceptance Criteria:**

- `/api/config` endpoint returns current simulator settings
- Configuration can be updated via API calls
- Changes take effect immediately without service restart

### US-5: Status Visibility

**As a** developer debugging issues **I want** to access current telemetry data
in JSON format **So that** I can inspect values without querying Prometheus

**Acceptance Criteria:**

- `/api/status` endpoint returns current metrics as JSON
- Response includes all telemetry fields with human-readable labels
- Response time is under 50ms

## 4. Functional Requirements

### FR-1: Service Architecture

1.1. Backend MUST be implemented using FastAPI framework 1.2. Backend MUST run
inside a Docker container 1.3. Service MUST expose HTTP endpoints on port 8000
1.4. Service MUST start automatically when container launches 1.5. Service MUST
use async/await patterns for I/O operations

### FR-2: Prometheus Metrics Endpoint

2.1. Backend MUST expose `/metrics` endpoint following Prometheus exposition
format 2.2. Metrics MUST include all telemetry defined in CLAUDE.md:

- Position: `starlink_dish_latitude_degrees`, `starlink_dish_longitude_degrees`,
  `starlink_dish_altitude_meters`
- Network: `starlink_network_latency_ms`,
  `starlink_network_throughput_down_mbps`, `starlink_network_throughput_up_mbps`
- Status: `starlink_dish_obstruction_percent`, `starlink_dish_speed_knots`,
  `starlink_dish_heading_degrees`
- Additional metrics: uptime, packet loss, signal quality, etc. 2.3. Metrics
  MUST update at 1-second intervals 2.4. Each metric MUST include appropriate
  HELP and TYPE annotations 2.5. Metrics MUST maintain consistent naming
  conventions (snake_case with units)

### FR-3: Simulation Engine

3.1. Simulator MUST generate synthetic route data programmatically (KML support
deferred to future phase) 3.2. Position simulation MUST:

- Update latitude/longitude along a realistic path
- Include altitude changes
- Calculate and expose speed in knots
- Calculate and expose heading in degrees
- Support configurable route parameters (speed, waypoints, etc.) 3.3. Network
  simulation MUST:
- Generate realistic latency values (20-80ms typical, occasional spikes to
  200ms+)
- Generate realistic throughput (50-200 Mbps down, 10-40 Mbps up)
- Include packet loss percentage (0-5% typical)
- Simulate network degradation scenarios 3.4. Obstruction simulation MUST:
- Generate obstruction percentage (0-100%)
- Correlate obstructions with network performance degradation
- Include time-based variation (e.g., trees swaying) 3.5. Environmental
  simulation MUST:
- Include signal quality metrics
- Simulate weather impact on performance (optional)
- Generate realistic uptime values

### FR-4: API Endpoints

4.1. `/health` endpoint MUST:

- Return HTTP 200 when service is operational
- Include JSON response with status, uptime, and mode (simulation/live)
- Respond within 100ms 4.2. `/metrics` endpoint MUST:
- Return Prometheus-formatted metrics
- Set Content-Type to `text/plain; version=0.0.4`
- Include all metrics defined in FR-2.2 4.3. `/api/status` endpoint MUST:
- Return JSON object with current telemetry values
- Include human-readable field names
- Include timestamp in ISO 8601 format
- Respond within 50ms 4.4. `/api/config` endpoint MUST:
- Support GET to retrieve current configuration
- Support POST/PUT to update configuration
- Validate configuration changes before applying
- Return updated configuration after successful changes

### FR-5: Configuration Management

5.1. Backend MUST read configuration from YAML file (e.g., `config.yaml`) 5.2.
Configuration file MUST support:

- Simulation mode toggle (enabled/disabled)
- Metrics update interval (default: 1 second)
- Route parameters (start position, waypoints, speed)
- Network simulation ranges (latency, throughput, packet loss)
- Obstruction simulation parameters 5.3. Configuration MUST be hot-reloadable
  via `/api/config` endpoint 5.4. Invalid configuration MUST be rejected with
  clear error messages 5.5. Backend MUST use sensible defaults if configuration
  file is missing

### FR-6: Error Handling

6.1. Backend MUST implement graceful degradation:

- If simulation fails, use last known good values
- If metrics calculation fails, return default safe values
- Log errors but continue service operation 6.2. API endpoints MUST return
  appropriate HTTP status codes:
- 200 for successful operations
- 400 for bad requests
- 500 for internal server errors 6.3. Error responses MUST include descriptive
  error messages in JSON format 6.4. Backend MUST NOT crash due to simulation
  errors

### FR-7: Logging

7.1. Backend MUST log to stdout/stderr for Docker container compatibility 7.2.
Logs MUST include:

- Service startup/shutdown events
- Configuration changes
- Error conditions with stack traces
- Simulation state changes (if applicable) 7.3. Log level MUST be configurable
  via environment variable (DEBUG, INFO, WARNING, ERROR) 7.4. Logs MUST use
  structured format (JSON recommended) for parsing

### FR-8: Testing

8.1. Backend MUST include unit tests for:

- Simulation engine components (position, network, obstructions)
- Metrics formatting and validation
- Configuration loading and validation
- Error handling logic 8.2. Backend MUST include integration tests for:
- All API endpoints (health, metrics, status, config)
- Prometheus metrics format validation
- End-to-end simulation workflows 8.3. Test coverage MUST exceed 80% for core
  simulation logic 8.4. Tests MUST run in CI/CD pipeline (when implemented) 8.5.
  Tests MUST use pytest framework

## 5. Non-Goals (Out of Scope)

The following items are explicitly **out of scope** for Phase 2:

- **Live Starlink Integration:** Connecting to actual Starlink hardware at
  `192.168.100.1:9200` (deferred to Phase 6)
- **KML File Parsing:** Reading and processing KML route files from
  `/data/sim_routes/` (deferred to future phase)
- **POI/ETA Calculations:** Point-of-interest detection and ETA metrics
  (deferred to Phase 3)
- **KML Recording:** Saving telemetry data to KML format (deferred to Phase 4)
- **Grafana Dashboards:** Dashboard creation and configuration (deferred to
  Phase 5)
- **Authentication/Authorization:** User authentication and access control
- **Database Persistence:** Storing historical data (handled by Prometheus)
- **Web UI:** Any frontend or web interface for the backend
- **Multi-dish Support:** Supporting multiple Starlink terminals simultaneously
- **Advanced Network Simulation:** Detailed TCP/IP stack simulation or specific
  protocol behaviors

## 6. Design Considerations

### API Design

- Use RESTful conventions for API endpoints
- Return JSON responses with consistent structure
- Include appropriate HTTP headers (Content-Type, Cache-Control)
- Follow OpenAPI/Swagger standards (consider auto-generating docs with FastAPI)

### Simulation Realism

- Research typical Starlink performance characteristics to ensure realistic
  ranges
- Implement gradual transitions (avoid sudden jumps in latency or position)
- Consider diurnal patterns (e.g., network congestion at peak hours)
- Add small random variations to prevent obviously synthetic patterns

### Code Organization

```text
backend/
├── starlink-location/
│   ├── main.py              # FastAPI app entry point
│   ├── config.yaml          # Default configuration
│   ├── requirements.txt     # Python dependencies
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/             # API endpoint handlers
│   │   │   ├── health.py
│   │   │   ├── metrics.py
│   │   │   ├── status.py
│   │   │   └── config.py
│   │   ├── simulation/      # Simulation engine
│   │   │   ├── __init__.py
│   │   │   ├── position.py
│   │   │   ├── network.py
│   │   │   ├── obstructions.py
│   │   │   └── route.py
│   │   ├── models/          # Pydantic models
│   │   │   ├── telemetry.py
│   │   │   └── config.py
│   │   └── core/            # Core utilities
│   │       ├── config.py
│   │       ├── logging.py
│   │       └── metrics.py
│   └── tests/
│       ├── unit/
│       └── integration/
```

## 7. Technical Considerations

### Dependencies

- **FastAPI:** Web framework for API endpoints
- **uvicorn:** ASGI server for running FastAPI
- **prometheus-client:** Prometheus metrics library for Python
- **pydantic:** Data validation and settings management
- **pytest:** Testing framework
- **pytest-asyncio:** Async test support
- **PyYAML:** YAML configuration parsing
- **numpy:** For realistic random distributions in simulation (optional)

### Docker Configuration

- Use official Python 3.11+ base image
- Install dependencies via `requirements.txt`
- Expose port 8000
- Mount configuration file as volume or use environment-based config
- Ensure proper signal handling for graceful shutdown
- Use multi-stage build to minimize image size (optional optimization)

### Performance Considerations

- Use async/await for all I/O operations
- Consider caching metrics between requests (1-second TTL)
- Optimize Prometheus metrics export (avoid rebuilding entire response each
  time)
- Profile simulation code to ensure 1-second update interval is achievable
- Consider using background tasks for simulation updates

### Prometheus Integration Notes

- Use `prometheus_client` library's official gauge/counter types
- Register metrics at application startup
- Update metric values in background task (every 1 second)
- Ensure thread-safety if using concurrent workers
- Test metrics endpoint with Prometheus's promtool validator

### Error Handling Strategy

- Use FastAPI's exception handlers for consistent error responses
- Implement retry logic for transient simulation errors
- Log all errors with contextual information (trace IDs, timestamps)
- Provide fallback values for critical metrics (never return empty/null)
- Consider circuit breaker pattern for future live mode integration

## 8. Success Metrics

Phase 2 will be considered **successfully completed** when:

1. **Backend Service Operational:**
   - FastAPI service starts successfully in Docker container
   - All endpoints respond with correct status codes
   - Service runs continuously without crashes for 24+ hours

2. **Metrics Export Verified:**
   - `/metrics` endpoint returns valid Prometheus format (validated by promtool)
   - All required metrics are present and updating
   - Prometheus successfully scrapes metrics every 1 second

3. **Simulation Quality:**
   - Generated telemetry data appears realistic (values within expected ranges)
   - Metrics show smooth transitions and appropriate variations
   - Simulation demonstrates position movement, network changes, and obstruction
     patterns

4. **API Functionality:**
   - All endpoints (health, metrics, status, config) return correct responses
   - Configuration changes take effect immediately
   - API response times meet performance requirements (health: <100ms, status:
     <50ms)

5. **Test Coverage:**
   - Unit tests pass with >80% code coverage
   - Integration tests validate all endpoints
   - Tests run successfully in automated pipeline (pytest)

6. **Documentation Complete:**
   - API endpoints documented (OpenAPI/Swagger)
   - Configuration file format documented with examples
   - README includes instructions for running backend in Docker
   - Code includes docstrings for key functions and classes

7. **Integration Verified:**
   - Backend integrates with `docker compose up -d`
   - Prometheus container successfully scrapes backend metrics
   - Logs are visible via `docker compose logs -f`

## 9. Open Questions

1. **Simulation Route Patterns:** Should the synthetic route generator support
   multiple pattern types (circular, figure-8, straight line, random walk)? Or
   start with one simple pattern?

1. **Metric Cardinality:** Should metrics include labels (e.g., `dish_id`,
   `location_name`) for future multi-dish support, or keep them label-free for
   Phase 2?

1. **Configuration Hot-Reload Scope:** Should configuration changes require any
   validation or safety checks? For example, should certain ranges be enforced
   to prevent invalid simulation states?

1. **Simulation Determinism:** Should the simulator support a "seed" for
   reproducible simulations during testing? This could be useful for debugging
   but adds complexity.

1. **Error Metrics:** Should the backend expose Prometheus metrics about its own
   health (e.g., `backend_errors_total`, `simulation_loop_duration_seconds`)?
   This would be helpful for monitoring but increases scope.

1. **Rate Limiting:** Should API endpoints include rate limiting to prevent
   abuse, or defer this to future phases?

1. **Configuration Validation:** Should the backend validate configuration
   changes against the current simulation state, or simply accept any valid
   configuration and restart the simulator?

1. **Logging Format:** Preference for structured JSON logs or traditional text
   logs? JSON is better for parsing but less human-readable during development.

---

**Document Version:** 1.0 **Created:** 2025-10-23 **Status:** Draft - Awaiting
Review **Phase:** Phase 2 - Backend Metrics Exporter and Simulator
