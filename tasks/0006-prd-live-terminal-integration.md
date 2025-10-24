# PRD: Live Starlink Terminal Integration

## 1. Introduction/Overview

The Starlink monitoring dashboard currently operates exclusively in simulation mode, generating synthetic telemetry for development and testing. This feature will enable the system to connect to a physical Starlink terminal via its local gRPC API (192.168.100.1:9200) and collect real-time telemetry data including position, network metrics, and system status.

**Problem:** Without live terminal support, the dashboard cannot be used for its intended purpose: monitoring actual Starlink performance during mobile operations.

**Goal:** Enable the backend service to poll a live Starlink terminal, calculate heading from GPS data, and expose metrics to Prometheus/Grafana with automatic fallback to simulation mode if the terminal is unreachable.

## 2. Goals

1. Connect to Starlink terminal at 192.168.100.1:9200 via gRPC when configured in live mode
2. Poll real telemetry data at 1-second intervals
3. Calculate heading from successive GPS positions using the existing HeadingTracker service
4. Expose all telemetry as Prometheus metrics (matching simulation mode format)
5. Automatically fall back to simulation mode if terminal connection fails
6. Provide clear visibility into which mode (live/simulation) is active
7. Enable testing with a real terminal by [target test date]

## 3. User Stories

1. **As a mobile Starlink operator**, I want to see my terminal's real-time position on the Grafana map so that I can track my current location and trajectory.

2. **As a network administrator**, I want to monitor actual latency, throughput, and obstruction metrics from my Starlink dish so that I can diagnose connectivity issues.

3. **As a developer**, I want the system to automatically fall back to simulation mode when the dish is unavailable so that I can continue development and testing without hardware dependencies.

4. **As a system operator**, I want clear indication of whether I'm viewing live or simulated data so that I don't mistake simulation for reality.

5. **As a mobile operator**, I want the system to calculate my heading based on GPS movement so that I can see my direction of travel on the dashboard.

## 4. Functional Requirements

### 4.1 Core Live Mode Functionality

1. The system **must** support a configuration option to enable live mode (via `config.yaml` or `STARLINK_MODE` environment variable)
2. When in live mode, the system **must** attempt to connect to the Starlink terminal at `192.168.100.1:9200` using gRPC
3. The system **must** poll telemetry data from the terminal at 1-second intervals
4. The system **must** extract and process the following data from the Starlink API:
   - GPS position (latitude, longitude, altitude)
   - Network metrics (latency, download throughput, upload throughput)
   - Obstruction percentage
   - Dish status (uptime, errors, thermal state)
   - Any other available telemetry fields

### 4.2 Heading Calculation

5. The system **must** use the existing `HeadingTracker` service to calculate heading from successive GPS positions
6. Heading tracker settings **must** be configurable via `config.yaml` with the following parameters:
   - `min_distance_meters` (default: 10.0)
   - `max_age_seconds` (default: 30.0)
7. The system **must** only update heading when the terminal has moved a significant distance to avoid GPS jitter

### 4.3 Metrics Export

8. All telemetry from live mode **must** be exposed via the `/metrics` endpoint in the same format as simulation mode
9. The system **must** export a metric indicating current mode: `starlink_mode_info{mode="live"}` or `starlink_mode_info{mode="simulation"}`
10. All existing Prometheus metrics **must** continue to work without modification to Grafana dashboards

### 4.4 Automatic Fallback

11. If the system cannot connect to the Starlink terminal at startup, it **must** automatically fall back to simulation mode
12. The system **must** log a clear warning message when fallback occurs
13. If connection is lost during operation, the system **should** attempt to reconnect for 30 seconds before falling back to simulation
14. Fallback events **must** be logged with sufficient detail for troubleshooting (connection error, timeout, etc.)

### 4.5 Mode Visibility

15. The system **must** log the active mode (live/simulation) on startup with a clear, prominent message
16. The `/health` endpoint **must** include the current mode in its JSON response
17. A Prometheus metric **must** indicate the active mode for dashboard display
18. The system **should** log mode changes (e.g., fallback from live to simulation) at WARNING level

### 4.6 Dependencies

19. The system **must** add required gRPC dependencies to `requirements.txt`:
    - `grpcio>=1.50.0`
    - Additional dependencies for Starlink client library (see Technical Considerations)
20. The system **must** gracefully handle missing dependencies in simulation-only deployments

### 4.7 Code Structure

21. A `LiveCoordinator` class **must** be created to mirror the existing `SimulationCoordinator` interface
22. The `LiveCoordinator` **must** implement the same public methods as `SimulationCoordinator` to ensure drop-in compatibility
23. The application startup logic **must** conditionally instantiate the correct coordinator based on configuration
24. All live mode code **should** be organized in a new module (e.g., `app/live/`)

## 5. Non-Goals (Out of Scope)

1. **Dish control features** (reboot, stow) are optional/stretch goals and NOT required for initial release
2. **Multi-terminal support** (monitoring multiple dishes simultaneously)
3. **Historical data replay** from recorded sessions
4. **WebSocket push** for real-time updates (continue using Prometheus polling)
5. **Advanced error recovery** (automatic dish reset, diagnostic commands)
6. **Authentication/authorization** for API access (Starlink dish API is currently unauthenticated)
7. **Support for non-standard dish IP addresses** (assume 192.168.100.1 is fixed)

## 6. Design Considerations

### 6.1 Architecture

- Follow the existing pattern established by `SimulationCoordinator`
- Maintain clean separation between live and simulation code paths
- Ensure both coordinators implement a common interface for polymorphic usage

### 6.2 Configuration Schema

Update `app/models/config.py` to include heading tracker configuration:

```yaml
heading_tracker:
  min_distance_meters: 10.0
  max_age_seconds: 30.0
```

### 6.3 User Experience

- Zero changes required to Grafana dashboards
- Transparent switching between modes
- Clear logging for troubleshooting

## 7. Technical Considerations

### 7.1 Starlink Client Library

Two viable options exist:

**Option A: Use sparky8512/starlink-grpc-tools**
- Pros: Mature, well-documented, active community
- Cons: May include unnecessary tooling beyond core client

**Option B: Custom gRPC client**
- Pros: Minimal dependencies, full control
- Cons: More development effort, need protobuf definitions

**Recommendation:** Start with Option A (sparky8512/starlink-grpc-tools) for faster implementation. Can refactor to custom client later if needed.

### 7.2 Error Handling

Implement robust error handling for:
- Network timeouts
- gRPC connection failures
- Malformed telemetry responses
- Temporary dish unavailability (e.g., during reboot)

### 7.3 Performance

- 1-second polling interval is aggressive; monitor CPU/memory impact
- Consider connection pooling or persistent gRPC channels
- Ensure HeadingTracker doesn't recalculate unnecessarily

### 7.4 Dependencies

Key files to modify:
- `backend/starlink-location/requirements.txt` - Add gRPC dependencies
- `backend/starlink-location/app/main.py` - Conditional coordinator instantiation
- `backend/starlink-location/app/core/config.py` - Load heading tracker config
- `backend/starlink-location/app/models/config.py` - Add heading tracker settings schema

## 8. Success Metrics

### 8.1 Testing Criteria (Primary - for tomorrow's test)

1. ✅ **Live position visible on map**: Terminal's real GPS coordinates appear and update on Grafana geomap
2. ✅ **Real metrics updating**: Latency, throughput, obstructions display actual dish data (not simulated)
3. ✅ **Fallback works**: Disconnecting the dish triggers automatic fallback to simulation with log warnings
4. ✅ **Heading calculation**: Heading updates correctly when the terminal is in motion

### 8.2 Quality Metrics

5. Zero breaking changes to existing Grafana dashboards
6. No degradation in simulation mode performance
7. Clean separation of concerns (live vs simulation code)
8. Comprehensive error logging for troubleshooting

### 8.3 Long-term Success

9. System runs reliably for 24+ hours in live mode without crashes
10. Automatic recovery from temporary network disruptions
11. Community adoption (if open-sourced)

## 9. Open Questions

1. **Error threshold**: How many consecutive gRPC failures should trigger fallback to simulation? (Currently: 30 seconds of retries)

2. **Reconnection strategy**: Should the system periodically attempt to reconnect to the dish if it failed at startup, or only retry on application restart?

3. **Metrics during fallback**: Should the mode metric update in real-time when fallback occurs, or only reflect the configured mode?

4. **gRPC channel lifecycle**: Should we use a persistent gRPC channel or create new connections for each poll? (Persistent is more efficient)

5. **Protobuf definitions**: If using a custom client, where should we source the official Starlink protobuf files? (They may not be publicly documented by SpaceX)

6. **Testing without hardware**: How can we write unit tests for LiveCoordinator without access to a real dish? (Mock the gRPC responses)

7. **Docker networking**: Will the Docker container be able to reach 192.168.100.1 on the host network? (May need `network_mode: host`)

## 10. Implementation Notes

### 10.1 Suggested Development Order

1. Add gRPC dependencies to `requirements.txt`
2. Create `LiveCoordinator` class skeleton
3. Integrate Starlink client library (test basic connection)
4. Implement telemetry polling loop
5. Integrate `HeadingTracker` service
6. Add mode visibility (logs, /health, metrics)
7. Implement automatic fallback logic
8. Add heading tracker configuration to config schema
9. Update `main.py` with conditional coordinator instantiation
10. Test with real hardware
11. (Optional) Implement dish control endpoints

### 10.2 Testing Strategy

- **Unit tests**: Mock gRPC responses to test LiveCoordinator logic
- **Integration tests**: Use a local gRPC server simulator for end-to-end testing
- **Manual testing**: Verify with actual Starlink terminal (scheduled for tomorrow)

### 10.3 Docker Considerations

The `starlink-location` service may need `network_mode: host` in `docker-compose.yml` to access the dish at 192.168.100.1 on the host network. Alternatively, use `extra_hosts` to map the dish IP.

## 11. Acceptance Criteria

This feature is considered complete when:

1. ✅ The system successfully connects to a live Starlink terminal and displays real metrics in Grafana
2. ✅ All four primary success criteria pass during tomorrow's hardware test
3. ✅ Automatic fallback to simulation occurs when the dish is disconnected
4. ✅ Mode is clearly visible in logs, /health endpoint, and Prometheus metrics
5. ✅ Heading updates correctly during terminal movement
6. ✅ No changes required to existing Grafana dashboards
7. ✅ Code is documented with clear comments explaining live mode logic
8. ✅ Configuration options are documented in README or config.yaml comments

---

**Document Version:** 1.0
**Created:** 2025-10-24
**Target Completion:** 2025-10-25 (hardware test date)
**Owner:** Development Team
