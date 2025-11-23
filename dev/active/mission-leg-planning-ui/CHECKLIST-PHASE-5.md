# Checklist: Phase 5 - Satellite & AAR Configuration UI

**Branch:** `feat/mission-leg-planning-ui` **Folder:** `dev/active/mission-leg-planning-ui/` **Phase:** 5 - Satellite & AAR Configuration UI **Status:** Not Started

> Build the UI for satellite transitions/outages (X-Band, Ka, Ku/Starlink) and
> AAR segment editing with map visualization. Keep files < 350 lines and follow
> SOLID + strict TypeScript.

---

## Phase 5 Overview

**Goal:** Let users configure satellite transitions/outages per leg and define
air-to-air refueling (AAR) segments with map overlays.

**Exit Criteria:**

- X-Band configuration: starting satellite selector + transition table per leg
- Ka outage windows configurable
- Ku/Starlink outage windows configurable
- AAR segment editor: waypoint-based start/end selection
- Map shows transition points and AAR segments visually
- Form validation enforces data integrity

---

## 5.1: Define Types & Validation

- [ ] Add `frontend/mission-planner/src/types/satellite.ts` with interfaces for:
  - `SatelliteTransition` (id, name, start_at_iso, end_at_iso, notes, band)
  - `OutageWindow` (id, band, starts_at, ends_at, reason)
  - `AarSegment` (id, start_waypoint, end_waypoint, notes)
- [ ] Add Zod schemas in `frontend/mission-planner/src/lib/validation.ts` for
  transitions, outages, and AAR segments (ISO datetime strings, start < end,
  required IDs/names).
- [ ] Export type guards/types from `validation.ts` for reuse.

---

## 5.2: API Services

- [ ] Create `frontend/mission-planner/src/services/satellites.ts` with functions
  to load/save satellite config per mission leg (use `/api/v2/missions/{id}`
  payload shape; if backend endpoints are missing, stub with TODO and document
  expected request/response).
- [ ] Create `frontend/mission-planner/src/services/aar.ts` to load/save AAR
  segments per leg (same backend note as above).
- [ ] Ensure services use `apiClient` and return typed data.

---

## 5.3: React Query Hooks

- [ ] Add `useSatelliteConfig.ts` in `src/hooks/api/` with queries/mutations for
  transitions/outages per leg (cache key includes missionId + legId).
- [ ] Add `useAarSegments.ts` in `src/hooks/api/` with queries/mutations for AAR
  segments per leg.
- [ ] Invalidate relevant queries on mutation success.

---

## 5.4: UI Components – Satellite Config

- [ ] Create `src/components/satellites/XBandConfig.tsx`:
  - Selector for starting satellite
  - Table to add/edit/delete transition rows (name, start/end, notes)
  - Validation errors surfaced inline
- [ ] Create `src/components/satellites/KaOutages.tsx`:
  - List/table for outage windows with add/edit/delete
  - Uses validation schema; shows conflicts/error states
- [ ] Create `src/components/satellites/KuOutages.tsx`:
  - Same pattern as Ka, labeled Ku/Starlink outages
- [ ] Ensure each component stays < 350 lines; extract shared row editors to
  `src/components/satellites/common/` if needed.

---

## 5.5: UI Components – AAR Segment Editor

- [ ] Create `src/components/legs/AarSegmentEditor.tsx`:
  - Form fields: start_waypoint, end_waypoint, notes
  - List of existing segments with edit/delete
  - Uses React Hook Form + Zod resolver
- [ ] Ensure data flows through hooks (`useAarSegments`) and shows validation
  messages.

---

## 5.6: Map Visualization

- [ ] Add Leaflet overlays in `src/components/legs/LegMap.tsx` (or new map
  component) to render:
  - Transition markers/lines for X-Band (use distinct color)
  - Outage windows as time-bounded badges in a legend (no temporal animation)
  - AAR segment line between start/end waypoints (distinct color)
- [ ] Include simple legend and loading/error states.
- [ ] Keep component < 350 lines; extract helpers to `src/components/legs/map/`
  if needed.

---

## 5.7: Integrate into Missions Flow

- [ ] Add a Mission detail/leg detail page (`src/pages/MissionDetailPage.tsx`) to
  host satellite + AAR editors.
- [ ] Wire routing for `/missions/:missionId/legs/:legId` and link from
  MissionList/MissionsPage.
- [ ] Pass mission/leg context to hooks and components; ensure strict typing.

---

## 5.8: Validation & UX Polish

- [ ] Add form-level validation summaries and disable submit while pending.
- [ ] Prevent overlapping outage windows for the same band in the UI (basic
  check is acceptable).
- [ ] Provide toast or inline success/error feedback for mutations.

---

## 5.9: Testing

- [ ] Add unit tests (Vitest) for validation helpers in `src/lib/validation.ts`.
- [ ] Add component tests (React Testing Library) for one representative
  component (e.g., XBandConfig) covering add/edit/delete flows and validation
  errors.
- [ ] Keep each test file < 350 lines.

---

## 5.10: Manual Verification

- [ ] Start dev server:
  ```bash
  cd /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner && npm run dev
  ```
- [ ] Navigate to mission/leg detail page; configure:
  - Starting satellite + at least two X-Band transitions
  - One Ka outage window and one Ku/Starlink outage window
  - One AAR segment (start/end waypoints)
- [ ] Verify map shows transitions and AAR segment and that forms validate.

---

## 5.11: Commit & Push

- [ ] Stage and commit all Phase 5 changes with a message referencing Phase 5.
- [ ] Push branch:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Update `CHECKLIST-PHASE-5.md` with completed items as you go.

---

## Status

- [ ] Phase 5 not started
- [ ] Phase 5 in progress
- [ ] Phase 5 completed (meets exit criteria)

