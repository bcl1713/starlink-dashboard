## 1. Wave 1 — Fix Inaccurate Content

- [x] 1.1 Fix `starlink_dish_altitude_meters` → `starlink_dish_altitude_feet` and `altitude_min_meters` → `altitude_min_feet` in `backend/docs/ARCHITECTURE.md` and `backend/VALIDATION.md`
- [x] 1.2 Fix `MissionTimeline` → `MissionLegTimeline` in `docs/data-structures/mission-timeline-models.md` and update field structures to match actual code
- [x] 1.3 Fix POI ETA response structure in `docs/api/poi/eta-endpoints.md` (flat array → wrapped response with `eta_mode`, `flight_phase`, `timestamp`; add missing fields)
- [x] 1.4 Fix route API file structure in `docs/route-api-implementation.md` (single `routes.py` → actual 8-file split in `/app/api/routes/`)
- [x] 1.5 Fix route endpoint count in `docs/route-api-endpoints.md` (8 → 12+ endpoints)
- [x] 1.6 Fix broken links in root `README.md` (remove `./docs/setup/grafana-setup.md`, `./CONTRIBUTING.md`, `./dev/STATUS.md`)
- [x] 1.7 Fix case-sensitive links in `backend/README.md` (`testing.md` → `TESTING.md`, `troubleshooting.md` → `TROUBLESHOOTING.md`)
- [x] 1.8 Fix broken `CONFIGURATION.md` reference in `backend/docs/GETTING-STARTED.md`

## 2. Wave 2 — Fill Documentation Gaps

- [x] 2.1 Document undocumented API endpoints: flight-status (5), GPS v2 (2), starlink-csv (1), POI stats (3), GeoJSON hemisphere variants (3), position-table (1)
- [x] 2.2 Replace boilerplate `frontend/mission-planner/README.md` with project-specific content
- [x] 2.3 Populate or remove empty root `CLAUDE.md`
- [x] 2.4 Update `MEMORY.md` with missing frontend deps (Zustand, React Router, React Hook Form, Zod, Playwright)
- [x] 2.5 Update POI models documentation with complete `POIWithETA` fields (`course_status`, `route_aware_status`, `projected_*`, `eta_type`, `is_pre_departure`)

## 3. Wave 3 — Freshen Stale Content

- [x] 3.1 Update version references (docs say "0.3.0", code says "0.2.0") to be consistent
- [x] 3.2 Update "Last Updated" dates across all docs (frozen at 2025-11-04)
- [x] 3.3 Update `docs/completed-features.md` with post-Nov-2025 features (missions, timeline preview, PPTX export, IDL handling, label collision, GPS control)
- [x] 3.4 Update test counts where referenced (original "451 tests" is stale)
- [x] 3.5 Fill in "TBD" purpose statements in OpenSpec living specs

## 4. Spec Alignment — OpenSpec Living Specs

- [x] 4.1 Update `mission-export` spec: remove PDF/XLSX references from "Backward Compatibility" requirement (per delta spec)
- [x] 4.2 Update `export-performance` spec: fix "(XLSX, PPTX, PDF)" → "(CSV, PPTX)" in Route Map Caching scenario (per delta spec)
- [x] 4.3 Clean up stale PDF/XLSX references in API endpoint docstrings in `backend/starlink-location/app/mission/routes/operations.py`
