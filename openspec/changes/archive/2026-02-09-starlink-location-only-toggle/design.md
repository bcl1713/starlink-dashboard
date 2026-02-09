## Context

The Starlink dish exposes GPS control via the `dish_inhibit_gps` gRPC call, wrapped by `starlink_grpc.set_gps_config(enable=True/False)`. This function exists in the starlink-grpc-tools library but is not currently used in the codebase. The `StarlinkClient` class in `backend/starlink-location/app/live/client.py` already handles gRPC connections and data retrieval. The status data already includes `gps_enabled`, `gps_ready`, and `gps_sats` fields that can be exposed to the frontend.

## Goals / Non-Goals

**Goals:**
- Allow users to enable/disable GPS usage on the Starlink dish via the web UI
- Display current GPS status (enabled state, readiness, satellite count) for user feedback
- Follow existing API and component patterns in the codebase

**Non-Goals:**
- Persisting GPS preference in the application (the dish itself maintains this state)
- Automatic GPS toggling based on conditions
- Modifying how location data is used elsewhere in the application

## Decisions

### 1. API Design: Single Resource Endpoint

**Decision**: Create a single `/api/v2/gps/config` endpoint supporting GET and POST methods.

**Rationale**: This follows REST conventions where GPS configuration is treated as a resource. GET retrieves current state, POST updates it. This is simpler than separate enable/disable endpoints and matches the pattern in `config.py`.

**Alternatives Considered**:
- Separate `/gps/enable` and `/gps/disable` endpoints → More endpoints to maintain, less RESTful
- Adding to existing `/api/config` endpoint → Conflates simulation config with hardware config

### 2. Backend: Extend StarlinkClient

**Decision**: Add `get_gps_config()` and `set_gps_config()` methods to `StarlinkClient` class, then expose via new router module.

**Rationale**: Keeps gRPC interaction centralized in the client class. The client already handles connection management and error handling for other gRPC calls.

**Implementation**:
- `get_gps_config()`: Returns dict with `enabled`, `ready`, `satellites` from status_data
- `set_gps_config(enable: bool)`: Calls `starlink_grpc.set_gps_config()` and returns new state

### 3. Frontend: GPS Status Card Component

**Decision**: Create a dedicated `GPSControlCard` component placed in the dashboard or settings area rather than embedding in TimingSection.

**Rationale**: GPS control is a dish-level setting, not specific to route timing. A dedicated card provides clear visibility and can display all GPS status info (enabled, ready, satellites) alongside the toggle.

**Alternatives Considered**:
- Embed in TimingSection → Mixes concerns; GPS is hardware-level, not route-level
- New tab in LegConfigTabs → Overly complex for a single toggle
- Modal dialog → Hidden; users won't discover it easily

### 4. State Management: Direct API Calls

**Decision**: The frontend will make direct API calls on toggle change, no local caching of GPS state.

**Rationale**: The dish is the source of truth. Caching could lead to stale state if the dish is controlled externally. The status endpoint is fast enough for real-time display.

### 5. Error Handling: Permission Denied Handling

**Decision**: Handle `PERMISSION_DENIED` gRPC errors gracefully, displaying a clear message that the dish may not allow GPS control.

**Rationale**: Not all Starlink dishes may allow GPS modification. The UI should degrade gracefully rather than crash.

## Risks / Trade-offs

**[Network Latency]** → Each toggle requires a round-trip to the dish via gRPC. Mitigation: Show loading state on the toggle, disable during request.

**[Permission Denied]** → Some dishes may not allow GPS control. Mitigation: Detect and display helpful error message; disable toggle if not permitted.

**[State Sync]** → If GPS state is changed externally, UI may show stale state. Mitigation: Refresh GPS status on component mount and periodically (or on user request).

**[Dish Unavailability]** → Toggle will fail if dish is offline. Mitigation: Show connection status; disable toggle when disconnected.
