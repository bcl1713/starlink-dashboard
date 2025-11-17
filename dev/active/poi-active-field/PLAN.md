# Plan: POI Active Field

**Branch:** `feat/poi-active-field`
**Slug:** `poi-active-field`
**Folder:** `dev/active/poi-active-field/`
**Date:** 2025-11-17
**Owner:** brian
**Status:** Planning

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
