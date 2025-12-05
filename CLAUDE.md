# CLAUDE.md

Runtime development guidance for Claude Code. See README.md for project overview
and docs/ for comprehensive documentation.

## ⚠️ Backend Python Code Changes (CRITICAL)

**REQUIRED sequence for ANY .py file changes:**

```bash
docker compose down && docker compose build --no-cache && \
  docker compose up -d && docker compose ps
curl http://localhost:8000/health  # Verify changes took effect
```

**Why:** `docker compose up` alone serves cached code. Only the sequence above
rebuilds images without layer caching.

**Docker commands:** `up -d`, `down`, `logs -f`, `restart`, `ps`

## Module Quick Reference

**Backend structure** (refactored in Phase 001):

- API: `app/api/routes/`, `app/api/pois/`, `app/api/ui/`
- Mission: `app/mission/routes/`, `app/mission/timeline_builder/`,
  `app/mission/exporter/`, `app/mission/package/`
- Services: `app/services/kml/`, `app/services/eta/`,
  `app/services/route_eta/`, `app/services/poi_manager.py`,
  `app/services/flight_state_manager.py`
- Core: `app/core/metrics/`
- Data: `/data/routes/` (KML), `/data/sim_routes/` (simulator)

## Key References

- Project overview: `README.md`
- Architecture: `docs/architecture/design-document.md`
- Features & APIs: `docs/FEATURES-OVERVIEW.md`, `docs/API-REFERENCE-INDEX.md`
- Code standards: `.specify/memory/constitution.md`
- Setup: `docs/setup/quick-start.md`, `docs/setup/README.md`
- Development: `docs/development/workflow.md`

## Active Technologies

- Markdown (CommonMark specification) + ripgrep (rg) for search, git mv for
  preserving history (002-docs-cleanup)
- Filesystem-based markdown files in docs/ hierarchy (002-docs-cleanup)

## Recent Changes

- 002-docs-cleanup: Added Markdown (CommonMark specification) + ripgrep (rg) for
  search, git mv for preserving history
