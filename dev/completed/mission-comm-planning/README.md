# Mission Communication Planning Feature

**Status**: Phase 1 Data Foundations Complete ✅
**Branch**: `feature/mission-comm-planning`
**Last Updated**: 2025-11-10
**Test Coverage**: 42/42 passing (100%)

## Quick Start

This directory contains all planning, context, and documentation for the mission communication planning feature—a comprehensive system for predicting communication degradation across three onboard transports (X, Ka, Ku) by analyzing timed flight routes, satellite geometries, and operational constraints.

### Document Guide

| Document | Purpose | Audience |
|----------|---------|----------|
| **README.md** (this file) | Overview and navigation | Everyone |
| **mission-comm-planning-plan.md** | Full feature specification with phases and success metrics | PMs, Architects |
| **mission-comm-planning-context.md** | System context, data flows, and integration points | Developers, Architects |
| **mission-comm-planning-tasks.md** | Detailed implementation checklist with acceptance criteria | Developers |
| **PHASE-1-COMPLETION.md** | Comprehensive Phase 1 report with models, storage, and test inventory | Code reviewers, QA |
| **SESSION-NOTES.md** | Work session log with technical decisions and rationale | Team leads, Architecture |
| **mission-comm-planning-mockups.md** | UI/UX mockups for planner GUI and dashboard | UX/Frontend |

## Project Status

### Phase 1: Mission Data Foundations ✅ COMPLETE

**Deliverables**:
- ✅ Comprehensive Pydantic data models (Mission, TransportConfig, etc.)
- ✅ Portable mission storage with checksums (JSON + SHA256)
- ✅ 42 passing unit tests with full coverage
- ✅ Complete documentation and design rationale

**Code Location**:
```
backend/starlink-location/app/mission/
├── __init__.py          (module exports)
├── models.py            (551 lines - all data models)
└── storage.py           (243 lines - persistence layer)

backend/starlink-location/tests/unit/
├── test_mission_models.py    (25 tests)
└── test_mission_storage.py   (17 tests)

data/missions/               (auto-created on first save)
├── {mission_id}.json
└── {mission_id}.sha256
```

### Phase 1 Continuation: CRUD & Metrics (In Progress)

**Next Tasks** (in priority order):
1. CRUD endpoints (`app/mission/routes.py`)
   - POST /api/missions, GET /api/missions, GET /api/missions/{id}, PUT, DELETE
   - POST /api/missions/{id}/activate, GET /api/missions/active
2. Prometheus metrics exposure
   - mission_active_info, mission_phase_state, mission_next_conflict_seconds
3. Mission planner GUI scaffold
   - React/Vite frontend with route selection, transition forms, AAR configuration
4. Import/export workflow
   - Download mission JSON, upload to another instance

See `mission-comm-planning-tasks.md` for detailed specifications.

### Phases 2-5: Satellite Geometry, Timeline Engine, Visualization, Hardening (Planned)

Estimated 7 weeks total. See `mission-comm-planning-plan.md` for full roadmap.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Mission Planning System                   │
└─────────────────────────────────────────────────────────────┘

Phase 1: Data Foundations (COMPLETE)
├── Models: Mission, TransportConfig, XTransition, Timeline*
├── Storage: save_mission(), load_mission(), list_missions()
└── Tests: 42 tests covering all scenarios

Phase 1 Cont: APIs & UI
├── CRUD Endpoints: /api/missions/* routes
├── Metrics: mission_active_info, mission_phase_state
└── GUI: React planner for configuration

Phase 2: Geometry Engine
├── Satellite Catalog: KML/POI ingestion
├── Azimuth/Elevation: LookAngle calculations
└── Coverage Sampler: Ka footprint analysis

Phase 3: Timeline Engine
├── Transport State Machine: available/degraded/offline per X/Ka/Ku
├── Segmentation: Merge states into nominal/degraded/critical windows
└── Exports: CSV, XLSX, PDF with Zulu/Eastern/T+ timestamps

Phase 4: Visualization
├── Grafana Overlays: Satellites, coverage polygons, AAR markers
├── Timeline Panel: State timeline widget
└── Alerts: Prometheus rules for upcoming conflicts

Phase 5: Hardening
├── Regression Tests: 3+ scenario-based test suites
├── Performance: <1s recompute for 10 concurrent missions
└── Documentation: SOP, API reference, troubleshooting
```

## Key Design Decisions

### 1. Off-Route Projection Strategy
- **Problem**: Satellite transition POIs may not lie exactly on the flight route
- **Solution**: Store original coordinates for map display; project to route for timing
- **Benefit**: Operators see exact transition locations; timeline uses correct ETAs

### 2. Portable Mission Storage
- **Why**: Enable staging→production workflow without database migration
- **How**: Flat JSON files in `data/missions/{mission_id}.json`
- **Validation**: SHA256 checksums for manual edit detection

### 3. Three-Transport Asymmetry
- **X (Fixed Geostationary)**: Single satellite per segment; planner chooses transitions
- **Ka (Three Geostationary)**: Three satellites; coverage-based or manual outages
- **Ku (LEO Constellation)**: Always-on unless manually overridden

### 4. Integration with Existing Systems
- **Routes**: Missions reference route_id; timeline uses RouteTimingProfile
- **POIs**: Transitions use existing POI model; projections reuse RouteETACalculator
- **Flight Status**: Mission phases aligned with flight state manager
- **Metrics**: Prometheus integration for alerting and dashboards

See `PHASE-1-COMPLETION.md` for full architectural details and rationale.

## Testing

**Unit Tests**: 42/42 passing ✅

```bash
# Run all tests
docker compose exec starlink-location python -m pytest tests/unit/test_mission_*.py -v

# Run specific suite
docker compose exec starlink-location python -m pytest tests/unit/test_mission_models.py -v
docker compose exec starlink-location python -m pytest tests/unit/test_mission_storage.py -v
```

**Coverage**:
- Model validation (coordinates, durations, timestamps)
- Storage roundtrips (save/load/delete)
- Serialization/deserialization
- Checksum integrity
- Error handling

## Getting Started

### For Developers

1. **Review existing code**:
   ```bash
   cat backend/starlink-location/app/mission/models.py      # Data models
   cat backend/starlink-location/app/mission/storage.py     # Persistence
   ```

2. **Run tests**:
   ```bash
   docker compose up -d
   docker compose exec starlink-location python -m pytest tests/unit/test_mission_*.py -v
   ```

3. **Next task**: Implement CRUD endpoints (see mission-comm-planning-tasks.md)

### For Architects/PMs

1. Read `mission-comm-planning-plan.md` for full feature specification
2. Review `PHASE-1-COMPLETION.md` for technical details
3. Check `SESSION-NOTES.md` for design rationale

### For QA/Testing

1. Review test inventory in `PHASE-1-COMPLETION.md`
2. Test data models with sample JSON (see test files)
3. Validate storage roundtrips and restart resilience

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| 4e43e14 | docs: Add Phase 1 completion report | 4 files, +622 lines |
| 59255c0 | feat: Phase 1 data foundations | 11 files, +2094 lines |

## Integration Checklist

- [x] Models follow Pydantic v2 conventions
- [x] Storage uses portable flat files
- [x] Checksums validate data integrity
- [x] Unit tests cover all models and persistence
- [x] Docker build succeeds
- [ ] CRUD endpoints tested (Phase 1 cont)
- [ ] Metrics exposed in Prometheus (Phase 1 cont)
- [ ] GUI works with route API (Phase 1 cont)
- [ ] Satellite catalog implemented (Phase 2)
- [ ] Geometry engine tested (Phase 2)
- [ ] Timeline engine working (Phase 3)
- [ ] Grafana panels updated (Phase 4)
- [ ] Regression tests passing (Phase 5)

## Performance Notes

- Model instantiation: <1ms
- Storage write: <5ms
- Storage read: <3ms
- Test suite: ~250ms total
- Target: Timeline recompute <1s for 10 concurrent missions (Phase 3)

All operations well within acceptable thresholds.

## Common Questions

**Q: Can I use these models with a database?**
A: Yes, but Phase 1 uses flat files for portability. Future phases could add a database layer without changing the models.

**Q: How do off-route transitions work?**
A: Store the actual latitude/longitude for map display; the system projects them to the nearest route point for ETA calculation. Both coordinates are preserved.

**Q: What if a mission file gets corrupted?**
A: The checksum will mismatch and a warning is logged, but the mission still loads. Future versions could enforce strict validation or version control.

**Q: Can missions be copied between instances?**
A: Yes! Just copy the JSON file from `data/missions/{id}.json` to another instance. No database schema migration needed.

## Support & Documentation

- **Questions?** Check SESSION-NOTES.md for design rationale
- **Stuck?** Review the failing test in tests/unit/test_mission_*.py
- **Need details?** See PHASE-1-COMPLETION.md for implementation specifics

## Branch Management

- **Feature branch**: `feature/mission-comm-planning`
- **All Phases 1-5** work accumulates here
- **PR to main** after Phase 5 complete with full test coverage

## Related Documents

- **Route Timing**: `docs/ROUTE-TIMING-GUIDE.md`
- **Flight Status**: `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md`
- **POI System**: `backend/starlink-location/app/services/poi_manager.py`
- **Architecture**: `docs/design-document.md` section 2

---

**Last Updated**: 2025-11-10
**Created**: 2025-11-10
**Phase**: 1 Complete, 2-5 Planned
**Test Status**: 42/42 passing ✅
