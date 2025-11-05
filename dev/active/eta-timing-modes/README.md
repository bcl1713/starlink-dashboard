# ETA Timing Modes Implementation

**Feature:** Anticipated vs. Estimated ETA Display
**Status:** Planning Complete - Ready for Implementation
**Created:** 2025-11-04
**Effort Estimate:** XL (5-6 development sessions)

---

## Quick Start

This directory contains all planning materials for implementing the dual-mode ETA display feature.

### Documents in this Directory

1. **eta-timing-modes-plan.md** - Comprehensive strategic plan
   - Executive summary
   - Current state analysis
   - Implementation phases (8 phases)
   - Risk assessment
   - Success metrics
   - Timeline estimates

2. **eta-timing-modes-context.md** - Implementation context reference
   - Key file locations
   - Architectural decisions
   - Data flow diagrams
   - Dependencies
   - Debug/troubleshooting guides

3. **eta-timing-modes-tasks.md** - Task tracking checklist
   - Phase-by-phase task breakdown
   - Acceptance criteria for each task
   - Progress tracking checkboxes
   - Milestone tracking

4. **README.md** - This file (overview and navigation)

---

## Feature Overview

**Goal:** Automatically switch between displaying "Anticipated" ETAs (pre-departure, based on flight plan) and "Estimated" ETAs (post-departure, based on real-time telemetry).

**User Value:**
- See planned arrival times before takeoff
- Switch to real-time estimates after departure
- Clear visual distinction (blue = planned, green = live)
- No manual intervention required

---

## Implementation Approach

**Strategy:** Full implementation with flight phase tracking and state management

**8 Implementation Phases:**
1. Data Model Extensions (M)
2. Flight State Manager (L)
3. ETA Calculation Logic Enhancement (L)
4. API Endpoint Updates (M)
5. Prometheus Metrics Updates (M)
6. Grafana Dashboard Enhancements (L)
7. Testing and Validation (M)
8. Documentation and Deployment (S)

**Total Effort:** 26-34 hours (5-6 sessions)

---

## Key Technical Components

### New Files to Create (5)
- `app/models/flight_status.py` - Flight phase models
- `app/services/flight_state_manager.py` - State management
- `app/api/flight_status.py` - Flight status endpoints
- `tests/test_flight_state_manager.py` - Unit tests
- `dev/active/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` - User documentation

### Files to Modify (12)
- `app/models/route.py` - Add flight status fields
- `app/models/poi.py` - Add eta_type fields
- `app/services/eta_calculator.py` - Dual-mode calculation
- `app/core/eta_service.py` - Flight state integration
- `app/core/metrics.py` - New metrics
- `app/api/pois.py` - Include eta_type in responses
- `app/api/routes.py` - Flight status in responses
- `main.py` - Initialize FlightStateManager
- `monitoring/grafana/.../poi-management.json` - Dashboard updates
- `monitoring/grafana/.../fullscreen-overview.json` - Flight status panel
- `docs/ROUTE-TIMING-GUIDE.md` - Add ETA modes section
- `CLAUDE.md` - Add flight status management section

---

## State Machine Overview

```
PRE_DEPARTURE → IN_FLIGHT → POST_ARRIVAL
    ↓                            ↓
    └────────────────────────────┘
           (reset)
```

**Transitions:**
- PRE_DEPARTURE → IN_FLIGHT: Automatic (time or distance) or manual
- IN_FLIGHT → POST_ARRIVAL: Automatic (final waypoint) or manual
- POST_ARRIVAL → PRE_DEPARTURE: Manual reset only

---

## Getting Started with Implementation

### Step 1: Read the Plan
```bash
cat eta-timing-modes-plan.md
```
Start with the Executive Summary and Current State Analysis.

### Step 2: Review Context
```bash
cat eta-timing-modes-context.md
```
Understand key files, decisions, and dependencies.

### Step 3: Begin Phase 1
```bash
cat eta-timing-modes-tasks.md
```
Follow the checklist starting with Phase 1, Task 1.1.

### Step 4: Track Progress
Update checkboxes in `eta-timing-modes-tasks.md` as you complete tasks.

---

## Development Workflow Reminder

**CRITICAL:** After modifying any Python file, ALWAYS run:
```bash
docker compose down && docker compose build --no-cache && docker compose up -d
```

Failure to rebuild will result in running old code.

---

## Testing Strategy

### Test Coverage Goals
- FlightStateManager: 15+ tests
- ETACalculator: 20+ tests
- Models: 10+ tests
- API Endpoints: 15+ tests
- Integration: Full scenarios

**Total:** 451 existing tests + 60 new tests = **511 tests**

### Performance Targets
- ETA calculation: <50ms per POI
- Flight state check: <1ms per cycle
- API response: <100ms (95th percentile)

---

## Success Criteria

### Functional
- ✅ Automatic mode switching (no manual intervention)
- ✅ 100% test coverage for new code
- ✅ Zero breaking changes to existing APIs
- ✅ <5% performance overhead

### User Experience
- ✅ Visual clarity: Blue (planned) vs. Green (live)
- ✅ Dashboard load time: <2 seconds
- ✅ Mode switch latency: <1 second

### Technical
- ✅ Thread-safe state management
- ✅ Graceful degradation (no timing data)
- ✅ Comprehensive documentation

---

## Key Decisions Made

1. **In-Memory State:** No database persistence (acceptable trade-off)
2. **Automatic Departure Detection:** Time-based (5 min buffer) + distance-based (1000m)
3. **Dual-Mode in Single Class:** Keep ETA logic centralized
4. **Optional Fields:** All new API fields optional for backward compatibility
5. **Metric Labels:** Add eta_type label, don't create new metrics

See `eta-timing-modes-context.md` for detailed rationale.

---

## Dependencies

### Prerequisites
- Phase 0 complete (design docs)
- Existing route timing feature working (Session 28)
- Docker environment functional
- Prometheus + Grafana running

### External Dependencies
- Python 3.11+
- FastAPI 0.100+
- Pydantic 2.0+
- Prometheus client
- Grafana 10.0+

---

## Timeline Estimate

### By Phase (Hours)
| Phase | Effort | Hours |
|-------|--------|-------|
| 1. Models | M | 2-3 |
| 2. State Manager | L | 4-5 |
| 3. ETA Calculation | L | 5-6 |
| 4. API Updates | M | 3-4 |
| 5. Metrics | M | 2-3 |
| 6. Dashboard | L | 4-5 |
| 7. Testing | M | 4-5 |
| 8. Documentation | S | 2-3 |
| **Total** | **XL** | **26-34** |

### By Session (Assuming 4-6 hours/session)
- Session 1: Phases 1-2 (Models + State Manager)
- Session 2: Phase 3 (ETA Calculation)
- Session 3: Phases 4-5 (API + Metrics)
- Session 4: Phase 6 (Dashboard)
- Session 5: Phase 7 (Testing)
- Session 6: Phase 8 + Buffer (Docs + Contingency)

---

## Risk Mitigation

### Top Risks Identified
1. **Breaking Changes:** Mitigated by optional fields and versioning
2. **Performance:** Mitigated by benchmarking and caching
3. **State Sync:** Mitigated by thread-safe singleton pattern
4. **Dashboard Complexity:** Mitigated by query testing and documentation
5. **Timing Data Dependency:** Mitigated by graceful degradation

See full risk assessment in `eta-timing-modes-plan.md`.

---

## Questions or Issues?

### Resources
- **Plan:** `eta-timing-modes-plan.md` (comprehensive strategy)
- **Context:** `eta-timing-modes-context.md` (quick reference)
- **Tasks:** `eta-timing-modes-tasks.md` (progress tracking)

### Related Documentation
- `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md` - ETA system architecture
- `docs/ROUTE-TIMING-GUIDE.md` - Route timing feature
- `CLAUDE.md` - Project instructions

---

## Progress Tracking

### Current Status
- [x] Planning complete
- [ ] Implementation started
- [ ] Phase 1 complete
- [ ] Phase 2 complete
- [ ] Phase 3 complete
- [ ] Phase 4 complete
- [ ] Phase 5 complete
- [ ] Phase 6 complete
- [ ] Phase 7 complete
- [ ] Phase 8 complete
- [ ] Feature deployed

### Last Updated
**Date:** 2025-11-04
**Status:** Planning Complete - Ready for Implementation
**Next Step:** Begin Phase 1 (Data Model Extensions)

---

**Plan Version:** 1.0.0
**Created By:** Claude Code Strategic Planning Agent
