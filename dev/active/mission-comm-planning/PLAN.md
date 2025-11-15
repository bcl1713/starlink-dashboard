# Plan: Mission Communication Planning

**Branch:** `feature/mission-comm-planning`
**Slug:** `mission-comm-planning`
**Folder:** `dev/active/mission-comm-planning/`
**Date:** 2025-11-14
**Owner:** starlink-dashboard team
**Status:** In Progress

---

## Executive Summary

The mission communication planning feature enables pre-flight mission planning that predicts communication degradation across three onboard satellite transports (X-Band, HCX/Ka, StarShield/Ku) by analyzing timed flight routes, satellite geometries, and operational constraints. Phases 1–3 (data foundations, satellite geometry, timeline engine) are complete with full backend implementation, APIs, and Prometheus metrics. Phase 4 (Grafana visualization and alerting) is in progress, followed by Phase 5 (hardening and documentation). This work directly enables mission planners to predict communication windows and export timeline briefings for operations teams.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- **Phase 3 complete:** Timeline computation, export generators (CSV/XLSX/PDF), and mission-event POI synchronization fully integrated and tested with 607+ passing tests.
- **Phase 4 complete:** Grafana dashboard overlays (satellite POIs, coverage footprints, AAR markers) and mission timeline panel displaying nominal/degraded/critical segments with real-time updates.
- **Phase 5 complete:** Scenario regression tests, performance benchmarks (<1s recompute for 10 concurrent missions), comprehensive documentation, and operational SOP.
- **All phases verified:** End-to-end mission workflows (create → activate → view timeline → export briefing) work without errors in Docker environment.
- **Documentation finalized:** MISSION-PLANNING-GUIDE.md, MISSION-COMM-SOP.md, and Grafana instructions complete and linked from project README.

---

## Phases

### **Phase 1 — Mission Data Foundations** ✅ COMPLETE

**Description:**
Establish foundational data models, storage layer, CRUD APIs, and metrics for mission planning. This phase delivered Pydantic models for missions, transports, and timelines; portable flat-file storage; REST endpoints; and Prometheus metrics.

**Entry Criteria:**

- Scope locked
- Branch created (`feature/mission-comm-planning`)

**Exit Criteria:**

- Mission data models (9 Pydantic models) with validation
- Storage layer with JSON persistence and checksums
- CRUD endpoints (POST/GET/PUT/DELETE/activate) working
- Mission planner GUI implemented at `/ui/mission-planner`
- 87+ unit tests passing (models + storage + metrics)
- Mission POI system with mission_id scoping

---

### **Phase 2 — Satellite Geometry & Constraint Engine** ✅ COMPLETE

**Description:**
Build satellite catalog system, azimuth/elevation geometry calculations, coverage sampling, and rule engine for constraint evaluation. Includes HCX KMZ ingestion with IDL-aware polygon handling.

**Entry Criteria:**

- Phase 1 complete
- Satellite data (HCX KMZ) available

**Exit Criteria:**

- Satellite catalog module with X/Ka/Ku definitions
- Azimuth/elevation calculations (<5ms per operation)
- Ka coverage sampler with IDL awareness
- Rule engine producing MissionEvent streams
- 75+ dedicated unit tests (geometry, catalog, coverage, rules)
- All modules properly exported and integrated

---

### **Phase 3 — Communication Timeline Engine** ✅ COMPLETE

**Description:**
Implement transport availability state machine, timeline segmentation logic, and export generators (CSV/XLSX/PDF). Includes automatic POI synchronization for HCX/X-Band/AAR markers and Prometheus metric exposure.

**Entry Criteria:**

- Phase 2 complete
- Timed KML routes available

**Exit Criteria:**

- Transport availability state machine tracking X/Ka/Ku states
- Timeline segmentation producing ordered TimelineSegment objects
- Export generators with timezone-aware formatting (UTC/Eastern/T+)
- `/api/missions/{id}/timeline` endpoint returning structured JSON
- Mission-event POIs auto-generated and de-duped
- Prometheus metrics (`mission_comm_state`, `mission_degraded_seconds`, etc.)
- 100+ integration tests validating end-to-end flows
- All formats (CSV, XLSX, PDF) tested and verified

---

### **Phase 4 — Visualization & Customer Outputs** ⏳ IN PROGRESS

**Description:**
Wire mission data into Grafana dashboards with satellite POI overlays, coverage footprints, AAR markers, and mission timeline panel. Configure Prometheus/Grafana alerts for upcoming degraded windows. Add mission deactivation capability and route cascade cleanup. Validate UX with stakeholders.

**Entry Criteria:**

- Phase 3 complete
- `/api/missions/active/timeline` and POI endpoints stable
- HCX/X-Band/AAR POI generation working

**Exit Criteria:**

- Fullscreen Overview dashboard updated with satellite layers
- Mission timeline panel (State Timeline viz) operational
- Prometheus alert rules (`mission-alerts.yml`) firing correctly
- Mission deactivation endpoint implemented with route cascade
- Mission planner UI includes deactivation button
- Grafana variables updated for mission context
- UX validation session completed with stakeholder feedback
- Docs/screenshots captured in SESSION-NOTES.md

---

### **Phase 5 — Hardening & Ops Readiness** ⏳ PENDING

**Description:**
Add scenario regression tests, benchmark timeline performance, finalize documentation, create operational SOP, and ensure production readiness.

**Entry Criteria:**

- Phase 4 complete
- All APIs and metrics stable

**Exit Criteria:**

- 3+ scenario-based pytest cases covering normal ops, AAR, Ka coverage gaps, Ku outages
- Performance benchmarks run and documented (target: <1s for 10 missions)
- MISSION-PLANNING-GUIDE.md and MISSION-COMM-SOP.md complete
- Root README.md and docs/INDEX.md updated with links
- All tests passing in CI
- No outstanding TODOs or documentation gaps

---

## Success Criteria

- All five phases complete with documented acceptance criteria met
- 700+ passing tests across unit and integration suites
- Docker build succeeds without warnings
- Timeline export accuracy within ±2 minutes of expected transitions
- 100% detection of forbidden azimuth windows
- Mission planner workflow completable in <10 minutes
- All timestamps correctly formatted in UTC/Eastern/T+
- Grafana dashboards displaying real-time mission state
- Operations team can respond to alerts within <15 seconds
