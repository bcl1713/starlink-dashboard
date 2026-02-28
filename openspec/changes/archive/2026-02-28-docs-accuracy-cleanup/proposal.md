## Why

Project documentation has drifted significantly from the actual codebase. A comprehensive audit verified ~80+ doc files against code and found 6 critical inaccuracies (wrong metric names, nonexistent model references, incorrect file structures), 7 medium gaps (undocumented endpoints, boilerplate READMEs, broken links), and 3 minor staleness issues (outdated dates, test counts, version numbers). Developers and API consumers relying on these docs will encounter misleading information.

## What Changes

### Wave 1: Fix Inaccurate Content
- Fix `starlink_dish_altitude_meters` → `starlink_dish_altitude_feet` in `backend/docs/ARCHITECTURE.md` and `backend/VALIDATION.md` (config fields too: `altitude_min_meters` → `altitude_min_feet`)
- Fix `MissionTimeline` → `MissionLegTimeline` in `docs/data-structures/mission-timeline-models.md` and update field structures to match actual code
- Fix POI ETA response structure in `docs/api/poi/eta-endpoints.md` (flat array → wrapped response with `eta_mode`, `flight_phase`, `timestamp`; add missing fields)
- Fix route API file structure in `docs/route-api-implementation.md` (single `routes.py` → actual 8-file split in `/app/api/routes/`)
- Fix route endpoint count in `docs/route-api-endpoints.md` (8 → 12+ endpoints)
- Fix broken links in root `README.md` (`./docs/setup/grafana-setup.md`, `./CONTRIBUTING.md`, `./dev/STATUS.md` don't exist)
- Fix case-sensitive links in `backend/README.md` (`testing.md` → `TESTING.md`, `troubleshooting.md` → `TROUBLESHOOTING.md`)
- Fix broken `CONFIGURATION.md` reference in `backend/docs/GETTING-STARTED.md`

### Wave 2: Fill Documentation Gaps
- Document undocumented API endpoints: flight-status (5), GPS v2 (2), starlink-csv (1), POI stats (3), GeoJSON hemisphere variants (3), position-table (1)
- Replace boilerplate `frontend/mission-planner/README.md` with project-specific content
- Populate or remove empty root `CLAUDE.md`
- Update `MEMORY.md` with missing frontend deps (Zustand, React Router, React Hook Form, Zod, Playwright)
- Update POI models documentation with complete `POIWithETA` fields (`course_status`, `route_aware_status`, `projected_*`, `eta_type`, `is_pre_departure`)

### Wave 3: Freshen Stale Content
- Update version references (docs say "0.3.0", code says "0.2.0") to be consistent
- Update "Last Updated" dates across all docs (frozen at 2025-11-04)
- Update `docs/completed-features.md` with post-Nov-2025 features (missions, timeline preview, PPTX export, IDL handling, label collision, GPS control)
- Update test counts where referenced (original "451 tests" is stale)
- Fill in "TBD" purpose statements in OpenSpec living specs

## Capabilities

### New Capabilities

_None - this is a documentation-only change with no new features._

### Modified Capabilities

- `mission-export`: Spec baseline references PDF/XLSX formats that were removed; needs update to reflect CSV+PPTX only reality
- `export-performance`: Spec references cache logging messages at INFO level that aren't implemented; needs alignment

## Impact

- **Code**: No code changes. Documentation only.
- **Files affected**: ~30+ markdown files across `docs/`, `backend/starlink-location/`, `frontend/mission-planner/`, `openspec/specs/`, and project root
- **APIs**: No API changes, but API documentation will be corrected and expanded
- **Risk**: Zero runtime risk. All changes are documentation.
- **Dependencies**: None
