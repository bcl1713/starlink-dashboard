# Context for term-replacements

**Branch:** `chore/term-replacements`
**Folder:** `dev/active/term-replacements/`
**Last Updated:** 2025-11-22

---

## Background

The project uses communication band terminology that needs to be standardized:

- **HCX** (current) → **CommKa** (new): Refers to Ka-band satellite coverage for communication
- **WGS** (current) → **X-Band** (new): Refers to X-band satellite naming in test data and documentation
- **Starlink** references are intentionally preserved (too deeply embedded, will be migrated separately)

This change improves clarity and consistency in how communication bands are referenced throughout the system without affecting core infrastructure or functionality.

---

## Relevant Code Locations

### Files requiring WGS → X-Band changes (6 files):
- `backend/starlink-location/tests/unit/test_poi_manager.py` — POI test fixtures
- `backend/starlink-location/tests/unit/test_satellite_geometry.py` — Geometry test data
- `dev/completed/mission-comm-planning/mission-comm-planning-context.md` — Documentation
- `dev/completed/mission-comm-planning/STATUS.md` — Project status
- `dev/completed/mission-comm-planning/SESSION-NOTES.md` — Session notes

### Files requiring HCX → CommKa changes (31 files):

**Core Application:**
- `backend/starlink-location/main.py` — Service initialization
- `backend/starlink-location/app/satellites/kmz_importer.py` — Asset loading functions
- `backend/starlink-location/app/mission/timeline_service.py` — Label formatting
- `backend/starlink-location/app/mission/exporter.py` — Display constants
- `backend/starlink-location/app/satellites/catalog.py` — Coverage references
- `backend/starlink-location/app/satellites/coverage.py` — Comments
- `backend/starlink-location/app/satellites/__init__.py` — Exports

**Assets:**
- `data/sat_coverage/HCX.kmz` — Coverage file (rename to CommKa.kmz)

**Documentation (10 files):**
- `docs/MISSION-PLANNING-GUIDE.md`
- `docs/MISSION-DATA-QUICK-REFERENCE.md`
- `docs/MISSION-DATA-STRUCTURES.md`
- `docs/MISSION-VISUALIZATION-GUIDE.md`
- `monitoring/README.md`
- Various dev documentation files

**Configuration & Monitoring:**
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` — Overlay configuration

**Tests (3 files):**
- `backend/starlink-location/tests/unit/test_mission_exporter.py`
- `backend/starlink-location/tests/unit/test_kmz_importer.py`
- `backend/starlink-location/tests/integration/test_pois_quick_reference.py`

---

## Dependencies

- **Docker Compose:** Services must be restarted after file/code changes
- **Grafana:** Dashboard JSON may require reload
- **Prometheus:** Metrics names unchanged (starlink_ prefix preserved)
- **Python 3.x:** Backend code syntax validation required

---

## Constraints & Assumptions

- **WGS84 constants:** Scientific geodetic constants (`WGS84_SEMI_MAJOR_AXIS`, etc.) are preserved unchanged
- **Starlink references:** All Starlink terminology is intentionally preserved (will be handled in future phase)
- **File renames:** Asset files will be renamed (HCX.kmz → CommKa.kmz)
- **Function/variable names:** All code identifiers will be updated consistently
- **Backward compatibility:** Not required; clean break across codebase

---

## Risks

**Low Risk:**
- Test data updates — affects only test execution, not production code

**Medium Risk:**
- File renames — must update all references consistently to avoid broken imports
- Function name changes — must verify all callers updated correctly
- Configuration strings — incorrect updates could cause display issues

**Mitigation:**
- Use grep/rg to verify all occurrences found
- Test after each logical unit
- Keep commits focused and testable
- Run backend health checks after major changes

---

## Testing Strategy

Define exactly what "done and verified" means:

1. **Python Syntax Validation:**
   - Run `python -m py_compile` on all modified .py files
   - No syntax errors should occur

2. **Backend Health Check:**
   - Run services: `docker compose up -d`
   - Check health: `curl http://localhost:8000/health`
   - Verify response indicates "ok" status

3. **Documentation Verification:**
   - All markdown files render without errors
   - Links and references are still valid

4. **Grafana Display:**
   - Open Grafana: http://localhost:3000
   - Verify dashboard loads without errors
   - Check that overlay labels show "CommKa" instead of "HCX"

5. **Test Execution:**
   - Run pytest to ensure all tests pass with updated assertions

---

## References

- Search results: Found 29 WGS references, 164 HCX references, 2,438 Starlink references
- CLAUDE.md: Project instructions on backend workflow and code standards
- Planning context: User confirmed to preserve WGS84 constants and all Starlink references
