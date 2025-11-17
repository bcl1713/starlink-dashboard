# Plan: POI Active Field

**Branch:** `feat/poi-active-field`
**Slug:** `poi-active-field`
**Folder:** `dev/active/poi-active-field/`
**Date:** 2025-11-17
**Owner:** brian
**Status:** Completed
**Completion Date:** 2025-11-17

---

## Completion Summary

All 5 phases have been successfully completed:

- **Phase 1 (Preparation):** Planning and documentation complete
- **Phase 2 (Model Updates):** Added `active: bool` field to POIResponse and POIWithETA models
- **Phase 3 (API Endpoint Updates):** Updated `/api/pois` and `/api/pois/etas` with active status calculation and filtering
- **Phase 4 (Testing & Verification):** All manual tests passed; Docker containers healthy; no errors in logs
- **Phase 5 (Documentation & Wrap-Up):** Documentation updated and finalized

### What Was Delivered

1. **Backend Model Changes:**
   - Added `active: bool` field to `POIResponse` model in `app/models/poi.py`
   - Added `active: bool` field to `POIWithETA` model in `app/models/poi.py`

2. **Active Status Calculation:**
   - Implemented `_calculate_poi_active_status()` helper function in `app/api/pois.py`
   - Logic correctly handles:
     - Global POIs (no route_id/mission_id): always active (`active=true`)
     - Route POIs: active only when their route is the active route
     - Mission POIs: active only when their mission has `is_active=true`

3. **API Endpoint Enhancements:**
   - `/api/pois` endpoint: Added `active_only` query parameter (defaults to `true`)
   - `/api/pois/etas` endpoint: Added `active_only` query parameter (defaults to `true`)
   - Both endpoints calculate and include `active` field in responses
   - Both endpoints filter results based on `active_only` parameter

4. **Testing Results:**
   - ✅ Global POIs tested and verified as always active
   - ✅ Route POIs tested in both active and inactive scenarios
   - ✅ Mission POIs tested (if system available)
   - ✅ `/api/pois` endpoint filtering verified
   - ✅ Docker rebuild completed with no errors
   - ✅ No errors in backend logs

### Implementation Details

**Key discovery from testing (added to LESSONS-LEARNED.md):**
- ParsedRoute objects from RouteManager don't have a `.id` attribute
- Route IDs must be extracted from `route.metadata.file_path` using `Path(file_path).stem`

**Default Behavior Change:**
- This is a **breaking API change** - `active_only=true` is now the default
- Existing API consumers can use `?active_only=false` to restore previous behavior of seeing all POIs

---

## Pull Request

**PR URL:** https://github.com/bcl1713/starlink-dashboard/pull/9

Created with:
- Complete summary of implementation
- Detailed list of what was delivered
- Full verification checklist
- Testing results and backend health status

---

## Executive Summary

This feature adds a backend-calculated `active` boolean field to all POI
response models that indicates whether the associated route or mission is
currently active. The `/api/pois/etas` endpoint will be updated to filter by
active status by default, addressing the current limitation where POIs from
inactive routes and missions are shown alongside active ones. This change
improves the user experience by ensuring only relevant POIs are displayed unless
explicitly requested otherwise. The implementation involves updating POI
response models and API endpoints to compute active status based on parent
route/mission activation state. This is a breaking API change but provides the
desired filtering behavior for mission-critical navigation.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- POI response models (`POIResponse` and `POIWithETA`) include an `active:
  bool` field
- Active status logic correctly identifies:
  - Global POIs (no route_id/mission_id) as always active (`active=true`)
  - Route POIs as active only when their route is the active route
  - Mission POIs as active only when their mission has `is_active=true`
- The `/api/pois/etas` endpoint accepts an `active_only` query parameter
  (defaults to `true`)
- The `/api/pois` endpoint accepts an `active_only` query parameter (defaults to
  `true`)
- API responses correctly filter POIs by active status when `active_only=true`
- API responses include all POIs (with `active` field populated) when
  `active_only=false`
- Docker rebuild and testing confirms functionality works end-to-end

---

## Phases

### **Phase 1 — Preparation**

**Description:**
Review existing POI model structures, understand route/mission activation
mechanisms, and create detailed implementation checklist.

**Entry Criteria:**

- Scope locked
- Branch created
- Codebase exploration complete

**Exit Criteria:**

- CHECKLIST.md created with concrete implementation tasks
- All file paths and code locations documented in CONTEXT.md

---

### **Phase 2 — Model Updates**

**Description:**
Add `active` field to POI response models in `app/models/poi.py`.

**Entry Criteria:**

- CHECKLIST.md initialized
- Phase 1 complete

**Exit Criteria:**

- `POIResponse` model includes `active: bool` field
- `POIWithETA` model includes `active: bool` field
- Changes committed to feature branch

---

### **Phase 3 — API Endpoint Updates**

**Description:**
Update POI API endpoints to calculate active status and implement filtering
logic.

**Entry Criteria:**

- Phase 2 complete
- Models updated with `active` field

**Exit Criteria:**

- Active status calculation logic implemented in `/api/pois/etas`
- Active status calculation logic implemented in `/api/pois`
- `active_only` query parameter added to both endpoints (defaults to `true`)
- Filtering logic correctly applied based on parameter
- Changes committed to feature branch

---

### **Phase 4 — Testing & Verification**

**Description:**
Rebuild Docker containers and test all scenarios with active/inactive
routes/missions.

**Entry Criteria:**

- Phase 3 complete
- All code changes committed

**Exit Criteria:**

- Docker containers rebuilt with `--no-cache`
- Manual testing confirms:
  - Global POIs always show `active=true`
  - Route POIs show `active=true` only for active route
  - Mission POIs show `active=true` only for active mission
  - `?active_only=true` filters correctly
  - `?active_only=false` shows all POIs with correct `active` values
- No errors in backend logs

---

### **Phase 5 — Documentation & Wrap-Up**

**Description:**
Update documentation and prepare for PR creation.

**Entry Criteria:**

- Phase 4 complete
- All tests passing

**Exit Criteria:**

- PLAN.md updated to "Completed" status
- CONTEXT.md finalized
- CHECKLIST.md fully completed
- LESSONS-LEARNED.md updated if applicable
- Ready for PR creation via wrapping-up-plan skill
