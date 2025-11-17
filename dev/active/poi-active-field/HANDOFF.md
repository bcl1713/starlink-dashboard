# Handoff Summary for poi-active-field

**Branch:** `feat/poi-active-field`
**Folder:** `dev/active/poi-active-field/`
**Generated:** 2025-11-17
**Status:** Planning Complete, Ready for Implementation

---

## Overview

This work adds a backend-calculated `active` boolean field to all POI response
models that indicates whether the associated route or mission is currently
active. The `/api/pois/etas` endpoint will be updated to filter by active
status by default (breaking change), ensuring only relevant POIs are displayed
to users. Global POIs (no route/mission association) are always active. Route
POIs are active only when their route is the active route. Mission POIs are
active only when their mission has `is_active=true`.

---

## Current Status

- **Phase:** Phase 1 (Preparation) Complete — Planning Done
- **Checklist completion:** 0% (Implementation starting)
- **Major accomplishments since last session:**
  - ✅ Completed codebase exploration and requirements gathering
  - ✅ Generated PLAN.md with 5 phases and clear objectives
  - ✅ Generated CONTEXT.md with all file locations and testing strategy
  - ✅ Generated CHECKLIST.md with detailed, junior-friendly tasks
  - ✅ Feature branch created and pushed to remote

---

## Next Actions

Follow these steps to implement the feature:

1. **Start Phase 2 (Model Updates):**
   - Continue with CHECKLIST.md → Section "Phase 2: Model Updates"
   - Task 2.1: Add `active: bool` field to `POIResponse` class in
     `backend/starlink-location/app/models/poi.py` (around line 141)
   - Task 2.2: Add `active: bool` field to `POIWithETA` class in same file
     (around line 204)
   - Task 2.3: Commit changes with message: `feat: add active field to POI
     response models`

2. **Move to Phase 3 (API Endpoint Updates):**
   - Create helper function `_calculate_poi_active_status()` in
     `backend/starlink-location/app/api/pois.py`
   - Update `/api/pois/etas` endpoint to accept `active_only: bool = True`
     query parameter
   - Update `/api/pois` endpoint to accept `active_only: bool = True` query
     parameter
   - Implement active status calculation and filtering logic for both endpoints
   - Commit changes with message: `feat: add active filtering to POI endpoints`

3. **Run Phase 4 (Testing & Verification):**
   - CRITICAL: Rebuild Docker with: `docker compose down && docker compose
     build --no-cache && docker compose up -d`
   - Verify containers are healthy: `docker compose ps`
   - Test all 7 scenarios in CHECKLIST.md (global, route active/inactive, mission
     active/inactive, parameter behavior)

4. **Complete Phase 5 (Wrap-Up):**
   - Update PLAN.md status to "Completed"
   - Finalize CONTEXT.md with any new learnings
   - Update LESSONS-LEARNED.md if anything surprising happened
   - Ensure all checklist items are checked off

---

## Risks / Questions / Notes

**Breaking API Change:**
- Setting `active_only=True` by default means existing API consumers will only
  see active POIs
- Mitigation: Parameter can be set to `false` to get all POIs
- Document this prominently in CHANGELOG and PR

**Implementation Detail:**
- Helper function needs access to RouteManager and MissionStorage instances
- Check how other endpoints in `pois.py` obtain these dependencies via FastAPI
  injection

**Testing Caveat:**
- Mission system testing may require having missions set up first
- If mission endpoints not available, focus on global and route POI testing

---

## References

- **PLAN.md:** `dev/active/poi-active-field/PLAN.md` — Full 5-phase plan
- **CONTEXT.md:** `dev/active/poi-active-field/CONTEXT.md` — Code locations,
  dependencies, testing strategy
- **CHECKLIST.md:** `dev/active/poi-active-field/CHECKLIST.md` — Detailed
  step-by-step implementation tasks
- **Branch:** `feat/poi-active-field`
- **Design context:**
  - `docs/design-document.md` (section 5 - POI system)
  - `CLAUDE.md` (Route Management, Mission Communication)
  - Previous feature: `dev/completed/mission-comm-planning/`
