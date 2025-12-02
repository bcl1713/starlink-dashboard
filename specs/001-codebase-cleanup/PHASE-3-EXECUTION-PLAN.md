# Phase 3 Execution Plan: File Size Compliance (MVP)

**Status**: Active Implementation
**Target**: 80% compliance (21 of 26 files under 300 lines)
**Branch**: `001-codebase-cleanup`

## Strategic Approach

Given the analysis from Phase 1, we're implementing a **priority-based refactoring** focusing on:

1. **High-Impact Files** (largest violations, most reusable refactoring patterns)
2. **Sequential Groups** (dependencies between files honored)
3. **Smoke Testing** (verify behavior unchanged after each refactor)
4. **Small PRs** (1-3 related files per PR for manageable reviews)

---

## File Priority Matrix

| Priority | File | Lines | Type | Complexity | Refactor Into | Expected Effort |
|----------|------|-------|------|-----------|---------------|-----------------|
| **P0** | `backend/starlink-location/app/api/ui.py` | 3995 | Templates | High | `ui/` module (4 files) | 8h |
| **P1** | `backend/starlink-location/app/mission/timeline_service.py` | 1439 | Logic | Very High | `mission/timeline/` (3 files) | 6h |
| **P2** | `backend/starlink-location/app/mission/exporter.py` | 1927 | Logic | High | `mission/exporter/` (4 files) | 7h |
| **P3** | `backend/starlink-location/app/api/pois.py` | 1092 | Logic + Endpoints | Very High | `api/pois/` (3 files) | 5h |
| **P4** | `backend/starlink-location/app/api/routes.py` | 1046 | Endpoints | High | `api/routes/` (4 files) | 5h |
| **P5** | `backend/starlink-location/app/mission/package_exporter.py` | 1291 | Logic | High | `mission/package/` (3 files) | 6h |
| **P6** | `backend/starlink-location/app/mission/routes.py` | 1192 | Endpoints | High | `mission/routes/` (3 files) | 5h |
| **P7** | `backend/starlink-location/app/mission/routes_v2.py` | 1104 | Endpoints | Medium | Consolidate with `routes.py` | 4h |
| **P8** | `backend/starlink-location/app/services/kml_parser.py` | 1008 | Logic | Medium | `services/kml/` (3 files) | 4h |

**Backend Subtotal**: 9 files → 14 files (all under 300 lines)

---

## Implementation Strategy by Week

### Week 1: Foundation Modules (High-Impact, High-Reuse)

**Goal**: Establish service layer patterns and template extraction

1. **Day 1-2 (P0)**: Extract `ui.py` templates → `ui/` module
   - `ui/__init__.py` - Router initialization
   - `ui/templates.py` - HTML/CSS/JS templates (500-600 lines each)
   - `ui/helpers.py` - Form generation utilities
   - **Smoke test**: Verify `/ui/pois`, `/ui/routes`, `/ui/mission-planner` render

2. **Day 3-4 (P1)**: Decompose `timeline_service.py` → `mission/timeline/`
   - `timeline/__init__.py` - Calculator initialization
   - `timeline/calculator.py` - Timeline calculations
   - `timeline/state_manager.py` - State transitions
   - `timeline/validators.py` - Validation logic
   - **Smoke test**: Verify timeline endpoints work with existing missions

3. **Day 5 (P2)**: Extract exporter logic → `mission/exporter/`
   - `exporter/__init__.py` - Export router
   - `exporter/json_exporter.py` - JSON formatting
   - `exporter/kml_exporter.py` - KML formatting
   - `exporter/csv_exporter.py` - CSV formatting
   - **Smoke test**: Verify export endpoints for all formats

### Week 2: Service Layer (Reusable Patterns)

**Goal**: Extract business logic into focused services

4. **Day 1-2 (P3)**: Refactor `pois.py` → `api/pois/`
   - **Key action**: Extract 361-line `get_pois_with_etas()` function
   - `pois/__init__.py` - CRUD endpoints
   - `pois/etas.py` - ETA calculation wrapper
   - `pois/stats.py` - Aggregation endpoints
   - **Smoke test**: Verify POI list, filtering, ETA updates

5. **Day 3-4 (P4)**: Refactor `routes.py` → `api/routes/`
   - `routes/__init__.py` - CRUD endpoints
   - `routes/management.py` - Activation/deactivation
   - `routes/upload.py` - File upload handling
   - `routes/stats.py` - Progress tracking
   - **Smoke test**: Verify route upload, activation, list operations

6. **Day 5 (P5)**: Extract package logic → `mission/package/`
   - `package/__init__.py` - Package assembly router
   - `package/builder.py` - Mission package construction
   - `package/compressor.py` - ZIP compression
   - `package/validator.py` - Validation
   - **Smoke test**: Verify package download works

### Week 3: Consolidation (Remaining Critical Files)

**Goal**: Finish remaining high-complexity files

7. **Day 1-2 (P6+P7)**: Refactor mission routes → `mission/routes/`
   - Consolidate `routes.py` + `routes_v2.py`
   - `routes/__init__.py` - V1 + V2 endpoints
   - `routes/missions.py` - Mission CRUD
   - `routes/legs.py` - Leg management
   - `routes/waypoints.py` - Waypoint operations
   - **Smoke test**: Verify both v1 and v2 APIs work

8. **Day 3-4 (P8)**: Extract KML parsing → `services/kml/`
   - `kml/__init__.py` - Parser initialization
   - `kml/parser.py` - Parsing logic
   - `kml/validator.py` - Validation
   - `kml/transformer.py` - GeoJSON conversion
   - **Smoke test**: Verify route upload still works

### Week 4+: Remaining Files (Parallel)

**Moderate Files** (300-1000 lines) - Can run in parallel:
- `core/metrics.py` (850 lines) → `core/metrics/`
- `services/eta_calculator.py` (735 lines) → `services/eta/`
- `services/route_eta_calculator.py` (652 lines) → `services/route_eta/`
- `services/poi_manager.py` (624 lines) → `services/poi/`
- `services/flight_state_manager.py` (540 lines) → `services/flight_state/`

**Frontend** (Parallel with backend):
- `frontend/mission-planner/src/components/common/RouteMap.tsx` (482 lines)
- `frontend/mission-planner/src/pages/LegDetailPage.tsx` (379 lines)
- `frontend/mission-planner/src/pages/SatelliteManagerPage.tsx` (359 lines)

**Documentation** (Parallel with code):
- Split 9 large docs into topic-based modules

---

## PR Strategy

Each refactoring produces a **focused PR** with:

### PR Format: Group + Number

```
title: refactor(phase3): extract [module] into separate components

- Extracted [function/class] from X lines to Y files
- Created [module]/file structure:
  - file1.py: [purpose]
  - file2.py: [purpose]
- Smoke tested: [endpoints/features verified]
- Line count: [original] → [new] (X% reduction)

Files changed:
- backend/starlink-location/app/api/[module]/ (new module)
- Updated backend/starlink-location/app/api/__init__.py imports
```

### Smoke Test Checklist (Every PR)

For each refactored module:

```bash
# 1. Verify imports work
python -c "from backend.starlink_location.app.api.[module] import *"

# 2. Start backend
docker compose down && docker compose build --no-cache && docker compose up -d

# 3. Test critical endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/[endpoint]  # Main endpoint for module

# 4. Verify in frontend (if applicable)
# Open http://localhost:3000 and test UI interactions
```

---

## Success Criteria (End of Phase 3)

- [ ] At least 21 of 26 files under 300 lines
- [ ] All refactored files pass Black/Ruff linting
- [ ] All endpoints function correctly (smoke tested)
- [ ] No breaking changes to public APIs
- [ ] Clear separation of concerns in refactored modules
- [ ] All changes committed in focused PRs
- [ ] Deferred files (5 max) documented with justification comments

---

## Risk Mitigation

### High-Risk Areas
1. **ui.py template extraction**: Risk of breaking HTML output
   - **Mitigation**: Test each template endpoint individually
   - **Rollback**: Revert extraction, keep embedded (can defer to Phase 4)

2. **timeline_service.py**: Complex state machine
   - **Mitigation**: Write unit tests for state transitions before refactoring
   - **Rollback**: Revert to single file, document for later

3. **pois.py large function**: 361 lines in `get_pois_with_etas()`
   - **Mitigation**: Extract to service layer with comprehensive testing
   - **Rollback**: Keep wrapped function, split API endpoints instead

### Testing Strategy
- Use existing integration tests as smoke tests
- Add targeted unit tests for extracted services
- Manual API testing via curl before merge
- Frontend e2e testing for UI changes

---

## Dependency Resolution

### Import Graph Issues to Watch
1. **Circular imports**: `api/pois.py` ↔ `services/poi_manager.py`
   - **Solution**: Inject dependencies, break circular reference
2. **Global state**: `_coordinator` pattern in multiple modules
   - **Solution**: Extract to `core/coordinator_manager.py`
3. **Tight coupling**: UI templates hardcoded in endpoints
   - **Solution**: Template files + dependency injection

---

## Estimated Timeline

| Phase | Tasks | Est. Effort | Target Completion |
|-------|-------|------------|-------------------|
| **Week 1** | P0, P1, P2 (UI, Timeline, Exporter) | 21h | Day 5 |
| **Week 2** | P3, P4, P5 (POIs, Routes, Package) | 16h | Day 5 |
| **Week 3** | P6, P7, P8 (Mission, KML) | 13h | Day 4 |
| **Week 4+** | Moderate files + Frontend + Docs | 25h | Ongoing |
| **Total Phase 3** | 26 files → 80%+ compliance | ~75h | 4 weeks |

---

## Notes

- **Sequential within week**: Respect dependencies
- **Parallel across weeks**: Can run different weeks in parallel with different developers
- **Stop-and-validate checkpoints**: After Week 1, verify critical paths work
- **MVP threshold**: Stop after 21 files (80%) hit 300-line limit
- **Defer non-critical**: Up to 5 files can be deferred with justification
- **Document progress**: Update PHASE-3-PROGRESS.md daily

---

## Next Action

**Start Week 1, Day 1: Refactor ui.py**

```bash
# 1. Create ui/ module directory
mkdir -p backend/starlink-location/app/api/ui

# 2. Extract templates
# (See REFACTORING-GUIDE.md for step-by-step)

# 3. Update imports in __init__.py

# 4. Run smoke tests

# 5. Commit PR
```

Ready to proceed? Let me know and I'll start ui.py refactoring.
