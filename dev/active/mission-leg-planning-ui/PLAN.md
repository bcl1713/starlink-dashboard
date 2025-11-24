# Plan: Mission Leg Planning UI

**Branch:** `feat/mission-leg-planning-ui`
**Slug:** `mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Date:** 2025-11-24
**Owner:** brian
**Status:** Phases 1-6 complete + leg management + map fixes; frontend polish needed before Phase 7

---

## Executive Summary

This work introduces a hierarchical mission planning system where a **Mission** contains multiple **Mission Legs** (what are currently called "missions" in the codebase). Users will plan entire missions through a React-based web interface, configure satellite transitions and AAR segments for each leg, and export complete mission packages (including all legs, routes, POIs, and pre-generated documents) as zip files for portability across systems. The backend will be refactored to support this hierarchy while the new UI provides an intuitive wizard-style workflow. This enables mission planners to manage complex multi-leg operations as cohesive units rather than disconnected individual flights.

---

## Progress Updates (most recent first)

- **2025-11-24 — Critical fixes session:** Added missing leg management API endpoints (POST/PUT/DELETE), created AddLegDialog with improved UX, fixed LegDetailPage Save/Cancel buttons, fixed route display to use cleaned points array, implemented IDL crossing detection and segment splitting, fixed map bounds/center for IDL routes, normalized coordinates to 0-360 for Pacific-centered view. **Remaining:** AAR waypoints hardcoded (need route API integration), satellite list may be hardcoded (need verification), leg cards should be fully clickable.
- **2025-11-23 — Phase 6 completed:** Export/Import UI fully implemented with backend API integration. ExportDialog and ImportDialog components complete with progress indicators and drag-and-drop. Backend export/import endpoints fully functional and tested with complete roundtrip verification (export → delete → import → verify identical data).
- **2025-11-23 — Phase 5 completed:** Satellite & AAR configuration UI complete with X-Band transitions, Ka/Ku outages, AAR segment editor, and side-by-side map visualization.
- **2025-11-23 — Phase 4 completed:** Core mission UI in the React planner is working (missions list + create dialog), with API client, types, React Query hooks, routing, Tailwind, and ShadCN components wired to the v2 backend.
- **2025-11-23 — Phases 1-3 completed:** Backend models renamed to MissionLeg with new Mission container and hierarchical storage; v2 missions API and package export skeleton registered in FastAPI; frontend scaffolding created with Vite/TypeScript, ESLint/Prettier, Tailwind, and Docker Compose service.
- **Next focus:** Frontend polish (AAR waypoints, satellite management, leg card UX), then Phase 7 — Testing & Documentation.

---

## Objectives

The work will be complete when the following **testable outcomes** are achieved:

- **Mission hierarchy created**: Backend models distinguish between Mission (container) and MissionLeg (current Mission model renamed)
- **API endpoints functional**: New `/api/v2/missions` REST API supports CRUD operations for missions and nested legs
- **React UI operational**: Separate planning application allows users to create missions, add legs, configure satellites/AAR, and manage POIs
- **Batch export working**: Users can export an entire mission as a zip file containing all legs, routes, POIs, and pre-generated documents (PDF, XLSX, PPTX, CSV)
- **Import functional**: Users can upload a mission zip file on a different system and successfully recreate the entire mission with all assets
- **Satellite configuration complete**: UI supports X-Band starting satellite + transitions, Ka outages, and Ku/Starlink outages
- **AAR segments definable**: Users can specify AAR start/end waypoints for each leg
- **Documentation updated**: CLAUDE.md and API docs reflect new mission planning workflow

---

## Phases

### **Phase 1 — Backend Data Model Refactoring**

**Description:**
Rename existing `Mission` → `MissionLeg` and create new top-level `Mission` model. Update storage layer to support hierarchical structure (`data/missions/{mission_id}/mission.json` and `data/missions/{mission_id}/legs/{leg_id}.json`).

**Entry Criteria:**

- Scope locked
- Branch `feat/mission-leg-planning-ui` created
- Current codebase understood

**Exit Criteria:**

- All `Mission` references renamed to `MissionLeg` in models
- New `Mission` model created with `legs: List[MissionLeg]`
- Storage structure updated to support hierarchy
- Existing tests pass with renamed models
- All code committed and pushed

---

### **Phase 2 — Backend API Implementation**

**Description:**
Create new `/api/v2/missions` endpoints for mission management and nested leg operations. Implement export/import logic for mission packages.

**Entry Criteria:**

- Phase 1 complete
- Models and storage refactored

**Exit Criteria:**

- CRUD endpoints for missions working (`POST`, `GET`, `PUT`, `DELETE`)
- Nested leg endpoints functional (`/api/v2/missions/{id}/legs/...`)
- Export endpoint generates zip with all assets
- Import endpoint validates and reconstructs missions from zip
- Integration tests pass for all new endpoints
- OpenAPI docs updated

---

### **Phase 3 — Frontend Project Setup**

**Description:**
Initialize React application with Vite, set up routing, state management, and API client. Create basic UI shell with navigation.

**Entry Criteria:**

- Phase 2 complete
- Backend APIs available and tested

**Exit Criteria:**

- React project created in `frontend/mission-planner/`
- Dependencies installed (React Router, React Query, Material-UI, Leaflet)
- API client configured to call backend
- Basic routing structure in place
- App runs in development mode
- Docker configuration updated to serve frontend

---

### **Phase 4 — Core UI Components (Mission & Leg Management)**

**Description:**
Build mission list view, mission creation wizard, and leg management UI. Implement route upload and POI management per leg.

**Entry Criteria:**

- Phase 3 complete
- Frontend shell operational

**Exit Criteria:**

- Mission list view displays all missions with summary stats
- Mission creation wizard allows adding missions with multiple legs
- Each leg can have a route (KML upload) assigned
- POI management per leg functional
- Basic map visualization shows routes

---

### **Phase 5 — Satellite & AAR Configuration UI**

**Description:**
Implement satellite transition configuration (X-Band manual, Ka outages, Ku outages) and AAR segment definition UI with map visualization.

**Entry Criteria:**

- Phase 4 complete
- Core mission/leg CRUD working

**Exit Criteria:**

- X-Band configuration: starting satellite selector + transition table
- Ka outage windows configurable
- Ku/Starlink outage windows configurable
- AAR segment editor: waypoint-based start/end selection
- Map shows transition points and AAR segments visually
- Form validation ensures data integrity

---

### **Phase 6 — Export/Import UI & Integration**

**Description:**
Build export dialog allowing users to download mission packages, and import interface for uploading zips. Integrate with backend endpoints.

**Entry Criteria:**

- Phase 5 complete
- All configuration UIs operational

**Exit Criteria:**

- Export dialog triggers zip download with progress indicator
- Import drag-and-drop interface accepts zip files
- Import validation displays clear error messages
- Successful import recreates mission with all legs, routes, POIs
- Export package tested on separate system instance

---

### **Phase 7 — Testing & Documentation**

**Description:**
Write comprehensive tests for backend and frontend. Update project documentation with new workflows and examples.

**Entry Criteria:**

- Phase 6 complete
- All features implemented

**Exit Criteria:**

- Backend unit tests cover new models and endpoints (>80% coverage)
- Frontend component tests written
- E2E test covers full mission creation → export → import workflow
- CLAUDE.md updated with mission planning guide
- API documentation complete in OpenAPI spec
- User guide created with screenshots

---

### **Phase 8 — Wrap-Up & PR**

**Description:**
Finalize documentation, prepare PR, and hand off.

**Entry Criteria:**

- Phase 7 complete
- All tests passing

**Exit Criteria:**

- PLAN.md updated to "Completed"
- CONTEXT.md finalized
- CHECKLIST.md fully completed
- PR created and ready for review
