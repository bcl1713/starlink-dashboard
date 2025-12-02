# Smoke Test Checklist

**Feature**: 001-codebase-cleanup **Created**: 2025-12-02 **Version**: 1.0

## Overview

This document provides standardized smoke test procedures for verifying that
refactored code maintains behavioral equivalence with the original
implementation. These tests fulfill the manual verification requirement
specified in the `spec.md` clarifications: "Manual smoke testing per PR to
verify behavior unchanged."

Smoke tests are **required** for every PR before approval and merge. They serve
as the primary mechanism to detect regressions when automated test coverage is
insufficient.

---

## 1. General Testing Principles

### When to Perform Smoke Tests

- **Required**: After completing refactoring work, before creating PR
- **Required**: After reviewer requests changes and author pushes updates
- **Required**: If CI passes but reviewer wants manual verification

### Test Execution Environment

- **Docker**: All tests MUST be run against the Dockerized environment to match
  production
- **Mode**: Use simulation mode (`STARLINK_MODE=simulation`) for consistent,
  reproducible results
- **State**: Start with clean state (restart Docker containers before testing)

### Test Recording

All smoke test results MUST be documented in the PR description using the
following format:

```markdown
## Smoke Test Results

**Test Category**: [Backend API / Frontend Component / Documentation]
**Tested By**: [Your Name/Handle] **Date**: [YYYY-MM-DD] **Environment**:
Docker (simulation mode)

### Tests Performed

- [x] Test 1 name - PASSED
- [x] Test 2 name - PASSED
- [ ] Test 3 name - FAILED (details below)

### Failure Details

[If any tests failed, provide detailed information here]

### Verification Evidence

[Optional: Screenshots, curl output, or log excerpts demonstrating passing
tests]
```

---

## 2. Backend API Smoke Tests

Use these checklists when refactoring Python backend files in
`backend/starlink-location/app/`.

### 2.1 Core Health and Status Checks

**Applies to**: Any refactoring in `app/main.py`, `app/core/`, or
`app/services/`

**Prerequisites**:

```bash
docker compose down && docker compose build --no-cache && docker compose up -d
# Wait for containers to be healthy (check with: docker compose ps)
```

**Test Steps**:

1. **Health Endpoint Responds**

   ```bash
   curl http://localhost:8000/health
   ```

   **Expected**: HTTP 200 with JSON response including:

   ```json
   {
     "status": "ok",
     "mode": "simulation",
     ...
   }
   ```

   **Result**: [ ] PASSED [ ] FAILED

2. **Prometheus Metrics Endpoint Responds**

   ```bash
   curl http://localhost:8000/metrics
   ```

   **Expected**: HTTP 200 with Prometheus text format (starts with `# HELP`)

   **Result**: [ ] PASSED [ ] FAILED

3. **API Docs Endpoint Responds**

   ```bash
   curl http://localhost:8000/docs
   ```

   **Expected**: HTTP 200 with HTML content (OpenAPI/Swagger UI)

   **Result**: [ ] PASSED [ ] FAILED

4. **Container Logs Show No Errors**

   ```bash
   docker logs starlink-location --tail 50
   ```

   **Expected**: No `ERROR` or `CRITICAL` level logs; INFO logs show successful
   startup

   **Result**: [ ] PASSED [ ] FAILED

---

### 2.2 Route Management API Checks

**Applies to**: Refactoring `app/api/routes.py`, `app/services/kml_parser.py`,
`app/services/route_eta_calculator.py`

**Prerequisites**: Ensure sample routes exist in `/data/sample_routes/`
(already present in repo)

**Test Steps**:

1. **List All Routes**

   ```bash
   curl http://localhost:8000/api/routes
   ```

   **Expected**: HTTP 200 with JSON array of routes (may be empty initially)

   **Result**: [ ] PASSED [ ] FAILED

2. **Upload a Sample Route**

   ```bash
   curl -X POST \
     -F "file=@data/sample_routes/simple-circular.kml" \
     http://localhost:8000/api/routes/upload
   ```

   **Expected**: HTTP 201 with JSON response containing `route_id` and success
   message

   **Result**: [ ] PASSED [ ] FAILED

3. **Get Route Details**

   ```bash
   # Use route_id from previous step
   curl http://localhost:8000/api/routes/{route_id}
   ```

   **Expected**: HTTP 200 with JSON object containing route metadata (waypoint
   count, distance, etc.)

   **Result**: [ ] PASSED [ ] FAILED

4. **Activate Route**

   ```bash
   curl -X POST http://localhost:8000/api/routes/{route_id}/activate
   ```

   **Expected**: HTTP 200 with success message

   **Result**: [ ] PASSED [ ] FAILED

5. **Verify Route Metrics in Prometheus**

   ```bash
   curl 'http://localhost:9090/api/v1/query?query=starlink_route_progress_percent'
   ```

   **Expected**: HTTP 200 with JSON response; `result[0].value[1]` shows
   progress percentage (0-100)

   **Result**: [ ] PASSED [ ] FAILED

6. **Download Route KML**

   ```bash
   curl -O http://localhost:8000/api/routes/{route_id}/download
   ```

   **Expected**: HTTP 200 with KML file downloaded; file is valid XML

   **Result**: [ ] PASSED [ ] FAILED

7. **Delete Route**

   ```bash
   curl -X DELETE http://localhost:8000/api/routes/{route_id}
   ```

   **Expected**: HTTP 204 (no content) or HTTP 200 with success message

   **Result**: [ ] PASSED [ ] FAILED

---

### 2.3 POI Management API Checks

**Applies to**: Refactoring `app/api/pois.py`, `app/services/poi_manager.py`

**Prerequisites**: Have at least one active route (see 2.2 steps 2-4)

**Test Steps**:

1. **List All POIs**

   ```bash
   curl http://localhost:8000/api/pois
   ```

   **Expected**: HTTP 200 with JSON array of POIs (may be empty)

   **Result**: [ ] PASSED [ ] FAILED

2. **Create a POI**

   ```bash
   curl -X POST http://localhost:8000/api/pois \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Waypoint",
       "latitude": 37.7749,
       "longitude": -122.4194,
       "altitude_meters": 100
     }'
   ```

   **Expected**: HTTP 201 with JSON response containing `poi_id`

   **Result**: [ ] PASSED [ ] FAILED

3. **Get POI Details**

   ```bash
   curl http://localhost:8000/api/pois/{poi_id}
   ```

   **Expected**: HTTP 200 with JSON object containing POI data

   **Result**: [ ] PASSED [ ] FAILED

4. **Get POI ETAs (with active route)**

   ```bash
   curl http://localhost:8000/api/pois/etas
   ```

   **Expected**: HTTP 200 with JSON array; each POI has `eta_seconds`,
   `distance_meters`, `eta_type`, `flight_phase`

   **Result**: [ ] PASSED [ ] FAILED

5. **Update POI**

   ```bash
   curl -X PUT http://localhost:8000/api/pois/{poi_id} \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Updated Waypoint",
       "latitude": 37.7749,
       "longitude": -122.4194
     }'
   ```

   **Expected**: HTTP 200 with updated POI data

   **Result**: [ ] PASSED [ ] FAILED

6. **Delete POI**

   ```bash
   curl -X DELETE http://localhost:8000/api/pois/{poi_id}
   ```

   **Expected**: HTTP 204 or HTTP 200 with success message

   **Result**: [ ] PASSED [ ] FAILED

---

### 2.4 Mission Planning API Checks

**Applies to**: Refactoring `app/mission/routes.py`, `app/mission/routes_v2.py`,
`app/mission/timeline_service.py`, `app/mission/exporter.py`,
`app/mission/package_exporter.py`

**Test Steps**:

1. **List Missions**

   ```bash
   curl http://localhost:8000/api/missions
   ```

   **Expected**: HTTP 200 with JSON array (may be empty)

   **Result**: [ ] PASSED [ ] FAILED

2. **Create Mission (if endpoint exists)**

   ```bash
   curl -X POST http://localhost:8000/api/missions \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Mission",
       "description": "Smoke test"
     }'
   ```

   **Expected**: HTTP 201 with `mission_id` (or 404 if not implemented)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

3. **Get Mission Details**

   ```bash
   curl http://localhost:8000/api/missions/{mission_id}
   ```

   **Expected**: HTTP 200 with mission data (or 404 if none exist)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

4. **Export Mission (if endpoint exists)**

   ```bash
   curl http://localhost:8000/api/missions/{mission_id}/export
   ```

   **Expected**: HTTP 200 with exported file (KML, JSON, or package)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

5. **Get Flight Status**

   ```bash
   curl http://localhost:8000/api/flight-status
   ```

   **Expected**: HTTP 200 with JSON containing `flight_phase`, `eta_mode`,
   `time_until_departure_seconds`

   **Result**: [ ] PASSED [ ] FAILED

6. **Trigger Departure (Manual Override)**

   ```bash
   curl -X POST http://localhost:8000/api/flight-status/depart
   ```

   **Expected**: HTTP 200 with confirmation; subsequent `/api/flight-status`
   shows `flight_phase: in_flight`

   **Result**: [ ] PASSED [ ] FAILED

7. **Trigger Arrival (Manual Override)**

   ```bash
   curl -X POST http://localhost:8000/api/flight-status/arrive
   ```

   **Expected**: HTTP 200 with confirmation; `/api/flight-status` shows
   `flight_phase: post_arrival`

   **Result**: [ ] PASSED [ ] FAILED

---

### 2.5 UI HTML Endpoints Checks

**Applies to**: Refactoring `app/api/ui.py` (the 3995-line file)

**Test Steps**:

1. **Route Management UI**

   Open in browser: `http://localhost:8000/ui/routes`

   **Expected**: HTML page loads with route management interface (list, upload
   form, activate buttons)

   **Result**: [ ] PASSED [ ] FAILED

2. **POI Management UI**

   Open in browser: `http://localhost:8000/ui/pois`

   **Expected**: HTML page loads with POI management interface

   **Result**: [ ] PASSED [ ] FAILED

3. **Mission Planning UI** (if exists)

   Open in browser: `http://localhost:8000/ui/missions`

   **Expected**: HTML page loads (or 404 if not implemented)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

4. **Dashboard/Home UI** (if exists)

   Open in browser: `http://localhost:8000/` or `http://localhost:8000/ui`

   **Expected**: HTML page loads with navigation or dashboard

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

## 3. Frontend Component Smoke Tests

Use these checklists when refactoring TypeScript/React files in
`frontend/mission-planner/src/`.

### 3.1 Core Page Load Checks

**Applies to**: Any refactoring in `pages/`, `components/`, or `App.tsx`

**Prerequisites**:

```bash
cd frontend/mission-planner
npm install
npm start
# Wait for dev server to start (typically http://localhost:3000)
```

**Test Steps**:

1. **Home Page Loads Without Errors**

   Open in browser: `http://localhost:3000/`

   **Expected**: Page loads successfully; no console errors in browser DevTools

   **Result**: [ ] PASSED [ ] FAILED

2. **Navigation Works**

   Click through main navigation links

   **Expected**: All linked pages load without errors; no blank screens

   **Result**: [ ] PASSED [ ] FAILED

3. **No TypeScript Compilation Errors**

   Check terminal running `npm start`

   **Expected**: No TypeScript errors shown; only "Compiled successfully" message

   **Result**: [ ] PASSED [ ] FAILED

---

### 3.2 Route Map Component Checks

**Applies to**: Refactoring `components/common/RouteMap.tsx` (482 lines)

**Test Steps**:

1. **Map Renders on Page Load**

   Open page containing RouteMap component

   **Expected**: Map tiles load; no blank map area

   **Result**: [ ] PASSED [ ] FAILED

2. **Map Controls Work**

   Interact with zoom buttons, pan map by dragging

   **Expected**: Map responds to controls; smooth interaction

   **Result**: [ ] PASSED [ ] FAILED

3. **Route Displays on Map (if active route exists)**

   With an active route in backend, verify map shows route

   **Expected**: Route line appears on map in expected color (dark orange per
   docs)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

4. **Current Position Marker Displays**

   Verify current position marker shows on map

   **Expected**: Marker (green plane icon per docs) visible on map

   **Result**: [ ] PASSED [ ] FAILED

5. **POI Markers Display (if POIs exist)**

   With POIs in backend, verify markers show on map

   **Expected**: POI markers appear at correct locations

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

### 3.3 Leg Detail Page Checks

**Applies to**: Refactoring `pages/LegDetailPage.tsx` (379 lines)

**Test Steps**:

1. **Page Loads for Valid Leg ID**

   Navigate to `/legs/{leg_id}` (replace with actual ID from backend)

   **Expected**: Page loads with leg details; no errors

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

2. **Leg Data Displays Correctly**

   Verify leg name, start/end locations, distance, ETA, etc., are shown

   **Expected**: All expected fields populated with data

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

3. **Edit Leg Functionality (if present)**

   Click "Edit" button (if exists) and modify leg data

   **Expected**: Edit form opens; changes save successfully

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

4. **Delete Leg Functionality (if present)**

   Click "Delete" button and confirm deletion

   **Expected**: Leg deleted; redirected to legs list

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

### 3.4 Satellite Manager Page Checks

**Applies to**: Refactoring `pages/SatelliteManagerPage.tsx` (359 lines)

**Test Steps**:

1. **Page Loads Successfully**

   Navigate to `/satellites` (or equivalent route)

   **Expected**: Page loads; satellite list or manager interface visible

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

2. **Satellite List Displays**

   Verify list of satellites (if any) is shown

   **Expected**: Table/list of satellites with names, statuses, etc.

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

3. **Add Satellite Functionality (if present)**

   Click "Add Satellite" button and fill form

   **Expected**: New satellite created and appears in list

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

4. **Satellite Status Updates (if real-time)**

   Observe satellite statuses for updates (if live data)

   **Expected**: Statuses update periodically (if implemented)

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

## 4. Documentation Smoke Tests

Use these checklists when refactoring Markdown files in `docs/`.

### 4.1 Link Validation

**Applies to**: Any refactoring of Markdown documentation files

**Prerequisites**:

```bash
npm install -g markdown-link-check@3.12.1
```

**Test Steps**:

1. **Internal Links Resolve**

   ```bash
   markdown-link-check docs/REFACTORED_FILE.md --quiet
   ```

   **Expected**: Exit code 0; no broken internal links reported

   **Result**: [ ] PASSED [ ] FAILED

2. **Manual Link Click-Through (for split documents)**

   If document was split into multiple files, manually click all links between
   sections

   **Expected**: All links navigate to correct sections/files

   **Result**: [ ] PASSED [ ] FAILED

---

### 4.2 Build Verification (if using doc generator)

**Applies to**: If project uses a documentation generator (e.g., MkDocs, Docusaurus)

**Test Steps**:

1. **Docs Build Successfully**

   ```bash
   # Example for MkDocs:
   mkdocs build --strict

   # Example for Docusaurus:
   cd docs-site && npm run build
   ```

   **Expected**: Build completes without errors

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

2. **Generated Docs Display Correctly**

   Open built documentation in browser

   **Expected**: All pages render correctly; no missing content

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

### 4.3 Code Example Validation

**Applies to**: Documentation containing code snippets or examples

**Test Steps**:

1. **Code Examples Execute Successfully**

   Copy code examples from documentation and execute them (for bash commands, API
   calls)

   ```bash
   # Example: Test a curl command from docs
   curl http://localhost:8000/health
   ```

   **Expected**: Commands work as documented; outputs match documentation

   **Result**: [ ] PASSED [ ] FAILED

2. **Configuration Examples Are Valid**

   If documentation includes config file snippets (e.g., `.env`, YAML), validate
   syntax

   ```bash
   # Example for YAML:
   yamllint example-config.yaml
   ```

   **Expected**: No syntax errors

   **Result**: [ ] PASSED [ ] FAILED [ ] N/A

---

## 5. Smoke Test Failure Response

### If Any Test Fails

1. **Do NOT create the PR yet** (or mark PR as draft if already created)
2. **Document the failure**: Record which test failed and exact error/symptoms
3. **Investigate root cause**: Use logs, debugger, or additional manual testing
4. **Fix the issue**: Modify refactored code to restore correct behavior
5. **Re-run all smoke tests**: Ensure fix didn't break other functionality
6. **Only proceed to PR when all tests pass**

### If Failure is in Original Code (Not Caused by Refactoring)

- Document that the failure exists in the original code before refactoring
- Create a separate GitHub issue to track the bug
- Note in PR description: "Pre-existing bug documented in issue #XXX; not
  introduced by this refactoring"
- Proceed with PR if refactoring didn't worsen the bug

---

## 6. Smoke Test Templates for PRs

### Backend API Refactor Template

```markdown
## Smoke Test Results

**Test Category**: Backend API **Tested By**: [Your Name] **Date**: 2025-12-02
**Environment**: Docker (simulation mode) **Files Modified**:
`backend/starlink-location/app/api/routes.py`

### Core Health Checks

- [x] Health endpoint responds - PASSED
- [x] Prometheus metrics endpoint responds - PASSED
- [x] API docs endpoint responds - PASSED
- [x] Container logs show no errors - PASSED

### Route Management API Checks

- [x] List all routes - PASSED
- [x] Upload sample route - PASSED
- [x] Get route details - PASSED
- [x] Activate route - PASSED
- [x] Verify route metrics in Prometheus - PASSED
- [x] Download route KML - PASSED
- [x] Delete route - PASSED

**Overall Result**: ALL TESTS PASSED ✅
```

### Frontend Component Refactor Template

```markdown
## Smoke Test Results

**Test Category**: Frontend Component **Tested By**: [Your Name] **Date**:
2025-12-02 **Environment**: Local dev server (npm start) **Files Modified**:
`frontend/mission-planner/src/components/common/RouteMap.tsx`

### Core Page Load Checks

- [x] Home page loads without errors - PASSED
- [x] Navigation works - PASSED
- [x] No TypeScript compilation errors - PASSED

### Route Map Component Checks

- [x] Map renders on page load - PASSED
- [x] Map controls work (zoom, pan) - PASSED
- [x] Route displays on map - PASSED
- [x] Current position marker displays - PASSED
- [x] POI markers display - PASSED

**Overall Result**: ALL TESTS PASSED ✅
```

### Documentation Refactor Template

```markdown
## Smoke Test Results

**Test Category**: Documentation **Tested By**: [Your Name] **Date**: 2025-12-02
**Environment**: Local filesystem **Files Modified**: `docs/API-REFERENCE.md`
(split into 3 files)

### Link Validation

- [x] Internal links resolve (markdown-link-check) - PASSED
- [x] Manual link click-through - PASSED

### Code Example Validation

- [x] Curl commands execute successfully - PASSED
- [x] Configuration examples are valid - PASSED

**Overall Result**: ALL TESTS PASSED ✅
```

---

## 7. Related Requirements

This document supports the following requirements from `spec.md`:

- **Assumption 2**: "Each PR will include manual smoke testing to verify
  behavior remains unchanged"
- **Assumption 5**: "This is strictly refactoring—behavior must remain identical
  from a user perspective"
- **FR-013 through FR-017**: Documentation accuracy verification (code examples
  must execute successfully)

**Success Criteria**:

- **SC-007**: All documented API endpoints return responses matching
  documentation within 5% variance

---

**Document Version**: 1.0 **Last Updated**: 2025-12-02 **Maintained By**: Claude
Code Agent
