# KML Route Import - Task Checklist

**Last Updated:** 2025-10-31

**Feature Branch:** `feature/kml-route-import`

---

## Phase 1: Backend Route Upload API

### 1.1 Create Route API Module
- [ ] Create `backend/starlink-location/app/api/routes.py`
- [ ] Add FastAPI router with prefix `/api/routes`
- [ ] Register router in `main.py`
- [ ] Test router accessible at `/api/routes`

### 1.2 Implement Route Upload Endpoint
- [ ] Add `POST /api/routes/upload` endpoint
- [ ] Accept multipart/form-data with KML file
- [ ] Validate file type (.kml extension)
- [ ] Save file to `/data/routes/` directory
- [ ] Handle filename conflicts (auto-rename if exists)
- [ ] Trigger route manager reload
- [ ] Return route metadata in response
- [ ] Test with sample KML file

### 1.3 Implement Route List Endpoint
- [ ] Add `GET /api/routes` endpoint
- [ ] Fetch routes from route_manager.list_routes()
- [ ] Return RouteListResponse model
- [ ] Support `active=true` query parameter
- [ ] Test returns all routes

### 1.4 Implement Route Detail Endpoint
- [ ] Add `GET /api/routes/{route_id}` endpoint
- [ ] Fetch from route_manager.get_route()
- [ ] Include full route points
- [ ] Calculate and include stats (distance, bounds)
- [ ] Return 404 if not found
- [ ] Test with valid and invalid route IDs

### 1.5 Implement Route Activation Endpoint
- [ ] Add `POST /api/routes/{route_id}/activate` endpoint
- [ ] Call route_manager.activate_route()
- [ ] Return success response
- [ ] Return 404 if route not found
- [ ] Test activation switches active route

### 1.6 Implement Route Deactivation Endpoint
- [ ] Add `POST /api/routes/deactivate` endpoint
- [ ] Call route_manager.deactivate_route()
- [ ] Return success response
- [ ] Test clears active route

### 1.7 Implement Route Deletion Endpoint
- [ ] Add `DELETE /api/routes/{route_id}` endpoint
- [ ] Delete KML file from `/data/routes/`
- [ ] Delete associated POIs via poi_manager
- [ ] Return 404 if not found
- [ ] Return 204 No Content on success
- [ ] Test deletes file and removes from cache

### 1.8 Implement Route Download Endpoint
- [ ] Add `GET /api/routes/{route_id}/download` endpoint
- [ ] Stream KML file as download
- [ ] Set Content-Type: application/vnd.google-earth.kml+xml
- [ ] Set Content-Disposition with filename
- [ ] Return 404 if not found
- [ ] Test downloads original KML file

### 1.9 Implement Route Statistics Endpoint
- [ ] Add `GET /api/routes/{route_id}/stats` endpoint
- [ ] Return distance, point_count, bounds
- [ ] Calculate duration estimate (optional)
- [ ] Test returns accurate statistics

### 1.10 Integrate Route Manager with Main App
- [ ] Add route_manager global instance in main.py
- [ ] Initialize in startup_event()
- [ ] Call start_watching()
- [ ] Register with API modules
- [ ] Test route manager starts on app startup

---

## Phase 2: Route Management Web UI

### 2.1 Create HTML Template
- [ ] Create `backend/starlink-location/app/templates/` directory
- [ ] Create `routes.html` template
- [ ] Add Bootstrap or Tailwind CSS
- [ ] Design layout: header, table, upload form, modals
- [ ] Test template renders

### 2.2 Create Route UI Endpoint
- [ ] Extend `app/api/ui.py`
- [ ] Add `GET /ui/routes` endpoint
- [ ] Serve routes.html template
- [ ] Test page accessible

### 2.3 Implement Route List Display
- [ ] Add JavaScript to fetch `/api/routes`
- [ ] Populate table with route data
- [ ] Show: name, file, points, distance, status, actions
- [ ] Highlight active route
- [ ] Add manual refresh button
- [ ] Test table displays routes

### 2.4 Implement File Upload Form
- [ ] Add file input with accept=".kml"
- [ ] Add upload button
- [ ] Implement POST to `/api/routes/upload`
- [ ] Show upload progress indicator
- [ ] Display success/error messages
- [ ] Refresh route list on success
- [ ] Test file upload works

### 2.5 Implement Route Activation
- [ ] Add "Activate" button for inactive routes
- [ ] Add "Active" badge for active route
- [ ] Implement POST to `/api/routes/{id}/activate`
- [ ] Update UI on activation
- [ ] Test activation updates display

### 2.6 Implement Route Deletion
- [ ] Add "Delete" button for each route
- [ ] Show confirmation dialog
- [ ] Display POI count in warning
- [ ] Implement DELETE to `/api/routes/{id}`
- [ ] Refresh list on success
- [ ] Test deletion with confirmation

### 2.7 Implement Route Download
- [ ] Add "Download" button for each route
- [ ] Trigger GET to `/api/routes/{id}/download`
- [ ] Test file downloads correctly

### 2.8 Add Route Details View
- [ ] Implement expandable row or modal
- [ ] Display full route metadata
- [ ] Show bounds, distance, point count
- [ ] Optional: Add mini-map preview
- [ ] Test details view

### 2.9 Add Error Handling
- [ ] Display upload errors clearly
- [ ] Show loading states
- [ ] Handle network errors
- [ ] Validate file type client-side
- [ ] Test all error scenarios

---

## Phase 3: Grafana Route Visualization

### 3.1 Update GeoJSON Endpoint
- [ ] Verify `/api/route.geojson` returns active route
- [ ] Test returns empty if no active route
- [ ] Ensure LineString properly formatted
- [ ] Test with various routes

### 3.2 Add Route Layer to Geomap
- [ ] Edit `fullscreen-overview.json`
- [ ] Add new layer configuration
- [ ] Set data source to Infinity plugin
- [ ] Query `/api/route.geojson?include_pois=false`
- [ ] Set color to orange/red
- [ ] Set line width to 3px
- [ ] Set opacity to 0.7
- [ ] Test layer displays

### 3.3 Configure Route Tooltip
- [ ] Enable tooltip on route layer
- [ ] Show route name
- [ ] Show distance and point count
- [ ] Test tooltip appears on hover

### 3.4 Adjust Layer Ordering
- [ ] Verify layer z-order correct
- [ ] Route below position history
- [ ] Position marker on top
- [ ] Test layers render correctly

### 3.5 Add Route Bounds Fitting (Optional)
- [ ] Research Grafana auto-zoom capabilities
- [ ] Implement if feasible
- [ ] Test zoom to route bounds

### 3.6 Test with Multiple Routes
- [ ] Upload 3 different routes
- [ ] Activate each in turn
- [ ] Verify only active displays
- [ ] Test with large route (1000+ points)
- [ ] Check performance

---

## Phase 4: Route-POI Integration

### 4.1 Extract POIs from KML
- [ ] Extend KML parser to find Placemark elements
- [ ] Extract POI name, coordinates, description
- [ ] Return POIs in parse result
- [ ] Test with KML containing Placemarks

### 4.2 Import POIs During Upload
- [ ] Add `import_pois` query parameter
- [ ] Create POIs with route_id set
- [ ] Use poi_manager.create_poi()
- [ ] Test POI import

### 4.3 Filter POIs by Active Route
- [ ] Modify POI display to filter by route
- [ ] Show only POIs for active route
- [ ] Test POI filtering

### 4.4 Delete POIs on Route Deletion
- [ ] Call poi_manager.delete_route_pois()
- [ ] Show POI count in delete warning
- [ ] Test cascade delete

### 4.5 Add Route to POI Creation
- [ ] Add route dropdown to POI form
- [ ] Allow selecting route or "Global"
- [ ] Test POI creation with route

### 4.6 Update POI Table
- [ ] Add "Route" column
- [ ] Show route name or "Global"
- [ ] Add route filter
- [ ] Test display

---

## Phase 5: Simulation Mode Integration

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

**Overall Progress:** 0/94 tasks completed (0%)

### Phase Completion
- [ ] Phase 1: Backend Route Upload API (0/10)
- [ ] Phase 2: Route Management Web UI (0/9)
- [ ] Phase 3: Grafana Route Visualization (0/6)
- [ ] Phase 4: Route-POI Integration (0/6)
- [ ] Phase 5: Simulation Mode Integration (0/5)
- [ ] Phase 6: Testing & Documentation (0/7)
- [ ] Phase 7: Feature Branch & Deployment (0/5)

---

## Notes

- Mark tasks as completed using `[x]` when done
- Update "Last Updated" date when making changes
- Add notes for any blockers or important decisions
- Keep checklist in sync with actual implementation

---

**Status:** ✅ Ready to Begin Implementation

**Last Updated:** 2025-10-31
