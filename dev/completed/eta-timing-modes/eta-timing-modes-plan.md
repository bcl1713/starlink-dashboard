# ETA Timing Modes: Anticipated vs. Estimated Implementation Plan

**Version:** 1.0.0
**Created:** 2025-11-04
**Last Updated:** 2025-11-04
**Status:** Planning Complete - Ready for Implementation
**Effort Estimate:** XL (4-6 development sessions)

---

## Executive Summary

This plan outlines the comprehensive implementation of **dual-mode ETA display** for the Starlink Dashboard. The system will automatically switch between displaying "Anticipated" ETAs (pre-departure, based on scheduled flight plan) and "Estimated" ETAs (post-departure, based on actual real-time telemetry).

### Business Value

- **Enhanced Pre-Flight Planning:** Crews can see anticipated arrival times before departure
- **Real-Time Accuracy:** Post-departure ETAs reflect actual conditions and speeds
- **Operational Clarity:** Clear visual distinction between planned vs. actual times
- **Flight Phase Awareness:** System tracks flight status automatically

### Technical Approach

**Full Implementation** with flight phase tracking and comprehensive state management:
- Extend route timing models to track actual departure times and flight status
- Enhance ETA calculation logic with mode detection (anticipated vs. estimated)
- Add flight phase state machine (pre_departure → in_flight → post_arrival)
- Update API responses to include ETA type metadata
- Modify Grafana dashboards for conditional formatting based on ETA mode
- Expose new Prometheus metrics with ETA type labels

---

## Current State Analysis

### Architecture Overview

The ETA system currently has three layers:

1. **ETACalculator** (`app/services/eta_calculator.py`)
   - Core ETA calculation engine
   - 120-second speed smoothing window
   - Route-aware ETA calculations (Session 28)
   - Handles on-route, off-route with projection, and fallback scenarios

2. **RouteETACalculator** (`app/services/route_eta_calculator.py`)
   - Segment-by-segment distance calculations
   - Route progress tracking (0-100%)
   - POI projection onto route path
   - ETA caching (5-second TTL)

3. **ETA Service** (`app/core/eta_service.py`)
   - Singleton manager coordinating metric updates
   - Passes active route context to calculator
   - Updates Prometheus metrics every second

### Existing Data Models

**RouteTimingProfile** (from `app/models/route.py`):
```python
- departure_time: datetime          # First waypoint scheduled time
- arrival_time: datetime            # Last waypoint scheduled time
- total_expected_duration_seconds: float
- has_timing_data: bool
- segment_count_with_timing: int
```

**POIWithETA** (from `app/models/poi.py`):
```python
- eta_seconds: float
- distance_meters: float
- bearing_degrees: float
- course_status: str
- route_aware_status: str
```

### Current Limitations

1. **No Flight Departure Tracking:** System doesn't distinguish between pre-departure and in-flight
2. **Single ETA Mode:** All ETAs calculated using current speed, regardless of departure status
3. **No ETA Type Indicator:** API responses don't indicate if ETA is anticipated or estimated
4. **Dashboard Lacks Context:** Grafana displays all ETAs the same way
5. **No Flight Phase State:** No tracking of flight progression through phases

---

## Proposed Future State

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flight State Manager                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │Pre-Departure│───▶│  In-Flight  │───▶│Post-Arrival │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│         │                   │                   │            │
│         └───────────────────┴───────────────────┘            │
│                             │                                │
└─────────────────────────────┼────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ETA Calculation Engine                    │
│  ┌────────────────────────┐    ┌────────────────────────┐  │
│  │  Anticipated ETA Mode  │    │  Estimated ETA Mode    │  │
│  │  (Scheduled Speeds)    │    │  (Actual Speeds)       │  │
│  └────────────────────────┘    └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API & Metrics Layer                       │
│  ┌────────────────────────┐    ┌────────────────────────┐  │
│  │  POI API Endpoints     │    │ Prometheus Metrics     │  │
│  │  (eta_type included)   │    │ (eta_type label)       │  │
│  └────────────────────────┘    └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Grafana Dashboard                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Conditional Formatting by ETA Type                    │ │
│  │  - Anticipated: Blue background, "Planned" label       │ │
│  │  - Estimated: Green background, "Live" label           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Automatic Departure Detection**
   - Monitor current speed against 50 knot threshold
   - Set flight status to "in_flight" when speed exceeds threshold
   - Manual override API for early/delayed departures

2. **Dual-Mode ETA Calculation**
   - **Anticipated Mode (Pre-Departure):**
     - Use scheduled segment speeds from KML timing data
     - Assume on-time departure
     - Calculate based on flight plan
   - **Estimated Mode (Post-Departure):**
     - For route segments: Use calculated/scheduled speed
     - For current segment: Average current speed with expected speed based on segment progress
     - For off-route POIs: Project to route first, then calculate as above
     - Real-time telemetry-based calculation with intelligent speed blending

3. **Flight Phase Tracking**
   - **pre_departure:** Before takeoff (anticipated ETAs)
   - **in_flight:** After departure, before final destination (estimated ETAs)
   - **post_arrival:** Completed flight (no ETAs)

4. **Enhanced API Responses**
   - All POI endpoints include `eta_type` field
   - New `/api/routes/flight-status` endpoint
   - Flight phase information in route endpoints

5. **Prometheus Metrics Enhancement**
   - Add `eta_type` label to existing metrics
   - New `starlink_flight_phase` metric (0=pre, 1=in, 2=post)
   - New `starlink_actual_departure_time_unix` metric

6. **Dashboard Visualization**
   - Color-coded ETA panels (blue = anticipated, green = estimated)
   - "PLANNED" vs. "LIVE" badges on ETA values
   - Flight status indicator panel
   - Departure countdown timer (pre-departure only)

---

## Implementation Phases

### Phase 1: Data Model Extensions (Effort: M)

**Goal:** Extend existing models to support flight status tracking and ETA typing.

**Tasks:**

1. **Extend RouteTimingProfile** (`app/models/route.py`)
   - Add `actual_departure_time: Optional[datetime]` field
   - Add `actual_arrival_time: Optional[datetime]` field
   - Add `flight_status: str` enum field (pre_departure/in_flight/post_arrival)
   - Add `is_departed()` method
   - Add `is_in_flight()` method

2. **Extend POIWithETA** (`app/models/poi.py`)
   - Add `eta_type: str` field (anticipated/estimated)
   - Add `is_pre_departure: bool` field
   - Add `flight_phase: Optional[str]` field
   - Update example JSON schema

3. **Create FlightStatus Model** (new file: `app/models/flight_status.py`)
   - Define `FlightPhase` enum
   - Define `FlightStatusResponse` model
   - Define `DepartureUpdateRequest` model

**Acceptance Criteria:**
- All model tests pass
- New fields have proper validation
- Pydantic schemas generate correct OpenAPI docs
- Backward compatibility maintained (all new fields optional)

**Dependencies:** None

**Estimated Time:** 2-3 hours

---

### Phase 2: Flight State Manager (Effort: L)

**Goal:** Create a state manager to track and transition flight phases.

**Tasks:**

1. **Create FlightStateManager** (new file: `app/services/flight_state_manager.py`)
   - Singleton pattern for global state
   - Track current flight phase
   - Implement state transition logic
   - Departure detection (automatic and manual)
   - Arrival detection (within 100m of final waypoint)
   - State persistence (in-memory)

2. **Implement Departure Detection Logic**
   - Monitor current speed vs. threshold
   - Track speed persistence (e.g., >50 knots for 10+ seconds)
   - Auto-transition to in_flight when:
     - Current speed exceeds 50 knots consistently

3. **Implement Arrival Detection Logic**
   - Monitor distance to final waypoint
   - Auto-transition to post_arrival when:
     - Within 100m of final waypoint for >60 seconds

4. **Add Manual Override API**
   - `POST /api/routes/flight-status/depart` - Force departure
   - `POST /api/routes/flight-status/arrive` - Force arrival
   - `POST /api/routes/flight-status/reset` - Reset to pre-departure

**Acceptance Criteria:**
- State transitions occur correctly based on conditions
- Manual overrides work and are logged
- State persists across telemetry updates
- Unit tests cover all transition paths
- Thread-safe for concurrent access

**Dependencies:** Phase 1 complete

**Estimated Time:** 4-5 hours

---

### Phase 3: ETA Calculation Logic Enhancement (Effort: L)

**Goal:** Modify ETACalculator to support dual-mode calculations.

**Tasks:**

1. **Modify ETACalculator.calculate_poi_metrics()** (`app/services/eta_calculator.py`)
   - Accept `flight_state_manager` parameter
   - Query current flight phase
   - Branch calculation logic based on phase
   - Return `eta_type` in metric dictionary

2. **Implement Anticipated ETA Calculation**
   - Use scheduled segment speeds from route timing data
   - Calculate from scheduled departure time (not current time)
   - Assume flight follows planned route exactly
   - Method: `_calculate_anticipated_eta()`

3. **Implement Estimated ETA Calculation**
   - Use existing route-aware logic with enhancements
   - Speed calculation strategy:
     - Future route segments: Use calculated/scheduled segment speeds
     - Current segment: Blend current speed with expected speed based on progress
     - Off-route POIs: Project to route, then apply same logic
   - Calculate from current position and time
   - Method: `_calculate_estimated_eta()` (enhance existing logic)

4. **Update calculate_poi_metrics() Return Structure**
   - Add `eta_type` key to each POI metric dict
   - Add `flight_phase` key
   - Maintain backward compatibility

**Acceptance Criteria:**
- Pre-departure: ETAs calculated using scheduled speeds
- Post-departure: ETAs calculated using actual speeds
- Mode switching occurs automatically based on flight phase
- All existing tests pass with new logic
- New tests cover both modes

**Dependencies:** Phase 2 complete

**Estimated Time:** 5-6 hours

---

### Phase 4: API Endpoint Updates (Effort: M)

**Goal:** Update POI and route API endpoints to expose ETA type information.

**Tasks:**

1. **Update POI ETA Endpoint** (`app/api/pois.py`)
   - Modify `get_pois_with_etas()` to include flight state
   - Pass flight_state_manager to ETA calculator
   - Map `eta_type` from calculator to `POIWithETA` response
   - Set `is_pre_departure` and `flight_phase` fields

2. **Create Flight Status Endpoints** (new: `app/api/flight_status.py`)
   - `GET /api/routes/flight-status` - Get current status
   - `POST /api/routes/flight-status/depart` - Manual departure
   - `POST /api/routes/flight-status/arrive` - Manual arrival
   - `POST /api/routes/flight-status/reset` - Reset to pre-departure

3. **Update Route Timing Endpoint** (`app/api/routes.py`)
   - Add flight status to `/api/routes/active/timing` response
   - Include `actual_departure_time` if departed
   - Include `actual_arrival_time` if arrived

4. **Update API Documentation**
   - Add examples for anticipated vs. estimated responses
   - Document flight status state machine
   - Update OpenAPI schema

**Acceptance Criteria:**
- All POI responses include `eta_type` field
- Flight status endpoints work correctly
- API documentation is complete and accurate
- Backward compatibility maintained
- All API tests pass

**Dependencies:** Phase 3 complete

**Estimated Time:** 3-4 hours

---

### Phase 5: Prometheus Metrics Updates (Effort: M)

**Goal:** Expose flight status and ETA type via Prometheus metrics.

**Tasks:**

1. **Add Flight Status Metrics** (`app/core/metrics.py`)
   - `starlink_flight_phase` - Gauge (0=pre, 1=in, 2=post)
   - `starlink_actual_departure_time_unix` - Gauge
   - `starlink_actual_arrival_time_unix` - Gauge
   - `starlink_time_until_departure_seconds` - Gauge (pre-departure only)

2. **Add eta_type Label to Existing Metrics**
   - Modify `starlink_eta_poi_seconds` to include `eta_type` label
   - Modify `starlink_distance_to_poi_meters` to include `eta_type` label
   - Maintain backward compatibility (default label = "estimated")

3. **Update Metric Update Logic** (`app/core/eta_service.py`)
   - Query flight state manager for current phase
   - Set appropriate labels on metrics
   - Update metrics on every telemetry cycle

4. **Add Flight Status to Health Endpoint**
   - Include current flight phase in `/health` response
   - Include time until departure (if pre-departure)

**Acceptance Criteria:**
- New metrics appear in `/metrics` endpoint
- Existing metrics gain `eta_type` label
- Grafana can query metrics by ETA type
- Metrics update correctly on flight phase transitions
- No performance degradation

**Dependencies:** Phase 4 complete

**Estimated Time:** 2-3 hours

---

### Phase 6: Grafana Dashboard Enhancements (Effort: L)

**Goal:** Update dashboards to display anticipated vs. estimated ETAs with visual distinction.

**Tasks:**

1. **Update POI Management Dashboard** (`monitoring/grafana/provisioning/dashboards/poi-management.json`)
   - Add flight status indicator panel (top)
   - Update "Next Destination" panel with ETA type badge
   - Update "Time to Next Arrival" panel:
     - Blue background for anticipated ETAs
     - Green background for estimated ETAs
     - Add "PLANNED" or "LIVE" badge
   - Update ETA table with ETA type column

2. **Add Departure Countdown Panel** (pre-departure only)
   - Show time until scheduled departure
   - Hide panel when in-flight or post-arrival
   - Red color when <30 minutes to departure

3. **Add Flight Status Panel**
   - Current phase indicator
   - Scheduled vs. actual departure time comparison
   - Time since departure (in-flight only)

4. **Update Query Transformations**
   - Filter metrics by `eta_type` label
   - Use conditional formatting based on flight phase
   - Add tooltip showing ETA calculation mode

5. **Update Fullscreen Overview Dashboard** (`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`)
   - Add flight status indicator (small panel)
   - Color-code ETA displays by type

**Acceptance Criteria:**
- Visual distinction clear between anticipated and estimated
- Flight status prominently displayed
- Panels show/hide based on flight phase
- Dashboard updates automatically on phase transitions
- All queries work correctly with new metric labels

**Dependencies:** Phase 5 complete

**Estimated Time:** 4-5 hours

---

### Phase 7: Testing and Validation (Effort: M)

**Goal:** Comprehensive testing of the entire feature.

**Tasks:**

1. **Unit Tests**
   - FlightStateManager state transitions (15 tests)
   - ETACalculator dual-mode logic (20 tests)
   - Model validation (10 tests)
   - API endpoint responses (15 tests)

2. **Integration Tests**
   - Pre-departure scenario: Upload route, verify anticipated ETAs
   - Departure transition: Simulate departure, verify mode switch
   - In-flight scenario: Verify estimated ETAs during flight
   - Arrival transition: Simulate arrival, verify completion
   - Manual override scenarios

3. **End-to-End Testing**
   - Upload timed route
   - Verify pre-departure state
   - Activate route
   - Check dashboard shows anticipated ETAs
   - Trigger departure (automatic or manual)
   - Verify dashboard switches to estimated ETAs
   - Complete flight
   - Verify post-arrival state

4. **Performance Testing**
   - Measure overhead of flight state checks
   - Verify no performance degradation in ETA calculations
   - Test with 1000+ POIs

**Acceptance Criteria:**
- All tests pass (451 existing + 60 new = 511 total)
- 100% test coverage for new code
- No regressions in existing functionality
- Performance benchmarks met (<5% overhead)

**Dependencies:** Phase 6 complete

**Estimated Time:** 4-5 hours

---

### Phase 8: Documentation and Deployment (Effort: S)

**Goal:** Complete documentation and prepare for production.

**Tasks:**

1. **Update User Documentation**
   - Add section to `docs/ROUTE-TIMING-GUIDE.md` on ETA modes
   - Create `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` with:
     - Flight phase state machine diagram
     - Manual override instructions
     - Dashboard interpretation guide

2. **Update API Documentation**
   - Update OpenAPI descriptions
   - Add code examples for new endpoints
   - Document metric labels

3. **Update CLAUDE.md**
   - Add flight status management section
   - Document ETA mode behavior
   - Add troubleshooting tips

4. **Create Migration Notes**
   - Backward compatibility guarantees
   - Breaking changes (if any)
   - Recommended upgrade path

5. **Deployment Checklist**
   - Docker rebuild required (Python code changes)
   - No database migrations needed (in-memory state)
   - Grafana dashboard provisioning automatic
   - Verify metrics after deployment

**Acceptance Criteria:**
- All documentation complete and accurate
- API docs reflect new endpoints and fields
- Deployment checklist verified
- No user-facing breaking changes

**Dependencies:** Phase 7 complete

**Estimated Time:** 2-3 hours

---

## Risk Assessment and Mitigation Strategies

### Risk 1: Breaking Changes to API Responses

**Likelihood:** Low
**Impact:** High
**Mitigation:**
- Make all new fields optional with defaults
- Maintain existing response structure
- Add versioning to affected endpoints if needed
- Comprehensive backward compatibility testing

### Risk 2: Performance Degradation

**Likelihood:** Medium
**Impact:** Medium
**Mitigation:**
- Flight state checks are O(1) lookups (in-memory)
- Cache flight phase for each telemetry cycle
- Benchmark ETA calculation overhead (target: <5%)
- Use profiling to identify bottlenecks

### Risk 3: State Synchronization Issues

**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Use thread-safe singleton for FlightStateManager
- Atomic state transitions with locks
- Comprehensive state transition tests
- Manual override capability for recovery

### Risk 4: Dashboard Query Complexity

**Likelihood:** Low
**Impact:** Medium
**Mitigation:**
- Test Grafana queries with new labels
- Use query variables for flexibility
- Document query patterns
- Provide fallback queries for old metrics

### Risk 5: Timing Data Dependency

**Likelihood:** Medium
**Impact:** Medium
**Mitigation:**
- Graceful degradation when no timing data available
- Default to estimated mode if timing data missing
- Clear messaging when anticipated mode unavailable
- Support both timed and non-timed routes

---

## Success Metrics

### Functional Metrics

- **100% Test Coverage:** All new code covered by unit tests
- **Zero Breaking Changes:** Existing API clients work without modification
- **<5% Performance Overhead:** ETA calculations remain fast
- **Automatic Mode Switching:** No manual intervention required

### User Experience Metrics

- **Visual Clarity:** >90% user comprehension of ETA types in usability testing
- **Dashboard Load Time:** <2 seconds for POI management dashboard
- **Mode Switch Latency:** <1 second from departure trigger to dashboard update

### Technical Metrics

- **API Response Time:** <100ms for POI ETA endpoints (95th percentile)
- **Metric Update Frequency:** 1 second (no change from current)
- **State Transition Accuracy:** 100% correct transitions in test scenarios

---

## Required Resources and Dependencies

### Development Resources

- **Backend Developer:** Python, FastAPI, Pydantic expertise
- **Frontend Developer:** Grafana JSON dashboard configuration
- **QA Engineer:** Test case design and execution
- **Technical Writer:** Documentation updates

### Infrastructure Dependencies

- **Docker:** Rebuild required for Python code changes
- **Prometheus:** No changes needed (backward compatible)
- **Grafana:** Dashboard provisioning (automatic on restart)

### External Dependencies

- **KML Timing Data:** Routes must have timing metadata for anticipated mode
- **Simulation Mode:** For testing without real Starlink terminal
- **Existing Route System:** All route management APIs must function correctly

---

## Timeline Estimates

### Development Schedule (By Phase)

| Phase | Description | Effort | Duration |
|-------|-------------|--------|----------|
| 1 | Data Model Extensions | M | 2-3 hours |
| 2 | Flight State Manager | L | 4-5 hours |
| 3 | ETA Calculation Enhancement | L | 5-6 hours |
| 4 | API Endpoint Updates | M | 3-4 hours |
| 5 | Prometheus Metrics Updates | M | 2-3 hours |
| 6 | Grafana Dashboard Enhancements | L | 4-5 hours |
| 7 | Testing and Validation | M | 4-5 hours |
| 8 | Documentation and Deployment | S | 2-3 hours |
| **Total** | **End-to-End Implementation** | **XL** | **26-34 hours** |

### Session-Based Timeline

Assuming 4-6 hour development sessions:

- **Session 1:** Phases 1-2 (Models + State Manager)
- **Session 2:** Phase 3 (ETA Calculation Enhancement)
- **Session 3:** Phases 4-5 (API + Metrics)
- **Session 4:** Phase 6 (Grafana Dashboards)
- **Session 5:** Phase 7 (Testing + Validation)
- **Session 6:** Phase 8 + Buffer (Documentation + Deployment + Contingency)

**Total Estimated Sessions:** 5-6 sessions

---

## Appendix A: Code Examples

### Example 1: Flight State Manager Usage

```python
from app.services.flight_state_manager import FlightStateManager, FlightPhase

# Get singleton instance
flight_mgr = FlightStateManager.get_instance()

# Check current phase
current_phase = flight_mgr.get_current_phase()
# Returns: FlightPhase.PRE_DEPARTURE

# Check if flight has departed
if flight_mgr.is_departed():
    print("Flight is in progress")

# Manual departure trigger
flight_mgr.trigger_departure()

# Now phase is FlightPhase.IN_FLIGHT
```

### Example 2: Dual-Mode ETA Calculation

```python
from app.services.eta_calculator import ETACalculator

calculator = ETACalculator()

# Calculate with flight state awareness
metrics = calculator.calculate_poi_metrics(
    current_lat=40.7,
    current_lon=-74.0,
    pois=pois_list,
    speed_knots=150.0,
    active_route=active_route,
    flight_state_manager=flight_mgr  # NEW parameter
)

# Result includes eta_type
for poi_id, metric in metrics.items():
    print(f"POI: {metric['poi_name']}")
    print(f"ETA: {metric['eta_seconds']}s ({metric['eta_type']})")
    # Output: ETA: 1800s (anticipated) or ETA: 1650s (estimated)
```

### Example 3: API Response with ETA Type

```json
{
  "poi_id": "KADW",
  "name": "Andrews AFB",
  "eta_seconds": 1800,
  "eta_type": "anticipated",
  "is_pre_departure": true,
  "flight_phase": "pre_departure",
  "distance_meters": 75000,
  "bearing_degrees": 125.0,
  "course_status": "on_course"
}
```

### Example 4: Grafana Query with ETA Type Filter

```promql
# Query for anticipated ETAs only
starlink_eta_poi_seconds{eta_type="anticipated"}

# Query for estimated ETAs only
starlink_eta_poi_seconds{eta_type="estimated"}

# Conditional formatting based on type
(starlink_eta_poi_seconds{eta_type="anticipated"} > 0) * 1
OR
(starlink_eta_poi_seconds{eta_type="estimated"} > 0) * 2
```

---

## Appendix B: State Machine Diagram

```
                    ┌─────────────────┐
                    │                 │
                    │  PRE_DEPARTURE  │
                    │                 │
                    └────────┬────────┘
                             │
                             │ Triggers:
                             │ - Manual /depart
                             │ - Auto: speed > 50 knots consistently
                             │
                             ▼
                    ┌─────────────────┐
                    │                 │
                    │    IN_FLIGHT    │
                    │                 │
                    └────────┬────────┘
                             │
                             │ Triggers:
                             │ - Manual /arrive
                             │ - Auto: within 100m of final waypoint
                             │
                             ▼
                    ┌─────────────────┐
                    │                 │
                    │  POST_ARRIVAL   │
                    │                 │
                    └─────────────────┘
                             │
                             │ Trigger:
                             │ - Manual /reset
                             │
                             ▼
                    ┌─────────────────┐
                    │  PRE_DEPARTURE  │
                    │  (route reset)  │
                    └─────────────────┘
```

---

## Appendix C: File Change Summary

### New Files (5)

1. `backend/starlink-location/app/models/flight_status.py` - Flight phase models
2. `backend/starlink-location/app/services/flight_state_manager.py` - State management
3. `backend/starlink-location/app/api/flight_status.py` - Flight status endpoints
4. `backend/starlink-location/tests/test_flight_state_manager.py` - Unit tests
5. `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` - User documentation

### Modified Files (12)

1. `backend/starlink-location/app/models/route.py` - Add flight status fields
2. `backend/starlink-location/app/models/poi.py` - Add eta_type fields
3. `backend/starlink-location/app/services/eta_calculator.py` - Dual-mode calculation
4. `backend/starlink-location/app/core/eta_service.py` - Flight state integration
5. `backend/starlink-location/app/core/metrics.py` - New metrics
6. `backend/starlink-location/app/api/pois.py` - Include eta_type in responses
7. `backend/starlink-location/app/api/routes.py` - Flight status in responses
8. `backend/starlink-location/main.py` - Initialize FlightStateManager
9. `monitoring/grafana/provisioning/dashboards/poi-management.json` - Dashboard updates
10. `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` - Flight status panel
11. `docs/ROUTE-TIMING-GUIDE.md` - Add ETA modes section
12. `CLAUDE.md` - Add flight status management section

---

**Plan Created By:** Claude Code Strategic Planning Agent
**Plan Version:** 1.0.0
**Ready for Implementation:** Yes
**Blockers:** None
