# POI Interactive Management Feature - Strategic Implementation Plan

**Last Updated:** 2025-10-30

**Feature Branch:** `feature/poi-interactive-management`

---

## Executive Summary

This plan outlines the implementation of an interactive Points of Interest (POI) management system for the Starlink dashboard. The feature will allow users to create, edit, and delete POIs directly from the Grafana dashboard, view them as markers on the map with real-time ETA tooltips, and manage them through a comprehensive table view.

### Key Deliverables

1. Interactive POI markers on the fullscreen overview map with ETA tooltips
2. POI management interface (either embedded or separate dashboard)
3. Real-time ETA calculations based on current speed and heading
4. POI table view showing all POIs and time-to-arrival estimates
5. Full CRUD operations for POI management via UI

---

## Current State Analysis

### Existing Infrastructure

The codebase already has significant POI infrastructure in place:

#### Backend Components (`backend/starlink-location/`)

**Models** (`app/models/poi.py`):
- `POI` - Full POI data model with ID, name, lat/lon, icon, category, description
- `POICreate` - Request model for creating new POIs
- `POIUpdate` - Request model for updating existing POIs
- `POIResponse` - Response model for API endpoints
- `POIListResponse` - List response with pagination support

**API Endpoints** (`app/api/pois.py`):
- `GET /api/pois` - List all POIs (with optional route filtering)
- `GET /api/pois/{poi_id}` - Get specific POI
- `POST /api/pois` - Create new POI
- `PUT /api/pois/{poi_id}` - Update existing POI
- `DELETE /api/pois/{poi_id}` - Delete POI
- `GET /api/pois/count/total` - Get POI count

**Storage** (`app/services/poi_manager.py`):
- File-based JSON storage at `/data/pois.json`
- In-memory caching for performance
- Full CRUD operations
- Route-specific POI filtering
- Automatic file creation and timestamp tracking

**Prometheus Metrics** (`app/core/metrics.py`):
- `starlink_eta_poi_seconds{name="..."}` - ETA to each POI in seconds
- `starlink_distance_to_poi_meters{name="..."}` - Distance to each POI in meters

#### Frontend Components

**Grafana Dashboard** (`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`):
- Geomap panel with:
  - OpenStreetMap basemap
  - Route history layer (blue line showing position history)
  - Current position marker layer (green plane with heading rotation)
  - Tooltip support enabled
  - Grid position: 16w x 22h at (0,2)

### What Already Works

1. ✅ Backend API for full POI CRUD operations
2. ✅ ETA and distance calculations (available as Prometheus metrics)
3. ✅ POI storage and persistence
4. ✅ Geomap visualization with layers support
5. ✅ Real-time position tracking

### What's Missing

1. ❌ POI markers layer on the Grafana geomap
2. ❌ Interactive tooltips showing ETA on hover
3. ❌ UI for creating/editing/deleting POIs
4. ❌ Table view of POIs with ETA information
5. ❌ Integration between backend ETA metrics and Grafana UI
6. ❌ Query to fetch POI data from backend API
7. ❌ Visual indication of POI approach (color coding, alerts)

---

## Proposed Future State

### User Experience Flow

#### Viewing POIs

1. User opens fullscreen overview dashboard
2. Map displays current position, route history, AND POI markers
3. Each POI shows as a distinct icon/marker with its label
4. Hovering over a POI displays:
   - POI name
   - ETA (e.g., "Arrival in 15 minutes")
   - Distance (e.g., "23.5 km away")
   - Bearing/direction indicator

#### Managing POIs (Option A: Embedded Controls)

1. User clicks "Add POI" button on dashboard
2. Modal/form appears requesting:
   - Name (required)
   - Latitude (required, or click-to-place on map)
   - Longitude (required, or click-to-place on map)
   - Icon/category (dropdown)
   - Description (optional)
3. User submits, POI immediately appears on map
4. User can click existing POI to edit/delete

#### Managing POIs (Option B: Separate Dashboard)

1. User navigates to "POI Management" dashboard via link
2. Dashboard shows:
   - Table of all POIs with columns: Name, Category, Lat, Lon, ETA, Distance, Actions
   - Map view showing all POIs
   - "Add New POI" form/button
3. Table provides edit/delete actions for each POI
4. Changes sync immediately to fullscreen overview

#### Table View (Integrated or Separate)

- Live-updating table showing:
  - POI name
  - Category/icon
  - Current ETA (updates every second)
  - Current distance
  - Estimated arrival time (calculated from current time + ETA)
  - Actions (Edit, Delete)
- Sortable by ETA (closest first) or alphabetically
- Filterable by category

---

## Implementation Phases

### Phase 1: Backend ETA Integration & API Enhancement

**Goal:** Ensure backend continuously calculates and exposes POI ETAs

#### Tasks

1.1. **Review current ETA calculation logic**
   - Location: Backend metric update cycle
   - Verify Haversine distance calculation accuracy
   - Ensure heading-aware ETA (not just straight-line distance)
   - **Acceptance:** ETA calculations verified accurate to ±5%

1.2. **Create ETA aggregation endpoint**
   - New endpoint: `GET /api/pois/etas`
   - Returns JSON: `[{poi_id, name, eta_seconds, distance_meters, bearing}]`
   - Updates in real-time based on current telemetry
   - **Acceptance:** Endpoint returns real-time ETA data for all POIs

1.3. **Add POI metadata to metrics**
   - Include category and icon in metric labels (if feasible)
   - Allows Grafana to filter/style POIs by type
   - **Acceptance:** Prometheus metrics include POI metadata

1.4. **Test ETA calculation edge cases**
   - Test cases: stationary terminal, moving away from POI, very close approach
   - Validate bearing calculation (0° = North, 90° = East)
   - **Acceptance:** All edge cases handled gracefully

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** None

**Risks:**
- ETA accuracy may be affected by route changes (mitigation: use recent velocity average)
- High POI counts could impact performance (mitigation: caching, batch updates)

---

### Phase 2: Grafana POI Markers Layer

**Goal:** Display POI markers on the fullscreen overview map

#### Tasks

2.1. **Create Infinity Data Source configuration**
   - Add Infinity plugin to Grafana (if not installed)
   - Configure data source pointing to `http://starlink-location:8000/api/pois`
   - Test connection and data retrieval
   - **Acceptance:** Infinity data source successfully fetches POI list

2.2. **Add POI markers layer to geomap**
   - Insert new layer in fullscreen-overview.json after "Current Position" layer
   - Configuration:
     - Type: `markers`
     - Name: `Points of Interest`
     - Data source: Infinity (POI list endpoint)
     - Location mode: `coords` (latitude/longitude fields)
     - Symbol: Icon based on `category` field or default marker
     - Size: Medium (10-12px)
     - Color: Distinct from position marker (e.g., orange/yellow)
   - **Acceptance:** POI markers appear on map at correct coordinates

2.3. **Configure POI marker styling**
   - Use Grafana field overrides to set icon per POI category:
     - Airport → plane icon
     - City → building icon
     - Landmark → star icon
     - Default → marker pin
   - Set opacity for visibility: 0.9
   - Add slight shadow for depth
   - **Acceptance:** POIs display with appropriate icons and styling

2.4. **Add POI labels**
   - Enable text display on markers
   - Text field: `name`
   - Font size: 10px
   - Offset: (0, 15) to appear below marker
   - **Acceptance:** POI names visible below markers

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** Backend API working (Phase 1)

**Risks:**
- Grafana Infinity plugin may have limitations (mitigation: use JSON API endpoint)
- Large POI counts may clutter map (mitigation: zoom-based filtering, clustering)

---

### Phase 3: Interactive ETA Tooltips

**Goal:** Show real-time ETA when hovering over POI markers

#### Tasks

3.1. **Fetch ETA data for tooltips**
   - Add query to geomap panel: `GET /api/pois/etas` (from Phase 1.2)
   - Join POI data with ETA data by `poi_id`
   - Use Grafana transformations: "Join by field" → `poi_id`
   - **Acceptance:** ETA data successfully joined to POI data

3.2. **Format ETA display**
   - Create calculated field: `eta_formatted`
   - Logic:
     - If `eta_seconds < 60`: "Arriving in X seconds"
     - If `eta_seconds < 3600`: "Arriving in X minutes"
     - If `eta_seconds >= 3600`: "Arriving in X hours Y minutes"
   - **Acceptance:** ETA displays in human-readable format

3.3. **Configure tooltip content**
   - Enable tooltip on POI markers layer: `tooltip: true`
   - Tooltip mode: `details`
   - Fields to display:
     - Name (bold)
     - ETA formatted
     - Distance (meters or km if > 1000m)
     - Category (if present)
     - Description (if present)
   - **Acceptance:** Hovering over POI shows detailed tooltip with ETA

3.4. **Add visual ETA indicators**
   - Color-code POI markers by proximity:
     - Red: ETA < 5 minutes (imminent)
     - Orange: ETA 5-15 minutes (approaching)
     - Yellow: ETA 15-60 minutes (near-term)
     - Blue: ETA > 60 minutes (distant)
   - Use field override: `eta_seconds` → color mapping
   - **Acceptance:** POI markers change color based on proximity

3.5. **Test tooltip refresh rate**
   - Verify tooltips update as terminal moves (every 1-3 seconds)
   - Ensure no flickering or performance issues
   - **Acceptance:** Tooltips update smoothly in real-time

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** Phase 2 complete (POI markers visible)

**Risks:**
- Tooltip refresh may cause UI lag (mitigation: optimize query interval)
- Color coding may be hard to see on map (mitigation: adjust colors/opacity)

---

### Phase 4: POI Table View Dashboard

**Goal:** Create a table view showing all POIs with ETA information

#### Tasks

4.1. **Create new dashboard or panel**
   - Decision point: Separate dashboard or panel on fullscreen overview?
   - **Option A:** Add panel to fullscreen overview (below map or side-by-side)
   - **Option B:** Create `poi-management.json` dashboard with link from fullscreen
   - Recommendation: Option B for clean separation, Option A for quick reference
   - **Acceptance:** Dashboard/panel structure created

4.2. **Configure table data source**
   - Data source: Infinity plugin
   - Endpoint: `GET /api/pois/etas`
   - Refresh interval: 1s
   - **Acceptance:** Table receives POI data with ETAs

4.3. **Design table columns**
   - Columns:
     1. Name (string, sortable)
     2. Category (string, with icon)
     3. Latitude (number, 5 decimal places)
     4. Longitude (number, 5 decimal places)
     5. Distance (formatted: "X.X km" or "X m")
     6. ETA (formatted: "X min" or "X:XX hr:min")
     7. Arrival Time (calculated: current_time + eta_seconds)
     8. Actions (Edit/Delete buttons - Phase 5)
   - **Acceptance:** All columns display with correct formatting

4.4. **Add table sorting and filtering**
   - Default sort: ETA ascending (closest POI first)
   - Allow user sort by: Name, Category, ETA, Distance
   - Optional: Filter by category dropdown
   - **Acceptance:** Table is sortable and filterable

4.5. **Style table for readability**
   - Alternate row colors for readability
   - Highlight POIs with ETA < 10 minutes (bold or background color)
   - Compact row height for space efficiency
   - **Acceptance:** Table is visually clear and easy to scan

4.6. **Add "Time Until Arrival" countdown**
   - Display countdown timer for closest POI
   - Example: "Next POI: JFK Airport in 12:34"
   - Position: Above table or in stat panel
   - **Acceptance:** Countdown updates in real-time

**Estimated Effort:** Small to Medium (1-2 days)

**Dependencies:** Phase 1 complete (ETA API endpoint)

**Risks:**
- Table refresh may be expensive with many POIs (mitigation: limit to closest N POIs)
- Grafana table plugin may have formatting limitations (mitigation: use transformations)

---

### Phase 5: POI Management UI

**Goal:** Allow users to create, edit, and delete POIs from the dashboard

#### Tasks

5.1. **Research Grafana UI interaction options**
   - Option A: Grafana Forms (if available in version)
   - Option B: Custom HTML panel with iframe to backend UI
   - Option C: External web UI served by backend at `/ui/pois`
   - Option D: Grafana Data Manipulation plugin
   - Recommendation: Option C (most flexible and maintainable)
   - **Acceptance:** Implementation approach decided and documented

5.2. **Create POI management UI endpoint (Option C)**
   - Backend route: `GET /ui/pois`
   - Serve static HTML/JS/CSS or use Jinja2 templates
   - UI features:
     - Form to add new POI (name, lat, lon, category, description)
     - Table of existing POIs with Edit/Delete buttons
     - Map widget for click-to-place lat/lon
   - **Acceptance:** UI accessible at backend URL

5.3. **Implement POI creation form**
   - Form fields:
     - Name (text input, required)
     - Latitude (number input or map click, required)
     - Longitude (number input or map click, required)
     - Category (dropdown: Airport, City, Landmark, Waypoint, Other)
     - Icon (auto-selected based on category, or manual dropdown)
     - Description (textarea, optional)
   - Validation: Lat/lon range checks, name non-empty
   - Submit: POST to `/api/pois`
   - **Acceptance:** Form successfully creates POI via API

5.4. **Implement POI editing**
   - Click "Edit" button in table → populate form with POI data
   - Allow modification of all fields except ID
   - Submit: PUT to `/api/pois/{poi_id}`
   - Cancel button to reset form
   - **Acceptance:** Editing POI updates database and UI

5.5. **Implement POI deletion**
   - Click "Delete" button → show confirmation dialog
   - Confirmation: "Delete POI '{name}'? This cannot be undone."
   - Submit: DELETE to `/api/pois/{poi_id}`
   - **Acceptance:** Deleting POI removes from database and UI

5.6. **Add map click-to-place feature**
   - Embed small interactive map in UI (Leaflet.js)
   - Click map → auto-fill lat/lon fields in form
   - Show marker at clicked location
   - **Acceptance:** Clicking map populates lat/lon fields

5.7. **Integrate UI into Grafana dashboard**
   - Option A: Embed iframe panel pointing to `/ui/pois`
   - Option B: Add dashboard link to external UI
   - Configure authentication pass-through if needed
   - **Acceptance:** UI accessible from Grafana dashboard

5.8. **Add real-time sync**
   - After create/update/delete, trigger Grafana dashboard refresh
   - Use WebSocket or polling to detect backend changes
   - Alternative: Manual "Refresh" button in UI
   - **Acceptance:** Changes appear on map within 3 seconds

**Estimated Effort:** Large (4-5 days)

**Dependencies:** Phases 1-4 complete

**Risks:**
- Grafana iframe may have CORS or auth issues (mitigation: configure backend headers)
- UI may not match Grafana theme (mitigation: use CSS variables or embed simple form)
- Concurrent edits may cause conflicts (mitigation: last-write-wins with timestamp)

---

### Phase 6: Testing & Refinement

**Goal:** Validate all features work correctly and refine UX

#### Tasks

6.1. **End-to-end testing**
   - Test flow: Create POI → see on map → hover for ETA → edit → delete
   - Test with simulation mode and live mode
   - Test with 0, 1, 10, and 50+ POIs
   - **Acceptance:** All features work correctly in all scenarios

6.2. **Performance testing**
   - Measure dashboard load time with varying POI counts
   - Verify Grafana query refresh intervals don't cause lag
   - Check backend API response times under load
   - **Acceptance:** Dashboard loads in < 2s with 50 POIs

6.3. **ETA accuracy validation**
   - Compare calculated ETA vs. actual arrival time in simulation
   - Test edge cases: stationary, zigzag path, high speed
   - **Acceptance:** ETA accuracy within ±10% of actual

6.4. **UI/UX refinement**
   - Get user feedback on POI icon sizes, colors, tooltip layout
   - Adjust styling for readability and aesthetics
   - Add keyboard shortcuts if applicable (e.g., 'N' for new POI)
   - **Acceptance:** UI is intuitive and visually appealing

6.5. **Error handling**
   - Test invalid inputs: lat/lon out of range, empty name, special characters
   - Verify graceful degradation if backend API is down
   - Check error messages are user-friendly
   - **Acceptance:** All error cases handled gracefully with clear messages

6.6. **Documentation**
   - Update `CLAUDE.md` with POI management instructions
   - Add screenshots to README showing POI features
   - Document API endpoints in design-document.md
   - Create user guide for POI management UI
   - **Acceptance:** Documentation complete and accurate

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** Phases 1-5 complete

**Risks:**
- User feedback may require significant redesign (mitigation: prototype early)
- Performance issues may require optimization (mitigation: profiling and caching)

---

### Phase 7: Feature Branch & Deployment

**Goal:** Prepare feature for merge to main branch

#### Tasks

7.1. **Create feature branch**
   - Branch name: `feature/poi-interactive-management`
   - Branch from: `dev` or `main` (check current strategy)
   - **Acceptance:** Feature branch created and pushed

7.2. **Code review preparation**
   - Self-review all changes
   - Ensure code follows project style (Prettier, linting)
   - Add comments for complex logic (ETA calculation, Grafana config)
   - **Acceptance:** Code is clean and well-documented

7.3. **Create pull request**
   - PR title: "Add interactive POI management with ETA tooltips and table view"
   - PR description: Link to this plan document, list key changes
   - Screenshots: Show map with POIs, tooltip, table view, management UI
   - **Acceptance:** PR created with comprehensive description

7.4. **Testing in staging environment**
   - Deploy to staging Docker stack
   - Test all features in staging
   - Verify no regressions in existing features
   - **Acceptance:** All tests pass in staging

7.5. **Merge and deploy**
   - Address review feedback
   - Merge to main branch
   - Deploy to production
   - Monitor for issues post-deployment
   - **Acceptance:** Feature live in production

**Estimated Effort:** Small (1 day)

**Dependencies:** Phase 6 complete

**Risks:**
- Merge conflicts with main branch (mitigation: rebase frequently)
- Production deployment issues (mitigation: rollback plan)

---

## Risk Assessment and Mitigation Strategies

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Grafana Infinity plugin not available or limited | Medium | High | Use JSON API endpoint, consider alternative plugins like Grafana HTTP API |
| ETA calculation inaccurate at high speeds | Medium | Medium | Use moving average of recent velocities, add configurable accuracy threshold |
| UI iframe blocked by CORS/CSP | Medium | Medium | Configure backend headers, use same-origin proxy |
| Performance degradation with 100+ POIs | Low | Medium | Implement zoom-based filtering, marker clustering, pagination in table |
| Grafana dashboard JSON corruption | Low | High | Version control, backup before changes, validate JSON before commit |
| Backend API downtime affects POI display | Low | Medium | Implement graceful degradation, cache last known POIs in Grafana |

### User Experience Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| POI markers obscure route or position | Medium | Low | Make markers semi-transparent, add z-index layering |
| Tooltip doesn't update in real-time | Medium | Medium | Optimize query interval, test refresh rates |
| UI for adding POIs is cumbersome | Medium | High | Prototype early, get user feedback, prioritize usability |
| Table view cluttered with many POIs | Medium | Low | Add pagination, filtering by category, "show only approaching" toggle |

### Data Integrity Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Concurrent POI edits cause conflicts | Low | Low | Use optimistic locking with timestamps, display conflict warning |
| POI file corruption | Very Low | High | Automated backups, validate JSON on save |
| POI IDs collide or duplicate | Very Low | Medium | Use UUID generation or slugification with counters |

---

## Success Metrics

### Functional Metrics

1. **POI Visibility:** All POIs display on map with correct coordinates (100% accuracy)
2. **ETA Accuracy:** ETA calculations within ±10% of actual arrival time
3. **Real-time Updates:** ETA tooltips refresh within 3 seconds of telemetry update
4. **CRUD Operations:** All POI create/update/delete operations succeed without errors
5. **UI Responsiveness:** Dashboard loads in < 2 seconds with 50 POIs

### User Experience Metrics

1. **Ease of Use:** New users can add a POI in < 60 seconds without documentation
2. **Visual Clarity:** POI markers distinguishable from position marker at all zoom levels
3. **Information Density:** Tooltip provides all essential info without clutter
4. **Table Usability:** Users can find target POI in table in < 10 seconds

### Performance Metrics

1. **API Response Time:** `/api/pois` endpoint responds in < 100ms
2. **ETA Calculation Overhead:** < 5ms per POI per update cycle
3. **Grafana Query Duration:** POI queries complete in < 500ms
4. **Dashboard Refresh Rate:** Maintains 1-second update interval without lag

---

## Required Resources and Dependencies

### Software Dependencies

#### Backend
- **Existing:** FastAPI, Pydantic, Prometheus client
- **New (if needed):**
  - Jinja2 (for HTML templates if building custom UI)
  - Leaflet.js or similar (for map widget in POI UI)

#### Frontend (Grafana)
- **Existing:** Grafana 11.1.0+, Prometheus data source
- **New:**
  - Grafana Infinity plugin (or alternative JSON API plugin)
  - Custom HTML panel plugin (if embedding iframe)

### Infrastructure
- **Storage:** `/data/pois.json` (already exists)
- **Network:** Backend API accessible from Grafana container (already configured)
- **Volumes:** Ensure `/data` volume persists across restarts

### Documentation
- Update `CLAUDE.md` with POI management instructions
- Update `docs/design-document.md` Section 4 (API endpoints)
- Update `docs/design-document.md` Section 5 (POI system details)
- Create `docs/poi-user-guide.md` with screenshots and instructions

### Testing Resources
- Simulation mode for safe testing
- Sample POI dataset (airports, cities, waypoints)
- Test cases for ETA calculation edge cases

---

## Timeline Estimates

| Phase | Description | Effort | Duration |
|-------|-------------|--------|----------|
| 0 | Planning & Design (this document) | Small | 0.5 days |
| 1 | Backend ETA Integration | Medium | 2-3 days |
| 2 | Grafana POI Markers Layer | Medium | 2-3 days |
| 3 | Interactive ETA Tooltips | Medium | 2-3 days |
| 4 | POI Table View Dashboard | Small-Medium | 1-2 days |
| 5 | POI Management UI | Large | 4-5 days |
| 6 | Testing & Refinement | Medium | 2-3 days |
| 7 | Feature Branch & Deployment | Small | 1 day |

**Total Estimated Duration:** 15-20 days (3-4 weeks)

### Critical Path
1. Phase 1 (Backend) → Phase 2 (Markers) → Phase 3 (Tooltips) → Phase 6 (Testing) → Phase 7 (Deploy)
2. Phase 4 (Table) can be developed in parallel with Phase 3
3. Phase 5 (Management UI) can be developed in parallel with Phases 3-4

### Accelerated Timeline (Parallel Development)
- With parallel work: **10-14 days** (2-3 weeks)
- Phases 3, 4, 5 can partially overlap if multiple developers available

---

## Implementation Notes

### Design Decisions

#### Why File-based POI Storage?
- Already implemented and working
- Simple for single-user deployments
- Easy to backup and version control
- Sufficient for expected POI counts (< 1000)
- Future: Can migrate to database if needed

#### Why Grafana Infinity Plugin?
- Native Grafana integration
- No custom plugins required
- Supports JSON API endpoints
- Flexible data transformations
- Alternative: HTTP API data source

#### Why Separate Management UI?
- Grafana dashboards are primarily for visualization, not data entry
- Custom UI allows better UX for POI management
- Keeps Grafana dashboard clean and focused
- Easier to add features like map click-to-place
- Alternative: Could use Grafana Forms if available

#### Color Coding by ETA
- Red (< 5 min): Immediate attention, approaching fast
- Orange (5-15 min): Near-term, pilot should be aware
- Yellow (15-60 min): Mid-range, upcoming waypoint
- Blue (> 60 min): Distant, informational only
- Rationale: Color gradient provides at-a-glance situational awareness

### Integration Points

#### Backend → Grafana
- Prometheus metrics: `starlink_eta_poi_seconds{name="..."}`
- JSON API: `GET /api/pois` (POI list)
- JSON API: `GET /api/pois/etas` (POI list with ETAs)
- Refresh interval: 1 second (matches telemetry update rate)

#### Grafana → Backend (for POI management)
- Iframe to: `http://starlink-location:8000/ui/pois`
- Or: Dashboard link to external URL
- Authentication: Pass-through if Grafana auth enabled, or basic auth

#### POI Manager → Metrics
- On POI add/update/delete: Trigger metric label update
- Ensure new POIs appear in Prometheus metrics immediately
- Use background task or event listener to sync POIs to metrics

---

## Future Enhancements (Out of Scope for Initial Release)

1. **POI Alerts:** Alert when approaching POI (e.g., 5-minute warning)
2. **POI Categories with Icons:** More icon choices, custom icons upload
3. **POI Import/Export:** Import from KML/KMZ, export to GPX
4. **POI Sharing:** Share POI sets between users/devices
5. **Route-based ETA:** Calculate ETA along planned route, not straight-line
6. **POI Clustering:** Group nearby POIs at low zoom levels to reduce clutter
7. **POI History:** Track when POIs were reached, save arrival times
8. **Multi-user Collaboration:** Real-time sync of POI changes between users
9. **Mobile App:** Native mobile app for POI management on the go
10. **Voice Alerts:** Audio notification when approaching POI

---

## Conclusion

This comprehensive plan provides a clear roadmap for implementing interactive POI management in the Starlink dashboard. By leveraging existing infrastructure (backend API, Grafana geomap, Prometheus metrics), we can deliver a powerful feature with manageable complexity.

The phased approach ensures incremental progress with testable milestones. The risk assessment identifies potential blockers early, and mitigation strategies are in place.

**Key Success Factors:**
- Leverage existing POI backend (80% of backend work already done)
- Use Grafana native features (Infinity plugin, geomap layers)
- Prioritize UX (intuitive UI, real-time updates, clear visual feedback)
- Test thoroughly (simulation mode makes this easy)
- Document well (for future maintenance and user adoption)

**Next Steps:**
1. Review and approve this plan
2. Create feature branch: `feature/poi-interactive-management`
3. Begin Phase 1: Backend ETA Integration
4. Proceed sequentially through phases, testing at each milestone

---

**Plan Status:** ✅ Ready for Review and Implementation

**Last Updated:** 2025-10-30
