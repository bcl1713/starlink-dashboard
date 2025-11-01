# KML Route Import - Task Checklist

**Last Updated:** 2025-11-02

**Feature Branch:** `feature/kml-route-import`

---

## Phase 1: Backend Route Upload API

### 1.1 Create Route API Module ✅
- [x] Create `backend/starlink-location/app/api/routes.py`
- [x] Add FastAPI router with prefix `/api/routes`
- [x] Register router in `main.py`
- [x] Test router accessible at `/api/routes`

### 1.2 Implement Route Upload Endpoint ✅
- [x] Add `POST /api/routes/upload` endpoint
- [x] Accept multipart/form-data with KML file
- [x] Validate file type (.kml extension)
- [x] Save file to `/data/routes/` directory
- [x] Handle filename conflicts (auto-rename if exists)
- [x] Trigger route manager reload
- [x] Return route metadata in response
- [x] Test with sample KML file

### 1.3 Implement Route List Endpoint ✅
- [x] Add `GET /api/routes` endpoint
- [x] Fetch routes from route_manager.list_routes()
- [x] Return RouteListResponse model
- [x] Support `active=true` query parameter
- [x] Test returns all routes

### 1.4 Implement Route Detail Endpoint ✅
- [x] Add `GET /api/routes/{route_id}` endpoint
- [x] Fetch from route_manager.get_route()
- [x] Include full route points
- [x] Calculate and include stats (distance, bounds)
- [x] Return 404 if not found
- [x] Test with valid and invalid route IDs

### 1.5 Implement Route Activation Endpoint ✅
- [x] Add `POST /api/routes/{route_id}/activate` endpoint
- [x] Call route_manager.activate_route()
- [x] Return success response
- [x] Return 404 if route not found
- [x] Test activation switches active route

### 1.6 Implement Route Deactivation Endpoint ✅
- [x] Add `POST /api/routes/deactivate` endpoint
- [x] Call route_manager.deactivate_route()
- [x] Return success response
- [x] Test clears active route

### 1.7 Implement Route Deletion Endpoint ✅
- [x] Add `DELETE /api/routes/{route_id}` endpoint
- [x] Delete KML file from `/data/routes/`
- [x] Delete associated POIs via poi_manager
- [x] Return 404 if not found
- [x] Return 204 No Content on success
- [x] Test deletes file and removes from cache

### 1.8 Implement Route Download Endpoint ✅
- [x] Add `GET /api/routes/{route_id}/download` endpoint
- [x] Stream KML file as download
- [x] Set Content-Type: application/vnd.google-earth.kml+xml
- [x] Set Content-Disposition with filename
- [x] Return 404 if not found
- [x] Test downloads original KML file

### 1.9 Implement Route Statistics Endpoint ✅
- [x] Add `GET /api/routes/{route_id}/stats` endpoint
- [x] Return distance, point_count, bounds
- [x] Calculate duration estimate (optional)
- [x] Test returns accurate statistics

### 1.10 Integrate Route Manager with Main App ✅
- [x] Add route_manager global instance in main.py
- [x] Initialize in startup_event()
- [x] Call start_watching()
- [x] Register with API modules
- [x] Test route manager starts on app startup

---

## Phase 2: Route Management Web UI ✅

### 2.1 Create HTML Template ✅
- [x] Created inline HTML in `app/api/ui.py` (no separate template directory needed)
- [x] Added custom CSS matching POI UI design
- [x] Designed layout: header, upload form, route table, modals
- [x] Responsive design with responsive grid layout

### 2.2 Create Route UI Endpoint ✅
- [x] Extended `app/api/ui.py` with `GET /ui/routes` endpoint
- [x] Returns inline HTML with embedded CSS/JS
- [x] Page accessible at http://localhost:8000/ui/routes
- [x] Following POI UI pattern for consistency

### 2.3 Implement Route List Display ✅
- [x] JavaScript fetches `/api/routes` on page load
- [x] Populated table with: name, points, distance, status, actions
- [x] Highlights active route with blue background
- [x] Auto-refresh every 5 seconds
- [x] Empty state when no routes
- [x] Tested with sample KML file

### 2.4 Implement File Upload Form ✅
- [x] File input with accept=".kml" validation
- [x] Custom styled file button matching UI
- [x] POST to `/api/routes/upload` with FormData
- [x] Loading spinner during upload
- [x] Success/error alert messages
- [x] Auto-refresh on upload success
- [x] Client-side file type validation
- [x] Tested upload functionality

### 2.5 Implement Route Activation ✅
- [x] "Activate" button for inactive routes
- [x] Green "ACTIVE" badge for active route
- [x] POST to `/api/routes/{id}/activate`
- [x] UI updates immediately after activation
- [x] Table row highlights when active
- [x] Tested activation updates display

### 2.6 Implement Route Deletion ✅
- [x] "Delete" button with danger styling
- [x] Confirmation modal with route name
- [x] Warning about POI cascade deletion
- [x] DELETE to `/api/routes/{id}`
- [x] List refreshes after deletion
- [x] Tested with confirmation dialog

### 2.7 Implement Route Download ✅
- [x] "Download" button for each route
- [x] Triggers GET to `/api/routes/{id}/download`
- [x] Browser downloads KML file with proper name
- [x] Tested file download

### 2.8 Add Route Details View ✅
- [x] Modal popup with route details
- [x] Displays route ID, name, waypoints, distance, bounds, status
- [x] Fetches full details from `/api/routes/{id}` and `/api/routes/{id}/stats`
- [x] Shows bounds in latitude/longitude format
- [x] Shows distance in km and meters
- [x] Modal closes on outside click or close button
- [x] Tested details modal

### 2.9 Add Error Handling ✅
- [x] Upload error messages from server
- [x] Network error handling with try/catch
- [x] Loading states with spinner animation
- [x] File type validation (client-side)
- [x] API error response parsing
- [x] Tested all error scenarios

---

## Phase 3: Grafana Route Visualization ✅

### 3.1 Update GeoJSON Endpoint ✅
- [x] Verified `/api/route.geojson` returns active route
- [x] Tested returns empty if no active route
- [x] Ensured LineString properly formatted
- [x] Tested with various routes

### 3.2 Add Route Layer to Geomap ✅
- [x] Edited `fullscreen-overview.json`
- [x] Added new layer configuration
- [x] Set data source to Infinity plugin (refId H)
- [x] Query `/api/route.geojson?include_pois=false&include_position=false`
- [x] Set color to dark-orange
- [x] Set line width to 2px
- [x] Set opacity to 0.9
- [x] Tested layer displays correctly

### 3.3 Layer Ordering ✅
- [x] Verified layer z-order correct
- [x] Route positioned after POIs, before position history
- [x] Position marker on top (highest z-order)
- [x] Tested layers render correctly with proper stacking

### 3.4 Add Route Deactivate Button (BONUS) ✅
- [x] Added `deactivateRoute()` JavaScript function
- [x] Replaced ACTIVE badge with Deactivate button
- [x] Keeps Activate button for inactive routes
- [x] Uses existing alert system for feedback
- [x] Auto-refreshes route list after action
- [x] Tested deactivate endpoint works
- [x] Tested UI button functionality

### 3.5 Test with Multiple Routes ✅
- [x] Uploaded multiple test routes
- [x] Activated each in turn
- [x] Verified only active displays in GeoJSON
- [x] Tested with edge cases (no active route, switching routes)
- [x] Performance verified (5-second cache refresh)

---

## Phase 4: Route-POI Integration

### 4.1 Extract POIs from KML
- [x] Extend KML parser to find Placemark elements
- [x] Extract POI name, coordinates, description
- [x] Return POIs in parse result (via `ParsedRoute.waypoints`)
- [x] Test with KML containing Placemarks
  - Automated regression added in `tests/unit/test_kml_parser.py`

### 4.2 Import POIs During Upload
- [x] Add `import_pois` query parameter
- [x] Create POIs with route_id set
- [x] Use poi_manager.create_poi()
- [x] Test POI import

### 4.3 Filter POIs by Active Route
- [x] Modify POI display to filter by route
- [x] Show only POIs for active route
- [x] Test POI filtering

### 4.4 Delete POIs on Route Deletion
- [x] Call poi_manager.delete_route_pois()
- [x] Show POI count in delete warning
- [x] Test cascade delete

### 4.5 Add Route to POI Creation
- [x] Add route dropdown to POI form
- [x] Allow selecting route or "Global"
- [x] Test POI creation with route

### 4.6 Update POI Table
- [x] Add "Route" column
- [x] Show route name or "Global"
- [x] Add route filter
- [x] Test display

### POI Category Filtering (Session 7)
- [x] Add category label to Prometheus metrics
- [x] Create Grafana dashboard variable for filter
- [x] Implement backend category parameter filtering
- [x] Update both map and table queries with filter
- [x] Test all filter combinations

### Parser Refactor: Style/Color-Based Filtering (Session 9)
- [x] Analyze multi-leg KML structure (all 6 legs tested)
- [x] Identify style/color pattern (ffddad05 = main route)
- [x] Implement `_filter_segments_by_style()` function
- [x] Remove ordinal detection functions
- [x] Update RouteMetadata model (remove multi-leg fields)
- [x] Test with all 6 leg files (100% success)
- [x] Verify no regression on single-leg files
- [x] Docker rebuild successful
- [x] All files uploaded and validated

### POI Sync Fix (Session 6)
- [x] Identify stale cache issue in POIManager
- [x] Implement singleton pattern via dependency injection
- [x] Update API modules with setter functions
- [x] Wire injection in main.py startup
- [x] Test POI import immediately visible across API

---

## Phase 5: Simulation Mode Integration

### Parser Enhancement: Multi-Leg KML Detection (COMPLETED) ✅
- [x] Analyze multi-leg KML file structure (all 6 Leg files analyzed)
- [x] Identify ordinal position pattern (Ordinal 0/4 validated 100%)
- [x] Implement `_is_major_waypoint()` helper function
- [x] Implement `_detect_multi_leg_pattern()` detection function
- [x] Modify `_identify_primary_waypoints()` to use multi-leg detection
- [x] Implement `_filter_segments_by_boundaries()` function
- [x] Modify `_build_primary_route()` to apply segment filtering
- [x] Enhance `RouteMetadata` with multi-leg fields
- [x] Test with all 6 Leg files (100% success rate)
- [x] Verify no regression on single-leg files (backward compatible)
- [x] Document implementation in SESSION-NOTES.md

### 5.1 Review KML Follower
- [ ] Analyze `app/simulation/kml_follower.py`
- [ ] Understand route following logic
- [ ] Document integration points

### 5.2 Integrate with Simulator
- [ ] Modify SimulationCoordinator
- [ ] Check for active route on startup
- [ ] Use route if available
- [ ] Fall back to circular pattern
- [ ] Test simulator follows route

### 5.3 Add Route Progress Tracking
- [ ] Track waypoint index
- [ ] Create metric `starlink_route_progress_percent`
- [ ] Update during simulation
- [ ] Test metric exposed

### 5.4 Add Route Completion Behavior
- [ ] Implement loop/stop/reverse options
- [ ] Make configurable in config.yaml
- [ ] Test each behavior

### 5.5 Test Route Following
- [ ] Upload test route
- [ ] Activate route
- [ ] Start simulation
- [ ] Verify follows waypoints
- [ ] Check speed and heading
- [ ] Test accuracy

---

## Phase 6: Testing & Documentation

### 6.1 End-to-End Testing
- [ ] Test full upload → activate → visualize → delete flow
- [ ] Test with simple route (10 points)
- [ ] Test with complex route (1000+ points)
- [ ] Test with route containing POIs
- [ ] Test with invalid/malformed KML
- [ ] Document test results

### 6.2 UI/UX Testing
- [ ] Test in Chrome
- [ ] Test in Firefox
- [ ] Test in Safari
- [ ] Test responsive design
- [ ] Test with slow network
- [ ] Verify error messages clear

### 6.3 Performance Testing
- [ ] Measure upload time for large files
- [ ] Check Grafana map performance
- [ ] Verify file watching doesn't spike CPU
- [ ] Test with 10+ routes loaded
- [ ] Document performance metrics

### 6.4 Write Unit Tests
- [ ] Test KML parser edge cases
- [ ] Test route API endpoints
- [ ] Test route models
- [ ] Achieve >80% coverage
- [ ] All tests pass

### 6.5 Write Integration Tests
- [ ] Test upload flow
- [ ] Test GeoJSON generation
- [ ] Test route-POI integration
- [ ] All tests pass

### 6.6 Update Documentation
- [ ] Update `CLAUDE.md` with route instructions
- [ ] Update `docs/design-document.md` Section 4
- [ ] Update `docs/design-document.md` Section 5
- [ ] Create `docs/route-user-guide.md`
- [ ] Update `docs/API-REFERENCE.md`
- [ ] Update `README.md`

### 6.7 Create Sample KML Files
- [ ] Create `/data/sample_routes/` directory
- [ ] Add simple circular route
- [ ] Add cross-country route
- [ ] Add route with embedded POIs
- [ ] Add to README

---

## Phase 7: Feature Branch & Deployment

### 7.1 Code Review Preparation
- [ ] Self-review all changes
- [ ] Check code style (PEP 8)
- [ ] Add type hints
- [ ] Add docstrings
- [ ] Remove TODOs and debug code
- [ ] Run linter

### 7.2 Create Pull Request
- [ ] Write PR title following conventions
- [ ] Write comprehensive PR description
- [ ] Include screenshots of UI
- [ ] Include Grafana screenshots
- [ ] Link to planning documents
- [ ] Submit PR

### 7.3 Address Review Feedback
- [ ] Respond to comments
- [ ] Make requested changes
- [ ] Update PR
- [ ] Get approval

### 7.4 Merge to Dev
- [ ] Rebase on latest dev
- [ ] Ensure all tests pass
- [ ] Merge PR
- [ ] Delete feature branch

### 7.5 Deploy and Monitor
- [ ] Deploy to dev environment
- [ ] Monitor logs for errors
- [ ] Test in deployed environment
- [ ] Verify no regressions

---

## Additional Tasks

### Documentation
- [ ] Add route management section to README
- [ ] Create troubleshooting guide for route issues
- [ ] Document route file format requirements
- [ ] Add architecture diagrams if needed

### Nice-to-Have Features (Optional)
- [ ] Route rename functionality
- [ ] Route metadata editing
- [ ] Drag-and-drop file upload
- [ ] Route preview before upload
- [ ] Batch upload multiple routes
- [ ] Export route as GPX/GeoJSON

---

## Progress Tracking

**Overall Progress:** 39/94 tasks completed (41%)

### Phase Completion
- [x] Phase 1: Backend Route Upload API (10/10) ✅
- [x] Phase 2: Route Management Web UI (9/9) ✅
- [x] Phase 3: Grafana Route Visualization (6/6) ✅
- [x] Phase 4: Route-POI Integration (6/6) ✅
- [x] Additional: POI Category Filtering (Session 7) ✅
- [x] Additional: Parser Refactor - Style/Color-Based Filtering (Sessions 8-9) ✅
- [x] Additional: POI Sync Fix - Singleton Injection (Session 6) ✅
- [ ] Phase 5: Simulation Mode Integration (0/5) - READY TO START
- [ ] Phase 6: Testing & Documentation (0/7)
- [ ] Phase 7: Feature Branch & Deployment (0/5)

---

## Notes

- Mark tasks as completed using `[x]` when done
- Update "Last Updated" date when making changes
- Add notes for any blockers or important decisions
- Keep checklist in sync with actual implementation

---

**Status:** ✅ Session 10 Complete - All previous work tested and validated

**Last Updated:** 2025-11-02 Session 10 (Final Status: Ready for Phase 5)
