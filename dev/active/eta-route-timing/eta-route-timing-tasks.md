# ETA Route Timing - Task Checklist

**Last Updated:** 2025-11-03
**Status:** Ready for Implementation
**Effort:** XL (11-17 days estimated)

---

## Phase 1: Data Model Enhancements (Est. 1-2 days)

- [ ] **1.1** Extend RoutePoint model
  - [ ] Add `expected_arrival_time: Optional[datetime]` field
  - [ ] Add `expected_segment_speed_knots: Optional[float]` field
  - [ ] Add JSON schema examples
  - [ ] Verify backward compatibility
  - [ ] Tests: model creation with/without timing

- [ ] **1.2** Extend RouteWaypoint model
  - [ ] Add `expected_arrival_time: Optional[datetime]` field
  - [ ] Document field usage
  - [ ] Tests: waypoint with timing

- [ ] **1.3** Create RouteTimingProfile class (optional)
  - [ ] Holds: segment speeds, total duration, departure time
  - [ ] Methods: get_segment_speed(), get_total_duration()
  - [ ] Tests: profile creation and queries

- [ ] **1.4** Update API response models
  - [ ] RouteDetailResponse includes timing fields
  - [ ] RouteResponse includes timing count
  - [ ] Tests: API models serialize/deserialize correctly

- [ ] **1.5** Unit tests for Phase 1
  - [ ] test_route_models_with_timing.py
  - [ ] Verify all 4 model updates work
  - [ ] Existing routes still parse (backward compat)
  - [ ] Code coverage >90%

---

## Phase 2: KML Parser Enhancements (Est. 2-3 days)

- [ ] **2.1** Create timestamp extraction utility
  - [ ] Function: `extract_timestamp_from_description(description: str) -> Optional[datetime]`
  - [ ] Regex: `Time Over Waypoint: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z)`
  - [ ] Parse to UTC datetime
  - [ ] Handle missing/malformed data gracefully
  - [ ] Tests: 20+ test cases (valid, invalid, edge cases)

- [ ] **2.2** Update KML parser main function
  - [ ] Call extraction utility for each waypoint
  - [ ] Store in `RouteWaypoint.expected_arrival_time`
  - [ ] Log warnings if parsing fails
  - [ ] Pass timing data through to RoutePoint

- [ ] **2.3** Calculate segment speeds during parsing
  - [ ] After route assembly, iterate consecutive waypoints
  - [ ] For each pair with times: `speed = distance / time_delta`
  - [ ] Store in `RoutePoint.expected_segment_speed_knots`
  - [ ] Skip segments with missing/invalid times
  - [ ] Skip segments with zero time delta
  - [ ] Handle out-of-order timestamps (log warning)

- [ ] **2.4** Add route-level timing metadata
  - [ ] Extract departure waypoint from route name (e.g., KADW in "KADW-PHNL")
  - [ ] Find first waypoint with timestamp
  - [ ] Store departure time in ParsedRoute or profile
  - [ ] Calculate total expected duration
  - [ ] Tests: departure detection on all 6 legs

- [ ] **2.5** Parser integration tests
  - [ ] Parse all 6 test KML files
  - [ ] Verify waypoint timestamps extracted correctly
  - [ ] Verify segment speeds calculated (spot-check math)
  - [ ] Verify no crashes on edge cases
  - [ ] Code coverage >90%

- [ ] **2.6** Validation tests
  - [ ] Leg 1: KADW→PHNL timing accuracy
  - [ ] Leg 2: PHNL→RJTY timing accuracy
  - [ ] Legs 3-6: Parse without errors
  - [ ] Verify math on 2-3 segments per leg

---

## Phase 3: ETA Calculator v2 (Est. 3-4 days)

- [ ] **3.1** Create RouteETACalculator class
  - [ ] File: `app/services/route_eta_calculator.py`
  - [ ] Methods:
    - [ ] `__init__(default_speed_knots=400, blending_factor=0.5)`
    - [ ] `set_route(route: ParsedRoute) -> None`
    - [ ] `update_position(lat, lon, speed, timestamp) -> None`
    - [ ] `is_departed() -> bool`
    - [ ] `calculate_poi_etas(pois) -> dict`
  - [ ] Docstrings for all public methods

- [ ] **3.2** Implement departure detection
  - [ ] Track ground position and speed on initialization
  - [ ] Speed > 50 knots threshold = departed (configurable via DEPARTURE_THRESHOLD_SPEED_KNOTS)
  - [ ] Once departed, flag persists until route deactivated
  - [ ] Log departure with timestamp
  - [ ] Tests: speed threshold, persistence, reset
  - [ ] Note: 50 knots indicates takeoff roll (max taxi ~30 knots with buffer)

- [ ] **3.3** Implement pre-departure ETA calculation
  - [ ] When is_departed() == False:
    - [ ] For each waypoint with expected_arrival_time:
    - [ ] Calculate eta_countdown_seconds = expected_arrival_time - current_utc_time
    - [ ] Calculate eta_time_gmt = expected_arrival_time (as ISO-8601 datetime)
    - [ ] Return both values (countdown + absolute time)
    - [ ] Return negative countdown if time is in past
  - [ ] Tests: various current times relative to schedule, both time formats

- [ ] **3.4** Implement in-flight ETA blending
  - [ ] When is_departed() == True:
    - [ ] For each POI/waypoint:
      - [ ] If has expected_arrival_time:
        - [ ] Calculate time_to_expected = expected - now
        - [ ] Calculate distance_eta = distance / current_speed
        - [ ] Blend: eta = distance_eta * α + time_to_expected * (1-α)
      - [ ] Else: Use distance / current_speed (fallback)
  - [ ] Configurable α (default 0.5)
  - [ ] Tests: blending formula verification, edge cases

- [ ] **3.5** Extend POI ETA calculations
  - [ ] Update POI metric responses to include:
    - [ ] `eta_countdown_seconds` (relative time in seconds)
    - [ ] `eta_time_gmt` (absolute time in GMT/Z)
    - [ ] `expected_arrival_time` (if waypoint)
    - [ ] `expected_segment_speed_knots` (if available)
    - [ ] `actual_speed_knots` (current speed)
    - [ ] `blending_factor_used` (for debugging)
    - [ ] `is_pre_departure` (mode flag)
    - [ ] `on_route` (boolean)
  - [ ] Tests: POI response structure with both time formats
  - [ ] Tests: on_route flag accuracy

- [ ] **3.6** Implement off-route point projection
  - [ ] For POIs not on route: project to nearest route segment
  - [ ] Calculate distance from current position to projected point along route
  - [ ] Use projected distance for ETA calculation
  - [ ] Return both original and projected coordinates in API response:
    - [ ] `latitude`, `longitude` (original position for map)
    - [ ] `projected_latitude`, `projected_longitude` (projection to route)
  - [ ] Add flags to response:
    - [ ] `on_route` (boolean - is point on route?)
    - [ ] `projected_to_route` (boolean - was point projected?)
    - [ ] `point_status` (ahead/reached/passed)
  - [ ] Tests: projection accuracy on 6 KML files
  - [ ] Tests: ETA calculation with projected distance

- [ ] **3.7** Implement hybrid point status determination
  - [ ] When route active:
    - [ ] Use route-projected distance to determine "ahead" vs "passed"
    - [ ] Compare current position along route to projected point position
  - [ ] When route inactive:
    - [ ] Fall back to angle-based heading logic (existing)
  - [ ] Update POI status logic to work with both approaches
  - [ ] Tests: point status accuracy for on-route and off-route POIs
  - [ ] Tests: graceful fallback when route deactivated

- [ ] **3.8** Unit tests for Phase 3
  - [ ] test_route_eta_calculator.py
    - [ ] Departure detection (5+ scenarios with 50 knot threshold)
    - [ ] Pre-departure ETA (5+ scenarios, both time formats)
    - [ ] In-flight blending formula (10+ scenarios)
    - [ ] Off-route point projection accuracy
    - [ ] Hybrid point status determination
    - [ ] Edge cases (zero speed, missing times, etc.)
  - [ ] Code coverage >90%
  - [ ] Math verification with manual calculations

- [ ] **3.9** Integration tests with real KML
  - [ ] test_route_eta_integration.py
  - [ ] Load each of 6 KML files
  - [ ] Calculate ETAs for first 3 waypoints each
  - [ ] Verify against expected times (both countdown and GMT formats)
  - [ ] Simulate position updates and verify adjustments
  - [ ] Test off-route POI scenarios (satellite handoff markers)
  - [ ] Verify hybrid point status with and without active route

---

## Phase 4: Simulator & Route Follower Integration (Est. 1-2 days)

- [ ] **4.1** Extend KMLRouteFollower
  - [ ] Add `set_timing_profile(profile: RouteTimingProfile) -> None`
  - [ ] Method: `get_expected_speed_for_segment(segment_idx) -> Optional[float]`
  - [ ] Method: `get_expected_arrival_time(waypoint_idx) -> Optional[datetime]`
  - [ ] Docstrings

- [ ] **4.2** Update SimulationCoordinator
  - [ ] When active route changes: pass timing profile to follower
  - [ ] Use expected segment speeds when available
  - [ ] Speed variations within ±10% of expected
  - [ ] Log segment speed changes
  - [ ] Tests: follower uses expected speeds

- [ ] **4.3** Update PositionSimulator
  - [ ] Accept expected speed hint from route follower
  - [ ] Blend simulated speed with expected speed
  - [ ] Ensure arrival times match (or close) in simulation
  - [ ] Tests: simulator respects timing

- [ ] **4.4** Optional simulation controls
  - [ ] `POST /api/sim/set_speed_multiplier?factor=1.0`
  - [ ] Allows speeding up/slowing down simulation
  - [ ] Tests: speed multiplier works

- [ ] **4.5** Integration tests for simulator
  - [ ] Upload route → activate → simulate → verify timing
  - [ ] Simulator progress matches expected times

---

## Phase 5: Dashboard & Metrics (Est. 2-3 days)

- [ ] **5.1** Create new Prometheus metrics
  - [ ] In `app/core/metrics.py`:
    - [ ] `starlink_expected_segment_speed_knots` (gauge)
    - [ ] `starlink_departure_time` (gauge, unix timestamp)
    - [ ] `starlink_eta_to_next_waypoint_seconds` (gauge)
    - [ ] `starlink_waypoint_sequence` (gauge)
    - [ ] `starlink_actual_vs_expected_speed_ratio` (gauge)
  - [ ] All with appropriate labels (route_name, etc.)

- [ ] **5.2** Update `/api/route/coordinates` endpoint
  - [ ] Include timing info in response
  - [ ] Show expected vs. actual speeds
  - [ ] Include departure/arrival times
  - [ ] Tests: endpoint response structure

- [ ] **5.3** Update `/api/pois` endpoint
  - [ ] Include `expected_arrival_time` when available
  - [ ] Include `is_pre_departure` flag
  - [ ] Include blending info (for debugging)
  - [ ] Tests: POI response with timing

- [ ] **5.4** Update route detail API
  - [ ] Include timing profile in route details
  - [ ] Show segment speeds
  - [ ] Show total expected duration
  - [ ] Tests: detailed route response

- [ ] **5.5** Create Grafana dashboard panels
  - [ ] Modify `fullscreen-overview.json`:
    - [ ] Timeline panel: planned vs. actual waypoint arrivals
    - [ ] Speed profile panel: expected vs. actual over route
    - [ ] Gauge: pre-flight departure countdown (if pre-departure)
    - [ ] Table: expected vs. actual metrics
  - [ ] Update dashboard provisioning

- [ ] **5.6** Update route management UI
  - [ ] Display timing profile in route details modal
  - [ ] Show expected duration for active route
  - [ ] Show departure/arrival times
  - [ ] Show segment speeds in table
  - [ ] Tests: UI displays timing correctly

- [ ] **5.7** Metrics integration tests
  - [ ] Verify all metrics exposed to Prometheus
  - [ ] Verify metrics update on position changes
  - [ ] Verify Grafana queries work
  - [ ] Manual dashboard verification

---

## Phase 6: Testing & Documentation (Est. 2-3 days)

- [ ] **6.1** Comprehensive unit test suite
  - [ ] All Phase 1-5 components tested
  - [ ] Target >90% code coverage
  - [ ] Coverage report generated
  - [ ] All tests passing

- [ ] **6.2** Integration test suite
  - [ ] End-to-end: upload KML → activate → simulate → verify ETAs
  - [ ] All 6 test legs verified
  - [ ] Route switching behavior tested
  - [ ] Departure detection tested
  - [ ] ETA adjustments verified
  - [ ] All tests passing

- [ ] **6.3** Performance testing
  - [ ] KML parsing timing (<5s for 10k points)
  - [ ] ETA calculation timing (<10ms per POI)
  - [ ] Simulator speed accuracy (±1-2%)
  - [ ] Dashboard loading time acceptable
  - [ ] Document results

- [ ] **6.4** Update design documentation
  - [ ] `docs/design-document.md`
    - [ ] Add section on route timing & ETA calculations
    - [ ] Explain blending algorithm with examples
    - [ ] Show sample outputs (pre-flight & in-flight)
    - [ ] Diagram: architecture with timing flow

- [ ] **6.5** Update project instructions
  - [ ] `CLAUDE.md` - Add timing feature section
  - [ ] Configuration options documented
  - [ ] How to interpret timing-aware ETAs
  - [ ] Troubleshooting tips

- [ ] **6.6** Create user guide
  - [ ] How to use timing-aware routes
  - [ ] Pre-departure mode explanation
  - [ ] In-flight mode explanation
  - [ ] Dashboard panels guide
  - [ ] Configuration examples

- [ ] **6.7** Configuration implementation
  - [ ] Add env variables:
    - [ ] `ETA_BLENDING_FACTOR` (default: 0.5)
    - [ ] `DEPARTURE_SPEED_THRESHOLD_KNOTS` (default: 10)
    - [ ] `ENABLE_ROUTE_TIMING` (default: true)
    - [ ] `ETA_DEFAULT_SPEED_KNOTS` (default: 400)
  - [ ] Load in main.py
  - [ ] Pass to components
  - [ ] Tests: config loading

- [ ] **6.8** Regression testing
  - [ ] Verify existing ETA functionality still works
  - [ ] Non-routed flights (great-circle distance)
  - [ ] Routes without timing data
  - [ ] All existing tests pass
  - [ ] No breaking changes

- [ ] **6.9** Documentation review
  - [ ] All docs reviewed for accuracy
  - [ ] Examples verified working
  - [ ] API docs updated
  - [ ] Link checks performed

- [ ] **6.10** Final validation
  - [ ] All 6 test KML files validated
  - [ ] All tests passing (unit + integration)
  - [ ] Code coverage >90%
  - [ ] No critical/high bugs
  - [ ] Performance targets met
  - [ ] Documentation complete

---

## Cross-Phase Tasks

- [ ] **Git Management**
  - [ ] Create feature branch: `feature/eta-route-timing`
  - [ ] Commit after each phase
  - [ ] Keep commits focused and well-documented
  - [ ] Final PR before merge

- [ ] **Code Review Checkpoints**
  - [ ] Phase 1-2 review (models + parser)
  - [ ] Phase 3 review (ETA logic - critical)
  - [ ] Phase 5 review (metrics + dashboard)
  - [ ] Final full-stack review

- [ ] **Testing Throughout**
  - [ ] Unit tests alongside implementation
  - [ ] Integration tests after each phase
  - [ ] Manual testing on Docker stack
  - [ ] Fix any issues immediately

- [ ] **Documentation Throughout**
  - [ ] Add docstrings as code is written
  - [ ] Update CLAUDE.md incrementally
  - [ ] Create examples for new features
  - [ ] Keep task list in sync

---

## Success Completion Checklist

### Functionality Complete
- [ ] Pre-departure ETAs match KML timing (±2% tolerance)
- [ ] In-flight ETAs adjust smoothly with actual speed
- [ ] All 6 test KML files parse without errors
- [ ] Zero regressions in existing ETA functionality
- [ ] Departure detection reliable (50 knot threshold)
- [ ] Blending factor configurable and working (default 0.5)
- [ ] ETA data available in both countdown (seconds) and GMT/Z (ISO-8601) formats
- [ ] Off-route point projection working (distance and point status)
- [ ] Hybrid point status determination (route-based + angle-based fallback)
- [ ] Simulator respects timing and expected speeds

### Code Quality Complete
- [ ] >90% code coverage achieved
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] No critical or high-severity bugs
- [ ] Code follows project style (Prettier formatting)
- [ ] All docstrings complete
- [ ] Type hints on all functions

### Performance Complete
- [ ] ETA calculations <10ms per POI
- [ ] Route parsing <5 seconds per file
- [ ] Simulator timing accurate ±1-2%
- [ ] Dashboard loads without lag
- [ ] Metrics update reliably

### Documentation Complete
- [ ] Design document updated
- [ ] CLAUDE.md updated
- [ ] API documentation complete
- [ ] Configuration documented
- [ ] User guide created
- [ ] All examples verified

### Deployment Ready
- [ ] Feature branch created
- [ ] All commits squashed/cleaned
- [ ] Merge conflicts resolved
- [ ] Final tests all passing
- [ ] PR created and ready for review

---

## Progress Tracking

**Started:** [TBD - when branch created]
**Phase 1 Due:** [TBD]
**Phase 2 Due:** [TBD]
**Phase 3 Due:** [TBD - critical path]
**Phase 4 Due:** [TBD]
**Phase 5 Due:** [TBD - dashboard visualization]
**Phase 6 Due:** [TBD]
**Completion Target:** [TBD - 11-17 days from start]

---

**Checklist Status:** ✅ Ready for Use
**Last Updated:** 2025-11-03
