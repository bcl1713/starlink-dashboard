# Mission Communication Planning - Session Notes

**Date**: 2025-11-11
**Branch**: `feature/mission-comm-planning`
**Session Duration**: ~2 hours
**Status**: Phase 3 timeline scaffolding in progress

## Session Summary (2025-11-11)

- Added `backend/starlink-location/app/mission/state.py` with helpers to translate `MissionEvent` streams into contiguous per-transport intervals plus `tests/unit/test_mission_state.py`.
- Implemented `backend/starlink-location/app/mission/timeline.py` to merge interval data into `TimelineSegment`s + `MissionTimeline` instances with coverage from `tests/unit/test_mission_timeline.py`.
- Updated pytest fixtures to isolate mission storage under `/tmp/test_data/missions`, preventing first-run integration failures that were caused by leftover JSON files.
- Rebuilt the Docker image, restarted `starlink-location`, and re-ran the full test suite inside the container: `docker compose exec starlink-location python -m pytest` → 691 passed / 22 skipped / 1 warning (expected Pydantic serializer deprecation).
- Refreshed `mission-comm-planning-context.md`, `...-tasks.md`, and `STATUS.md` with the new progress plus next actions.

### Files Touched
- `backend/starlink-location/app/mission/state.py` (new) & `tests/unit/test_mission_state.py`
- `backend/starlink-location/app/mission/timeline.py` (new) & `tests/unit/test_mission_timeline.py`
- `backend/starlink-location/tests/conftest.py` (mission storage isolation)
- Documentation under `dev/active/mission-comm-planning/`

### Outstanding / Next Steps
1. Hook the new interval/timeline helpers into mission activation so we persist fresh segments on every save/activate.
2. Expose `/api/missions/{id}/timeline` + `/api/missions/active/timeline` and publish Prometheus metrics (`mission_comm_state{transport=...}`, degraded/critical counters).
3. Once APIs exist, re-run `docker compose exec starlink-location python -m pytest tests/integration/test_mission_routes.py tests/integration/test_eta_modes.py` followed by the full suite.
4. Begin export generator + Grafana timeline work after the API/metrics backbone is in place.

### Verification Commands
- `docker compose exec starlink-location python -m pytest`
- `docker compose exec starlink-location python -m pytest tests/unit/test_mission_state.py tests/unit/test_mission_timeline.py`

---

**Date**: 2025-11-10
**Branch**: `feature/mission-comm-planning`
**Session Duration**: ~90 minutes
**Status**: Phase 1 Data Foundations Complete

## Session Summary

Successfully completed Phase 1 Data Foundations for the mission communication planning feature. Established comprehensive data models, storage layer, and test infrastructure that will serve as the foundation for phases 2-5.

## Work Completed

### Data Models (app/mission/models.py - 551 lines)

**Core Entities**:
- `Mission` – Root aggregate capturing route, transports, and metadata
- `TransportConfig` – Three-transport coordination (X, Ka, Ku)
- `XTransition` – Satellite handoff specifications with lat/lon coordinates
- `KaOutage` – Manual Ka coverage gaps
- `AARWindow` – Air-refueling segments referenced by waypoint names
- `KuOutageOverride` – Manual Ku constellation outages
- `TimelineSegment` – Temporal periods with uniform communication status
- `TimelineAdvisory` – Operator guidance for manual actions
- `MissionTimeline` – Complete timeline with statistics

**Design Decisions**:
1. Off-route projection: Store actual coordinates; project to route for timing
2. Portable storage: Flat JSON files enable staging→production workflow
3. Three-transport semantics: X singular, Ka triple, Ku always-on
4. Checksum integrity: SHA256 per mission for manual edit detection

### Storage Layer (app/mission/storage.py - 243 lines)

**API**:
- `save_mission()` – Write to `data/missions/{id}.json` + checksum
- `load_mission()` – Deserialize with validation
- `list_missions()` – Metadata retrieval
- `delete_mission()` – Remove mission + checksum
- `mission_exists()` – Quick existence check
- `compute_mission_checksum()` – JSON-based hash for reproducibility

**Key Features**:
- Automatic directory creation
- Checksum logging (warning on mismatch, doesn't fail)
- Graceful handling of missing files
- Portable design (no database, copy-friendly)

### Test Coverage (42 tests passing)

**Models (25 tests)**:
- Coordinate validation (-90/90 lat, -180/180 lon)
- Longitude normalization (200° → -160°)
- Duration validation (>0 required)
- Serialization/deserialization roundtrips
- Enumeration correctness

**Storage (17 tests)**:
- Save/load roundtrips (data preservation)
- Checksum computation and validation
- Deletion operations
- Listing with metadata
- Complex nested transport configs
- Restart resilience

### Documentation

**New Files**:
- `PHASE-1-COMPLETION.md` – Comprehensive Phase 1 report with test inventory, design decisions, and next steps
- `SESSION-NOTES.md` – This file

**Updated Files**:
- `mission-comm-planning-context.md` – Separated completed vs. in-progress components
- `mission-comm-planning-tasks.md` – Marked 2 tasks complete, detailed CRUD task

## Technical Decisions & Rationale

### 1. Pydantic v2 Migration
**Decision**: Use Pydantic v2 (as specified in requirements.txt)
**Rationale**: Modern schema validation, better performance
**Impact**: Had to adapt checksum function (no `sort_keys` in `model_dump_json`)
**Result**: Implemented JSON-based serialization with explicit `json.dumps(sort_keys=True)`

### 2. Flat-File vs. Database
**Decision**: Portable JSON files in `data/missions/`
**Rationale**:
- Planners can prepare missions offline on staging instance
- Copy to live stack without schema migration
- No database overhead for relatively small datasets
- Easier debugging and inspection
**Tradeoff**: No full-text search initially (acceptable, can add later)

### 3. Off-Route Projection Strategy
**Decision**: Store original coordinates for display; project to route for timing
**Rationale**:
- Satellite transition POIs may not lie on flight path
- Operators need to see exact transition locations on map
- Timeline needs ETA based on route progression
**Implementation**: Reuses existing `RouteETACalculator.project_poi_to_route()` (already battle-tested)

### 4. Three-Transport Asymmetry
**Decision**: Model X, Ka, Ku with different state machines
**Rationale**:
- X: Single satellite per segment, planner chooses transitions
- Ka: Three satellites, coverage-based + optional manual outages
- Ku: Always-on, only explicit overrides
**Result**: Each transport has distinct configuration and availability logic

### 5. Checksum Integrity Without Enforcement
**Decision**: Log checksum mismatches but allow loads to continue
**Rationale**:
- Developers may hand-edit mission files during testing
- Immediate rejection would be frustrating for workflow
- Logging creates audit trail
**Future**: Could upgrade to version control or file locking if needed

## Integration Points Identified

### Existing Systems
1. **Route System** (`app/models/route.py`)
   - Missions reference `route_id`
   - Timeline will use `RouteTimingProfile` for departure/arrival times
   - AARWindows reference KML waypoint names

2. **POI System** (`app/models/poi.py`)
   - Transition POIs will use existing POI model
   - Off-route projections will use `POIManager.calculate_poi_projections()`
   - Projected locations stored in POI.projected_latitude/longitude

3. **Flight Status** (`app/models/flight_status.py`)
   - Mission timeline references flight phases (pre_departure, in_flight, post_arrival)
   - Activation resets FlightStateManager state
   - ETA mode (anticipated vs. estimated) synchronized with mission state

4. **Metrics** (`app/metrics.py`)
   - Will expose mission_active_info, mission_phase_state, mission_next_conflict_seconds
   - Updates on activation and timeline recompute

### Planned Integrations (Phase 2-3)
- Satellite catalog and geometry calculations (Phase 2)
- Communication timeline engine (Phase 3)
- Grafana dashboard panels (Phase 4)

## Known Issues & Workarounds

### None at this stage
All unit tests pass; storage is resilient; models are comprehensive.

## Performance Observations

```
Model instantiation:  <1ms
Storage write:        <5ms (JSON + checksum)
Storage read:         <3ms (deserialize + validate)
Test suite runtime:   ~250ms total (both modules)
```

All operations well within acceptable real-time thresholds.

## Next Steps (Phase 1 Continuation)

### Immediate (This Sprint)
1. **CRUD Endpoints** (`app/mission/routes.py`)
   - POST /api/missions (create)
   - GET /api/missions (list)
   - GET /api/missions/{id} (read)
   - PUT /api/missions/{id} (update)
   - DELETE /api/missions/{id} (delete)
   - POST /api/missions/{id}/activate (activate + reset flight state)
   - GET /api/missions/active (get currently active)

2. **Mission Metrics** (`app/metrics.py` integration)
   - Expose mission_active_info, mission_phase_state, mission_next_conflict_seconds
   - Update on activation
   - Link to timeline recompute (Phase 3)

### Phase 2 (Satellite Geometry)
- Implement satellite catalog and KMZ loader
- Azimuth/elevation calculations
- Transition projection buffers
- Coverage sampler for Ka

### Phase 3 (Timeline Engine)
- Transport availability state machine
- Timeline segmentation logic
- Export generators (CSV, XLSX, PDF)

### Phase 4 (Visualization)
- Grafana map overlays for satellites and coverage
- Mission timeline panel
- Alert rules

### Phase 5 (Hardening)
- Scenario regression tests
- Performance benchmarking
- Operational documentation

## Files Changed (Commit 59255c0)

```
New Files:
  backend/starlink-location/app/mission/__init__.py        (32 lines)
  backend/starlink-location/app/mission/models.py          (551 lines)
  backend/starlink-location/app/mission/storage.py         (243 lines)
  backend/starlink-location/tests/unit/test_mission_models.py    (297 lines)
  backend/starlink-location/tests/unit/test_mission_storage.py   (306 lines)
  dev/active/mission-comm-planning/*.md files

Modified:
  backend/starlink-location/app/api/ui.py (minor cleanup)

Total: +2094 lines, 11 files
```

## Team Coordination Notes

### Branch Strategy
- Feature branch: `feature/mission-comm-planning`
- All Phase 1-5 work will accumulate here
- PR to main after Phase 5 complete

### Dependency Graph
```
Phase 1: Data + Storage (COMPLETE)
├── Phase 1 cont: CRUD + Metrics
├── Phase 2: Geometry Engine
│   └── Phase 3: Timeline Engine
│   └── Phase 3 cont: Exports
├── Phase 4: Visualization
└── Phase 5: Hardening
```

### Review Checklist (For Phase 1 Merge)
- [ ] CRUD endpoints implement POST/GET/PUT/DELETE/POST activate/GET active
- [ ] Metrics registered and update on mission lifecycle events
- [ ] GUI scaffolded with route selection and form inputs
- [ ] Import/export working for mission JSON
- [ ] Integration tests use TestClient
- [ ] No console errors in development server
- [ ] Docker build completes without warnings
- [ ] Tests pass in CI

## Lessons Learned

1. **Pydantic v2 differences**: Changed serialization API; had to adapt checksum logic
2. **Fixture scoping**: Test fixtures properly scoped to avoid reusing stale data
3. **JSON stability**: Using `sort_keys=True` ensures reproducible checksums
4. **Portable design pays off**: Can copy missions between systems without migration
5. **Test-driven model design**: Tests revealed edge cases (longitude normalization, zero duration)

## Questions for Stakeholders

1. **Departure time adjustments**: Should missions track scheduled vs. actual separately?
2. **Multi-stage missions**: Support chaining routes end-to-end?
3. **Satellite data sources**: Use provided HCX KMZ, orbital elements, or both?
4. **Timeline granularity**: 1-second segments or coarser (minute/event-based)?
5. **Manual overrides**: Should operators be able to override timeline segments live?

## References

- Plan: `mission-comm-planning-plan.md`
- Tasks: `mission-comm-planning-tasks.md`
- Context: `mission-comm-planning-context.md`
- Completion Report: `PHASE-1-COMPLETION.md`
- Commit: 59255c0 (feat: Phase 1 - Mission communication planning data foundations)
