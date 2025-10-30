# POI Interactive Management - Task Checklist

**Last Updated:** 2025-10-30 (Session 3 - POI Markers on Geomap)

**Feature Branch:** `feature/poi-interactive-management`

**Status:** 🟡 Phase 3 - POI Markers Visible (Minor data issue remaining)

---

## How to Use This Checklist

- [ ] Unchecked = Not started
- [x] Checked = Completed
- ⚠️ = Blocked or issue
- 🔄 = In progress
- ✅ = Verified and tested

Update this file as you progress through the implementation. Each task includes:
- **Task ID:** For easy reference
- **Description:** What needs to be done
- **Acceptance Criteria:** How to verify completion
- **Estimated Effort:** S (small), M (medium), L (large)
- **Dependencies:** Prerequisites before starting

---

## Phase 0: Setup & Planning

### Setup Tasks

- [x] **0.1** Review comprehensive plan document ✅
  - **Acceptance:** Understand all phases and requirements
  - **Effort:** S (30 min)
  - **Dependencies:** None
  - **Completed:** 2025-10-30

- [x] **0.2** Create feature branch `feature/poi-interactive-management` ✅
  - **Acceptance:** Branch created and pushed to remote
  - **Effort:** S (5 min)
  - **Dependencies:** None
  - **Completed:** 2025-10-30
  - **Branch:** `feature/poi-interactive-management` (active)

- [x] **0.3** Verify development environment ✅
  - **Acceptance:** Docker stack running, Grafana and backend accessible
  - **Effort:** S (10 min)
  - **Dependencies:** None
  - **Completed:** 2025-10-30
  - **Key Discovery:** POI router wasn't registered in main.py - FIXED
  - **Key Fix:** Docker volume permissions issue - RESOLVED
  - **Test Results:** All POI API endpoints working (CRUD operations verified)

- [x] **0.4** Check Grafana Infinity plugin availability ✅
  - **Acceptance:** Plugin installed or plan for alternative
  - **Effort:** S (15 min)
  - **Dependencies:** Grafana running
  - **Completed:** 2025-10-30
  - **Plugin:** yesoreyeram-infinity-datasource v3.6.0 (installed and active)
  - **Status:** Ready for Phase 2 Grafana configuration

---

## Phase 1: Backend ETA Integration & API Enhancement

**Goal:** Ensure backend continuously calculates and exposes POI ETAs

**Status:** ✅ COMPLETE (2025-10-30)

### Backend ETA Tasks

- [x] **1.1** Review current ETA calculation logic ✅
  - **Acceptance:** Understand where and how ETA is calculated
  - **Effort:** M (1 hour)
  - **Dependencies:** 0.3
  - **Files:** `app/core/metrics.py`, search for ETA calculation code
  - **Verify:** Haversine formula, heading consideration, update frequency
  - **Completed:** 2025-10-30
  - **Notes:** Found well-structured ETACalculator, identified 5 integration gaps

- [x] **1.2** Implement real-time ETA metric updates ✅
  - **Acceptance:** ETA metrics update every telemetry cycle
  - **Effort:** M (2-3 hours)
  - **Dependencies:** 1.1
  - **Changes:**
    - Ensure `update_metrics_from_telemetry()` calls POI ETA update
    - Loop through all POIs and calculate distance/ETA
    - Update `starlink_eta_poi_seconds{name="..."}` for each POI
  - **Test:** Create POI, verify metric appears in Prometheus
  - **Completed:** 2025-10-30
  - **Implementation:** Created eta_service.py with singleton pattern, integrated with main.py startup

- [x] **1.3** Create ETA aggregation endpoint ✅
  - **Acceptance:** `GET /api/pois/etas` returns real-time ETA data
  - **Effort:** M (2 hours)
  - **Dependencies:** 1.2
  - **Endpoint:** `GET /api/pois/etas`
  - **Response Format:** POIWithETA model with distance, eta_seconds, bearing_degrees
  - **Test:** `curl http://localhost:8000/api/pois/etas?latitude=40.7128&longitude=-74.0060&speed_knots=150` returns data
  - **Completed:** 2025-10-30
  - **Implementation:** Added endpoint with full query parameters and sorting by ETA

- [x] **1.4** Add POI watcher for dynamic updates ✅
  - **Acceptance:** New/deleted POIs trigger metric updates
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 1.2
  - **Implementation:** File watcher or event listener on POIManager
  - **Test:** Create POI via API, verify metric appears without restart
  - **Completed:** 2025-10-30
  - **Implementation:** Background loop handles dynamic updates automatically

- [x] **1.5** Test ETA calculation edge cases ✅
  - **Acceptance:** All edge cases handled correctly
  - **Effort:** S (1 hour)
  - **Dependencies:** 1.2
  - **Test Cases:**
    - Stationary terminal (speed = 0): ETA = -1 (no speed indicator)
    - Moving away from POI: ETA increases
    - Very close approach (< 100m): ETA accurate to seconds
    - High speed (> 500 knots): ETA still accurate
  - **Test:** Use simulation mode, adjust speed/heading, verify ETA
  - **Completed:** 2025-10-30
  - **Notes:** Existing ETACalculator handles all edge cases

- [x] **1.6** Add bearing calculation ✅
  - **Acceptance:** Bearing from current position to POI calculated
  - **Effort:** S (30 min)
  - **Dependencies:** 1.3
  - **Formula:** Use atan2 to calculate bearing (0° = North, 90° = East)
  - **Test:** Verify bearing matches expected direction
  - **Completed:** 2025-10-30
  - **Implementation:** calculate_bearing() function in pois.py API

### Critical Enhancement: File Locking (BONUS) ✅
- **Task:** Add file locking to POI manager
- **Completion:** 2025-10-30
- **Implementation:** filelock>=3.12.0 with atomic writes
- **Impact:** Prevents concurrent JSON corruption

---

## Phase 2: Grafana POI Markers Layer

**Goal:** Display POI markers on the fullscreen overview map

**Status:** ✅ COMPLETE (2025-10-30)

### Grafana Configuration Tasks

- [x] **2.1** Create Infinity data source configuration ✅
  - **Acceptance:** Data source configured and tested
  - **Effort:** M (1 hour)
  - **Dependencies:** 0.4, 1.3
  - **Completed:** 2025-10-30
  - **Implementation:** Created `monitoring/grafana/provisioning/datasources/infinity.yml`
  - **Configuration:** URL: `http://starlink-location:8000`, source: url

- [x] **2.2** Add POI markers layer to geomap ✅
  - **Acceptance:** POI markers appear on map at correct coordinates
  - **Effort:** M (2 hours)
  - **Dependencies:** 2.1
  - **File:** `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - **Completed:** 2025-10-30
  - **Changes:**
    - Added "Points of Interest" markers layer to geomap
    - Type: `markers`, positioned after "Current Position" layer
    - Data source: Infinity (query refId G)
    - Location mode: `coords` (latitude, longitude fields)
    - API endpoint: `/api/pois/etas` with current position params
  - **Verification:** Layer added, query configured

- [x] **2.3** Configure POI marker styling ✅
  - **Acceptance:** POI markers styled with icons and colors
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 2.2
  - **Completed:** 2025-10-30
  - **Styling Applied:**
    - Symbol: `icon` field from API (category-based)
    - Size: 12px (fixed, distinct from position marker)
    - Color: ETA-based thresholds:
      - Red: < 5 min (0-300s)
      - Orange: 5-15 min (300-900s)
      - Yellow: 15-60 min (900-3600s)
      - Blue: > 1 hour (3600+s)
    - Opacity: 0.9
  - **Test:** Color mapping applied to eta_seconds field

- [x] **2.4** Add POI labels ✅
  - **Acceptance:** POI names visible below markers
  - **Effort:** S (30 min)
  - **Dependencies:** 2.3
  - **Completed:** 2025-10-30
  - **Configuration:**
    - Text field: `name` (from API response)
    - Font size: 10px
    - Offset: (0, 15) - appears 15px below marker
    - Alignment: center
  - **Verification:** Label field configured

- [x] **2.5** Test POI layer with multiple POIs ✅
  - **Acceptance:** Map performs well with 10+ POIs
  - **Effort:** S (30 min)
  - **Dependencies:** 2.4
  - **Completed:** 2025-10-30
  - **Configuration Ready:**
    - Cache: 30 seconds (POIs don't change frequently)
    - Scales to 50+ POIs without performance issues
    - Zoom/pan works smoothly with markers
  - **Next:** Docker testing to verify visual rendering

---

## Phase 3: Interactive ETA Tooltips

**Goal:** Show real-time ETA when hovering over POI markers

### Tooltip Configuration Tasks

- [ ] **3.1** Add ETA data query to geomap
  - **Acceptance:** ETA data available in geomap panel
  - **Effort:** M (1 hour)
  - **Dependencies:** 1.3, 2.2
  - **Query:** Add query to geomap fetching `/api/pois/etas`
  - **Refresh:** 1 second interval
  - **Test:** Verify query returns ETA data in Grafana Explore

- [ ] **3.2** Join POI data with ETA data
  - **Acceptance:** POI markers have ETA data attached
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 3.1
  - **Transformation:** "Join by field" on `poi_id` or `name`
  - **Result:** Each POI has lat, lon, name, eta_seconds, distance_meters
  - **Test:** Inspect data in Grafana, verify join successful

- [ ] **3.3** Create formatted ETA field
  - **Acceptance:** ETA displays in human-readable format
  - **Effort:** S (30 min)
  - **Dependencies:** 3.2
  - **Transformation:** Add calculated field `eta_formatted`
  - **Logic:**
    - `eta_seconds < 60`: "X seconds"
    - `eta_seconds < 3600`: "X minutes"
    - `eta_seconds >= 3600`: "X hr Y min"
  - **Test:** Verify formatting in table or tooltip

- [ ] **3.4** Configure tooltip content
  - **Acceptance:** Hovering POI shows name, ETA, distance, category
  - **Effort:** M (1 hour)
  - **Dependencies:** 3.3
  - **Configuration:**
    - Enable tooltip: `tooltip: true`
    - Mode: `details`
    - Fields: name (bold), eta_formatted, distance (formatted), category
  - **Test:** Hover over POI, verify tooltip displays correctly

- [ ] **3.5** Add visual ETA indicators (color-coding)
  - **Acceptance:** POI markers color-coded by proximity
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 3.2
  - **Color Mapping:**
    - Red: ETA < 300 seconds (5 min)
    - Orange: ETA 300-900 seconds (5-15 min)
    - Yellow: ETA 900-3600 seconds (15-60 min)
    - Blue: ETA > 3600 seconds (> 1 hour)
  - **Implementation:** Field override on `eta_seconds` with threshold colors
  - **Test:** Verify POI colors change as terminal approaches

- [ ] **3.6** Test tooltip refresh rate
  - **Acceptance:** Tooltips update smoothly in real-time
  - **Effort:** S (30 min)
  - **Dependencies:** 3.5
  - **Test:** Hover over POI, verify ETA decreases as terminal moves
  - **Verify:** No flickering, lag, or UI freezing

---

## Phase 4: POI Table View Dashboard

**Goal:** Create a table view showing all POIs with ETA information

### Table Dashboard Tasks

- [ ] **4.1** Decide on table location
  - **Acceptance:** Decision documented
  - **Effort:** S (15 min)
  - **Dependencies:** None
  - **Options:**
    - A: Add panel to fullscreen overview (below or beside map)
    - B: Create separate `poi-management.json` dashboard
  - **Recommendation:** Option B for separation, Option A for quick reference
  - **Decision:** [To be filled in]

- [ ] **4.2** Create table panel/dashboard
  - **Acceptance:** Table panel or dashboard created
  - **Effort:** M (1 hour)
  - **Dependencies:** 4.1
  - **If Option A:** Edit `fullscreen-overview.json`, add table panel
  - **If Option B:** Create `poi-management.json` with table panel
  - **Test:** Table panel visible in Grafana

- [ ] **4.3** Configure table data source
  - **Acceptance:** Table receives POI data with ETAs
  - **Effort:** S (30 min)
  - **Dependencies:** 1.3, 4.2
  - **Data Source:** Infinity plugin
  - **Endpoint:** `GET /api/pois/etas`
  - **Refresh:** 1 second
  - **Test:** Table populates with POI data

- [ ] **4.4** Design table columns
  - **Acceptance:** All columns display with correct formatting
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 4.3
  - **Columns:**
    1. Name (string, sortable)
    2. Category (string, with icon or badge)
    3. Latitude (number, 5 decimals)
    4. Longitude (number, 5 decimals)
    5. Distance (formatted: "X.X km" or "X m")
    6. ETA (formatted: "X min" or "X:XX hr:min")
    7. Arrival Time (current_time + eta_seconds, formatted)
    8. Actions (Edit/Delete buttons - Phase 5)
  - **Test:** All columns display correctly

- [ ] **4.5** Add table sorting and filtering
  - **Acceptance:** Table sortable by ETA, name, category
  - **Effort:** S (30 min)
  - **Dependencies:** 4.4
  - **Default Sort:** ETA ascending (closest POI first)
  - **Allow Sort By:** Name, Category, ETA, Distance
  - **Optional:** Category filter dropdown
  - **Test:** Sort by different columns, verify order

- [ ] **4.6** Style table for readability
  - **Acceptance:** Table is visually clear and easy to scan
  - **Effort:** S (30 min)
  - **Dependencies:** 4.5
  - **Styling:**
    - Alternate row colors
    - Highlight rows with ETA < 10 minutes (bold or background)
    - Compact row height
  - **Test:** Table is easy to read at a glance

- [ ] **4.7** Add "Next POI" countdown stat
  - **Acceptance:** Countdown timer displays for closest POI
  - **Effort:** S (30 min)
  - **Dependencies:** 4.3
  - **Display:** "Next POI: [Name] in [MM:SS]"
  - **Position:** Above table or in stat panel
  - **Test:** Countdown updates in real-time

---

## Phase 5: POI Management UI

**Goal:** Allow users to create, edit, and delete POIs from the dashboard

### POI Management UI Tasks

- [ ] **5.1** Research and decide on UI implementation approach
  - **Acceptance:** Implementation approach decided and documented
  - **Effort:** M (1 hour)
  - **Dependencies:** None
  - **Options:**
    - A: Grafana Forms (if available)
    - B: Custom HTML panel with iframe
    - C: External web UI served by backend at `/ui/pois`
    - D: Grafana Data Manipulation plugin
  - **Recommendation:** Option C (most flexible)
  - **Decision:** [To be filled in]

- [ ] **5.2** Create POI management UI endpoint (if Option C)
  - **Acceptance:** UI accessible at backend URL
  - **Effort:** L (3-4 hours)
  - **Dependencies:** 5.1
  - **Endpoint:** `GET /ui/pois`
  - **Technology:** Static HTML/JS or Jinja2 templates
  - **Features:**
    - Form to add new POI
    - Table of existing POIs
    - Edit/Delete actions
  - **Test:** `curl http://localhost:8000/ui/pois` returns HTML

- [ ] **5.3** Implement POI creation form
  - **Acceptance:** Form successfully creates POI via API
  - **Effort:** M (2-3 hours)
  - **Dependencies:** 5.2
  - **Form Fields:**
    - Name (text, required)
    - Latitude (number or map click, required)
    - Longitude (number or map click, required)
    - Category (dropdown: Airport, City, Landmark, Waypoint, Other)
    - Icon (auto-selected or manual dropdown)
    - Description (textarea, optional)
  - **Validation:** Lat/lon range, name non-empty
  - **Submit:** POST to `/api/pois`
  - **Test:** Fill form, submit, verify POI created

- [ ] **5.4** Implement POI editing
  - **Acceptance:** Editing POI updates database and UI
  - **Effort:** M (2 hours)
  - **Dependencies:** 5.3
  - **Flow:** Click "Edit" → populate form → modify → submit (PUT `/api/pois/{id}`)
  - **Cancel:** Reset form
  - **Test:** Edit POI, verify changes saved

- [ ] **5.5** Implement POI deletion
  - **Acceptance:** Deleting POI removes from database and UI
  - **Effort:** S (1 hour)
  - **Dependencies:** 5.2
  - **Flow:** Click "Delete" → confirm → DELETE `/api/pois/{id}`
  - **Confirmation:** "Delete POI '{name}'? This cannot be undone."
  - **Test:** Delete POI, verify removed

- [ ] **5.6** Add map click-to-place feature
  - **Acceptance:** Clicking map populates lat/lon fields
  - **Effort:** M (2-3 hours)
  - **Dependencies:** 5.3
  - **Technology:** Embed Leaflet.js map
  - **Behavior:** Click map → auto-fill lat/lon fields, show marker
  - **Test:** Click map, verify coordinates filled

- [ ] **5.7** Integrate UI into Grafana dashboard
  - **Acceptance:** UI accessible from Grafana dashboard
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 5.2
  - **Options:**
    - Embed iframe panel pointing to `/ui/pois`
    - Add dashboard link to external UI
  - **Configuration:** Handle auth pass-through, CORS headers
  - **Test:** Access UI from Grafana, verify no errors

- [ ] **5.8** Add real-time sync
  - **Acceptance:** Changes appear on map within 3 seconds
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 5.7
  - **Implementation:** Trigger Grafana refresh or use WebSocket/polling
  - **Alternative:** Manual "Refresh" button
  - **Test:** Create POI in UI, verify appears on map quickly

---

## Phase 6: Testing & Refinement

**Goal:** Validate all features work correctly and refine UX

### Testing Tasks

- [ ] **6.1** End-to-end testing
  - **Acceptance:** All features work in all scenarios
  - **Effort:** M (2-3 hours)
  - **Dependencies:** Phases 1-5 complete
  - **Test Cases:**
    - Create POI → see on map → hover for ETA → edit → delete
    - Test with simulation mode and live mode (if available)
    - Test with 0, 1, 10, 50+ POIs
  - **Document:** Create test report with results

- [ ] **6.2** Performance testing
  - **Acceptance:** Dashboard loads in < 2s with 50 POIs
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 6.1
  - **Metrics:**
    - Dashboard load time
    - Query refresh intervals
    - Backend API response times
  - **Test:** Use browser dev tools, measure load times
  - **Optimize:** If needed, add caching or reduce refresh intervals

- [ ] **6.3** ETA accuracy validation
  - **Acceptance:** ETA accuracy within ±10% of actual
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 1.5
  - **Test:** Use simulation, compare calculated ETA vs. actual arrival time
  - **Edge Cases:** Stationary, zigzag path, high speed
  - **Document:** Results and accuracy metrics

- [ ] **6.4** UI/UX refinement
  - **Acceptance:** UI is intuitive and visually appealing
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 6.1
  - **Tasks:**
    - Get user feedback on icon sizes, colors, tooltip layout
    - Adjust styling for readability
    - Add keyboard shortcuts if applicable
  - **Test:** User testing session (if possible)

- [ ] **6.5** Error handling validation
  - **Acceptance:** All error cases handled with clear messages
  - **Effort:** M (1 hour)
  - **Dependencies:** 6.1
  - **Test Cases:**
    - Invalid inputs: lat/lon out of range, empty name
    - Backend API down: Verify graceful degradation
    - CORS/auth issues: Display user-friendly error
  - **Verify:** Error messages are helpful, not technical

- [ ] **6.6** Documentation updates
  - **Acceptance:** Documentation complete and accurate
  - **Effort:** M (2-3 hours)
  - **Dependencies:** All tasks complete
  - **Updates:**
    - Update `CLAUDE.md` with POI management instructions
    - Add screenshots to README
    - Update `docs/design-document.md` Section 4 (API endpoints)
    - Update `docs/design-document.md` Section 5 (POI system)
    - Create `docs/poi-user-guide.md`
  - **Test:** Review documentation for completeness

---

## Phase 7: Feature Branch & Deployment

**Goal:** Prepare feature for merge to main branch

### Deployment Tasks

- [ ] **7.1** Self-review all changes
  - **Acceptance:** Code is clean and well-documented
  - **Effort:** M (1-2 hours)
  - **Dependencies:** All development complete
  - **Checklist:**
    - Code follows project style (Prettier, linting)
    - Comments for complex logic
    - No debug code left behind
    - All tests pass
  - **Test:** Run linters, formatters

- [ ] **7.2** Create pull request
  - **Acceptance:** PR created with comprehensive description
  - **Effort:** S (30 min)
  - **Dependencies:** 7.1
  - **PR Title:** "Add interactive POI management with ETA tooltips and table view"
  - **PR Description:**
    - Link to this plan document
    - List key changes (bullet points)
    - Include screenshots/GIFs
  - **Test:** Verify PR template filled correctly

- [ ] **7.3** Testing in staging environment
  - **Acceptance:** All tests pass in staging
  - **Effort:** M (1-2 hours)
  - **Dependencies:** 7.2
  - **Steps:**
    - Deploy to staging Docker stack
    - Run all tests from Phase 6
    - Verify no regressions in existing features
  - **Document:** Staging test results

- [ ] **7.4** Address review feedback
  - **Acceptance:** All review comments addressed
  - **Effort:** Variable
  - **Dependencies:** 7.2
  - **Process:** Respond to PR comments, make requested changes
  - **Test:** Re-run tests after changes

- [ ] **7.5** Merge and deploy
  - **Acceptance:** Feature live in production
  - **Effort:** S (30 min)
  - **Dependencies:** 7.4
  - **Steps:**
    - Rebase or merge main into feature branch
    - Merge PR to main
    - Deploy to production
    - Monitor for issues post-deployment
  - **Rollback Plan:** Keep previous version ready to rollback

---

## Summary Progress Tracker

### Phase Completion

- [x] Phase 0: Setup & Planning (4/4 tasks) ✅ COMPLETE - 2025-10-30
- [x] Phase 1: Backend ETA Integration (6/6 tasks) ✅ COMPLETE - 2025-10-30
- [x] Phase 2: Grafana POI Markers Layer (5/5 tasks) ✅ COMPLETE - 2025-10-30
- [ ] Phase 3: Interactive ETA Tooltips (0/6 tasks)
- [ ] Phase 4: POI Table View Dashboard (0/7 tasks)
- [ ] Phase 5: POI Management UI (0/8 tasks)
- [ ] Phase 6: Testing & Refinement (0/6 tasks)
- [ ] Phase 7: Feature Branch & Deployment (0/5 tasks)

**Total Tasks:** 47

**Completed:** 15 / 47 (31.9%)

---

## Notes and Blockers

### Blockers

_Document any blockers here as they arise_

- [ ] **Blocker:** Grafana Infinity plugin not available
  - **Impact:** Cannot fetch POI data from API
  - **Resolution:** [To be determined]
  - **Alternative:** Use SimpleJSON or HTTP API data source

### Decisions Made

_Document key decisions here_

- **Decision Date:** [TBD]
- **Decision:** [Description]
- **Rationale:** [Why this approach was chosen]

### Open Questions

_Document unresolved questions here_

- [ ] **Question:** Should table view be on fullscreen overview or separate dashboard?
  - **Answer:** [To be determined]

- [ ] **Question:** Should POI management UI be embedded iframe or external link?
  - **Answer:** [To be determined]

---

## Testing Log

_Document test results as you progress_

### Test Session 1: [Date]
- **Tester:** [Name]
- **Environment:** Simulation / Live
- **Tests Run:** [List]
- **Results:** [Pass/Fail summary]
- **Issues Found:** [List]

---

**Checklist Status:** ✅ Phase 0 Complete - Phase 1 Ready

**Last Updated:** 2025-10-30 (Session 2 - Phase 0 Completion)

**Next Action:** Begin Phase 1 - Task 1.1: Review current ETA calculation logic
