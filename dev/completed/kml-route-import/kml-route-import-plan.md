# KML Route Import and Management Feature - Strategic Implementation Plan

**Last Updated:** 2025-10-31

**Feature Branch:** `feature/kml-route-import`

---

## Executive Summary

This plan outlines the implementation of an interactive KML route import and management system for the Starlink dashboard, following Phase 4 of the phased development plan. The feature will allow users to upload, activate, and manage KML route files through a web UI, visualize routes on the Grafana map, and track progress along the route in real-time.

### Key Deliverables

1. Web UI for uploading and managing KML route files
2. REST API endpoints for route CRUD operations
3. Real-time route visualization on Grafana fullscreen overview map
4. Route activation/deactivation functionality
5. Route statistics (distance, point count, bounds)
6. Integration with existing POI system (route-specific POIs)
7. Route following in simulation mode

---

## Current State Analysis

### Existing Infrastructure

The codebase already has significant route infrastructure in place:

#### Backend Components (`backend/starlink-location/`)

**Models** (`app/models/route.py`):
- `RoutePoint` - Single point in a route (lat, lon, altitude, sequence)
- `RouteMetadata` - Route metadata (name, description, file_path, imported_at, point_count)
- `ParsedRoute` - Complete route with metadata and points
  - Methods: `get_total_distance()`, `get_bounds()`
- `RouteResponse` - API response model

**KML Parser** (`app/services/kml_parser.py`):
- `parse_kml_file()` - Parse KML to ParsedRoute
- `validate_kml_file()` - Validate KML without full parsing
- `KMLParseError` - Custom exception for parsing errors
- Supports LineString extraction
- Handles KML namespace properly

**Route Manager** (`app/services/route_manager.py`):
- Watches `/data/routes/` directory for KML files
- File system observer using watchdog library
- Auto-loads routes on create/modify/delete
- In-memory route cache
- Active route tracking
- Error tracking for failed parses
- Methods:
  - `start_watching()` / `stop_watching()`
  - `list_routes()` - Get all routes with metadata
  - `get_route(route_id)` - Get specific route
  - `get_active_route()` - Get currently active route
  - `activate_route(route_id)` - Set active route
  - `deactivate_route()` - Clear active route
  - `get_route_errors()` - Get parse errors
  - `reload_all_routes()` - Reload from disk

**GeoJSON API** (`app/api/geojson.py`):
- `GET /api/route.geojson` - Get route as GeoJSON FeatureCollection
  - Query params: `include_pois`, `include_position`, `route_id`
  - Returns LineString feature for route
- `GET /api/route.json` - Get route metadata only
  - Returns name, description, point_count, bounds, distance
- `GET /api/pois.geojson` - Get POIs (supports route filtering)
- `GET /api/position.geojson` - Get current position

**Simulation Integration** (`app/simulation/kml_follower.py`):
- Exists but not analyzed in detail
- Likely handles route following in simulation mode

#### Frontend Components

**Grafana Dashboard** (`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`):
- Geomap panel with multiple layers
- Already has route history layer (blue line)
- Position: 16w x 22h at (0,2)

### What Already Works

1. ✅ KML parsing to ParsedRoute objects
2. ✅ File watching for automatic route discovery
3. ✅ Route storage in `/data/routes/` directory
4. ✅ GeoJSON conversion and serving
5. ✅ Active route concept (one route active at a time)
6. ✅ Route metadata calculations (distance, bounds)
7. ✅ POI system with route filtering support
8. ✅ Route visualization (position history as route)

### What's Missing

1. ❌ Web UI for uploading KML files
2. ❌ API endpoints for route CRUD operations (create/delete)
3. ❌ Route list/management UI
4. ❌ Grafana integration to display uploaded routes (not just position history)
5. ❌ Route selection/activation UI
6. ❌ Visual indication of active route
7. ❌ Route file download capability
8. ❌ Route rename/edit capability
9. ❌ Integration between routes and route-specific POIs
10. ❌ Documentation for route management

---

## Proposed Future State

### User Experience Flow

#### Uploading Routes

1. User navigates to "Route Management" UI (at `/ui/routes` or embedded in Grafana)
2. UI shows:
   - List of currently loaded routes with details (name, points, distance, status)
   - "Upload New Route" button
   - Active route clearly indicated
3. User clicks "Upload New Route"
4. File picker appears (accepts .kml files only)
5. User selects KML file from local system
6. File uploads to backend via `POST /api/routes/upload`
7. Backend validates and parses KML
8. Route appears in list immediately
9. Success message: "Route '{name}' uploaded successfully (X points, Y km)"

#### Viewing Routes

1. User opens fullscreen overview dashboard
2. Map displays:
   - Current position marker (green plane)
   - Position history (blue line)
   - Active route (if set) as distinct colored line (e.g., red/orange)
   - All POIs associated with active route
3. Route appears as LineString with:
   - Distinctive color (red or orange)
   - Medium opacity (0.7) to see underlying map
   - Tooltip on hover showing route name and stats

#### Managing Routes

1. User accesses route management UI
2. Table shows all routes with columns:
   - Name
   - File name
   - Point count
   - Total distance
   - Imported date
   - Status (Active / Inactive)
   - Actions (Activate, Download, Delete)
3. User can:
   - Click "Activate" to set route as active
   - Click "Download" to download original KML file
   - Click "Delete" to remove route (with confirmation)
4. Only one route can be active at a time
5. Activating a new route deactivates the previous one

#### Route-POI Integration

1. When uploading a route, user can optionally extract POIs from KML
2. POIs found in KML Placemark elements are imported with route_id association
3. POIs display on map only when their associated route is active
4. User can manage route-specific POIs separately from global POIs

---

## Implementation Phases

### Phase 1: Backend Route Upload API

**Goal:** Create API endpoints for uploading and managing routes

#### Tasks

1.1. **Create route API module**
   - File: `backend/starlink-location/app/api/routes.py`
   - Create FastAPI router with prefix `/api/routes`
   - Register in `main.py`
   - **Acceptance:** Router registered and accessible

1.2. **Implement route upload endpoint**
   - Endpoint: `POST /api/routes/upload`
   - Accept multipart/form-data with KML file
   - Validate file type (.kml extension)
   - Save to `/data/routes/` directory
   - File naming: Use original name or generate unique name if exists
   - Trigger route manager to reload
   - Return route metadata in response
   - **Acceptance:** KML file uploads successfully and appears in route manager

1.3. **Implement route list endpoint**
   - Endpoint: `GET /api/routes`
   - Return all routes from route manager
   - Include: id, name, description, point_count, is_active, imported_at, file_path
   - Support query param: `active=true` to get only active route
   - **Acceptance:** Returns list of all loaded routes with metadata

1.4. **Implement route detail endpoint**
   - Endpoint: `GET /api/routes/{route_id}`
   - Return full route data including points
   - Include calculated stats: distance, bounds
   - Return 404 if route not found
   - **Acceptance:** Returns complete route data for valid route_id

1.5. **Implement route activation endpoint**
   - Endpoint: `POST /api/routes/{route_id}/activate`
   - Call route_manager.activate_route()
   - Return success status
   - Return 404 if route not found
   - **Acceptance:** Activates route and deactivates previous active route

1.6. **Implement route deactivation endpoint**
   - Endpoint: `POST /api/routes/deactivate`
   - Call route_manager.deactivate_route()
   - Return success status
   - **Acceptance:** Clears active route

1.7. **Implement route deletion endpoint**
   - Endpoint: `DELETE /api/routes/{route_id}`
   - Delete KML file from `/data/routes/`
   - Also delete associated route-specific POIs
   - Route manager will auto-detect and remove from cache
   - Return 404 if route not found
   - **Acceptance:** Deletes route file and removes from system

1.8. **Implement route download endpoint**
   - Endpoint: `GET /api/routes/{route_id}/download`
   - Stream original KML file as download
   - Set appropriate headers: Content-Type, Content-Disposition
   - Return 404 if route not found
   - **Acceptance:** Downloads original KML file

1.9. **Add route statistics endpoint**
   - Endpoint: `GET /api/routes/{route_id}/stats`
   - Return: distance, point_count, bounds, duration_estimate (based on average speed)
   - **Acceptance:** Returns calculated statistics

**Estimated Effort:** Medium (3-4 days)

**Dependencies:** None (uses existing route infrastructure)

**Risks:**
- File upload size limits (mitigation: configure max size, validate before processing)
- Concurrent uploads (mitigation: use atomic file operations)
- Invalid KML files (mitigation: validate before saving, return clear errors)

---

### Phase 2: Route Management Web UI

**Goal:** Create user-friendly web interface for route management

#### Tasks

2.1. **Create route management HTML template**
   - File: `backend/starlink-location/app/templates/routes.html`
   - Use simple, clean design (Bootstrap or similar)
   - Sections:
     - Header with title and upload button
     - Route table (responsive)
     - Upload modal/form
     - Delete confirmation modal
   - **Acceptance:** HTML template created with all sections

2.2. **Create route UI endpoint**
   - File: `backend/starlink-location/app/api/ui.py` (extend existing)
   - Endpoint: `GET /ui/routes`
   - Serve HTML template
   - Include embedded JavaScript for interactivity
   - **Acceptance:** Route management page accessible

2.3. **Implement route list display**
   - JavaScript: Fetch from `GET /api/routes`
   - Populate table with route data
   - Show: name, file, points, distance, status, actions
   - Highlight active route (bold or colored row)
   - Auto-refresh every 5 seconds or use manual refresh button
   - **Acceptance:** Route table displays all routes

2.4. **Implement file upload form**
   - Form with file input (accept=".kml")
   - Upload button triggers POST to `/api/routes/upload`
   - Show upload progress indicator
   - Display success/error messages
   - Refresh route list on success
   - **Acceptance:** File upload works and updates route list

2.5. **Implement route activation**
   - "Activate" button for each inactive route
   - "Active" badge for currently active route
   - Click triggers POST to `/api/routes/{id}/activate`
   - Update UI to reflect new active route
   - **Acceptance:** Route activation works and UI updates

2.6. **Implement route deletion**
   - "Delete" button for each route
   - Show confirmation dialog: "Delete route '{name}'? This will also delete associated POIs."
   - If confirmed, trigger DELETE to `/api/routes/{id}`
   - Refresh route list on success
   - **Acceptance:** Route deletion works with confirmation

2.7. **Implement route download**
   - "Download" button for each route
   - Trigger GET to `/api/routes/{id}/download`
   - Browser downloads original KML file
   - **Acceptance:** KML file downloads correctly

2.8. **Add route details view**
   - Click route name to expand/show details
   - Display: description, bounds, distance, point count, imported date
   - Optional: Show mini-map with route preview
   - **Acceptance:** Route details viewable

2.9. **Add error handling**
   - Display clear error messages for:
     - Upload failures (invalid file, parse errors)
     - Activation failures
     - Deletion failures
   - Show loading states during operations
   - **Acceptance:** All error cases handled gracefully

**Estimated Effort:** Medium-Large (4-5 days)

**Dependencies:** Phase 1 complete (API endpoints)

**Risks:**
- CORS issues (mitigation: configure backend CORS headers)
- Large KML files slow to upload (mitigation: show progress, validate size)
- Browser compatibility (mitigation: test on Chrome, Firefox, Safari)

---

### Phase 3: Grafana Route Visualization

**Goal:** Display uploaded routes on Grafana fullscreen overview map

#### Tasks

3.1. **Update GeoJSON endpoint for active route**
   - Modify `/api/route.geojson` to prioritize active route
   - If no active route, return empty features
   - Ensure route LineString is properly formatted
   - **Acceptance:** GeoJSON endpoint returns active route

3.2. **Add route layer to Grafana geomap**
   - Edit: `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
   - Add new layer after position history layer
   - Layer configuration:
     - Name: "Active Route"
     - Type: `route` or `linestring`
     - Data source: Infinity plugin querying `/api/route.geojson?include_pois=false`
     - Color: Orange or red (distinct from position history)
     - Line width: 3px (thicker than position history)
     - Opacity: 0.7
   - **Acceptance:** Active route displays on map when set

3.3. **Add route tooltip/legend**
   - Enable tooltip on route layer
   - Show: route name, total distance, point count
   - Add legend entry: "Active Route (red/orange line)"
   - **Acceptance:** Hovering over route shows info

3.4. **Adjust layer ordering**
   - Ensure layers render in correct order:
     1. Basemap (OpenStreetMap)
     2. Active Route (underneath everything else)
     3. Position History (on top of route)
     4. POI Markers (on top)
     5. Current Position (top-most)
   - **Acceptance:** Layers render in correct z-order

3.5. **Add route bounds fitting**
   - Optional: Add "Fit to Route" button in Grafana
   - Zoom map to show entire active route
   - Use route bounds from `/api/routes/{id}/stats`
   - **Acceptance:** Map can zoom to fit entire route

3.6. **Test with multiple routes**
   - Upload 3+ different routes
   - Activate each in turn
   - Verify only active route displays
   - Check performance with large routes (1000+ points)
   - **Acceptance:** Route switching works smoothly

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** Phases 1-2 complete

**Risks:**
- Grafana Infinity plugin limitations (mitigation: use alternative data source)
- Large routes cause performance issues (mitigation: simplify/downsample route)
- Route obscures position history (mitigation: adjust opacity and colors)

---

### Phase 4: Route-POI Integration

**Goal:** Link POIs to specific routes and manage together

#### Tasks

4.1. **Extract POIs from KML uploads**
   - Modify KML parser to detect Placemark elements (POIs)
   - Extract: name, coordinates, description
   - Return POIs alongside route in parse result
   - **Acceptance:** KML parser extracts POIs from Placemark elements

4.2. **Create POIs during route upload**
   - Endpoint: `POST /api/routes/upload?import_pois=true`
   - If query param set, create POIs with route_id = route_id
   - Use POI manager to create each POI
   - Associate POI with route via route_id field
   - **Acceptance:** POIs imported from KML and linked to route

4.3. **Filter POIs by active route**
   - Modify POI list endpoint or GeoJSON endpoint
   - Option A: Only show POIs for active route
   - Option B: Show all POIs but highlight active route's POIs
   - Recommendation: Option A for cleaner UI
   - **Acceptance:** Only relevant POIs display on map

4.4. **Delete route-specific POIs on route deletion**
   - When deleting route, also delete associated POIs
   - Use `poi_manager.delete_route_pois(route_id)`
   - Warn user in confirmation dialog
   - **Acceptance:** Deleting route also deletes its POIs

4.5. **Add route selector to POI management**
   - In POI creation form, add route dropdown
   - Allow creating POIs linked to specific route
   - Option: "Global" (no route) or select from loaded routes
   - **Acceptance:** POIs can be created for specific routes

4.6. **Update POI table to show route association**
   - Add "Route" column to POI table
   - Display route name or "Global"
   - Allow filtering POIs by route
   - **Acceptance:** POI table shows route associations

**Estimated Effort:** Medium (3-4 days)

**Dependencies:** Phases 1-2 complete

**Risks:**
- KML files may not have standard Placemark format (mitigation: handle multiple formats)
- POI import may create duplicates (mitigation: check for duplicates by name+coords)
- Deleting route with many POIs (mitigation: confirm and show count)

---

### Phase 5: Simulation Mode Integration

**Goal:** Enable simulator to follow uploaded routes

#### Tasks

5.1. **Review KML follower implementation**
   - Analyze `app/simulation/kml_follower.py`
   - Understand current route following logic
   - Identify integration points with route manager
   - **Acceptance:** KML follower code understood

5.2. **Integrate route manager with simulator**
   - Modify simulation coordinator to use route manager
   - On simulator start, check for active route
   - If active route exists, use it; otherwise use default circular pattern
   - **Acceptance:** Simulator uses active route if available

5.3. **Add route progress tracking**
   - Track current waypoint index in route
   - Expose as metric: `starlink_route_progress_percent`
   - Calculate based on distance traveled vs. total distance
   - **Acceptance:** Route progress available as metric

5.4. **Add route completion behavior**
   - When route end reached, options:
     - Loop back to start
     - Stop at end
     - Reverse and go back
   - Make configurable in config.yaml
   - **Acceptance:** Route completion behavior configurable

5.5. **Test route following**
   - Upload test route (e.g., NYC to Boston)
   - Activate route
   - Start simulation
   - Verify position follows route waypoints
   - Check speed and heading match route
   - **Acceptance:** Simulator follows route accurately

**Estimated Effort:** Medium (2-3 days)

**Dependencies:** Phase 1 complete

**Risks:**
- Route following may not look realistic (mitigation: interpolate between waypoints)
- Route waypoints may be too sparse (mitigation: add interpolation logic)
- Performance with large routes (mitigation: optimize waypoint lookup)

---

### Phase 6: Testing & Documentation

**Goal:** Validate all features and document thoroughly

#### Tasks

6.1. **End-to-end testing**
   - Test flow: Upload route → Activate → See on map → Simulate following → Delete
   - Test with various KML files:
     - Simple route (10 points)
     - Complex route (1000+ points)
     - Route with POIs embedded
     - Invalid/malformed KML
   - **Acceptance:** All test cases pass

6.2. **UI/UX testing**
   - Test route management UI in different browsers
   - Verify responsive design on mobile
   - Check error messages are clear
   - Test with slow network (simulate upload delays)
   - **Acceptance:** UI works smoothly in all scenarios

6.3. **Performance testing**
   - Measure route upload time for large files
   - Check Grafana map performance with complex routes
   - Verify file watching doesn't cause CPU spikes
   - **Acceptance:** Performance acceptable (< 2s load time)

6.4. **Update documentation**
   - Update `CLAUDE.md` with route management instructions
   - Update `docs/design-document.md` Section 4 (API endpoints)
   - Update `docs/design-document.md` Section 5 (KML & Routes)
   - Create `docs/route-user-guide.md` with screenshots
   - Update `docs/API-REFERENCE.md` with new endpoints
   - **Acceptance:** All documentation updated

6.5. **Write tests**
   - Unit tests for:
     - KML parser (various KML formats)
     - Route manager (file operations)
     - API endpoints (upload, activate, delete)
   - Integration tests for:
     - Full route upload flow
     - Route-POI integration
     - GeoJSON generation
   - **Acceptance:** Test coverage > 80%

6.6. **Create sample KML files**
   - Include in `/data/sample_routes/`
   - Provide 3-5 example routes:
     - Simple circular route
     - Cross-country route
     - Route with embedded POIs
   - Document in README
   - **Acceptance:** Sample routes available for testing

**Estimated Effort:** Medium (3-4 days)

**Dependencies:** Phases 1-5 complete

**Risks:**
- Edge cases discovered late (mitigation: test early and often)
- Documentation out of sync with code (mitigation: update docs with each phase)

---

### Phase 7: Feature Branch & Deployment

**Goal:** Prepare feature for merge to dev/main branch

#### Tasks

7.1. **Code review preparation**
   - Self-review all changes
   - Ensure code follows project style (PEP 8, type hints)
   - Add docstrings for all new functions
   - Check for TODOs or commented code
   - **Acceptance:** Code is clean and well-documented

7.2. **Create pull request**
   - PR title: "feat: add KML route import and management system"
   - PR description:
     - Link to this plan document
     - List key changes and new endpoints
     - Include screenshots of route management UI
     - Show before/after Grafana screenshots
   - **Acceptance:** PR created with comprehensive description

7.3. **Address review feedback**
   - Respond to code review comments
   - Make requested changes
   - Update PR with changes
   - **Acceptance:** All feedback addressed

7.4. **Merge to dev branch**
   - Ensure all tests pass
   - Rebase on latest dev if needed
   - Merge PR
   - Delete feature branch
   - **Acceptance:** Code merged to dev

7.5. **Deploy and monitor**
   - Deploy to staging/dev environment
   - Monitor logs for errors
   - Test in deployed environment
   - **Acceptance:** Feature working in dev environment

**Estimated Effort:** Small (1-2 days)

**Dependencies:** Phase 6 complete

**Risks:**
- Merge conflicts with dev (mitigation: rebase frequently during development)
- Deployment issues (mitigation: test in Docker locally before deploy)

---

## Risk Assessment and Mitigation Strategies

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Large KML files (>5MB) cause upload timeouts | Medium | Medium | Set appropriate timeout, validate file size before upload |
| Invalid KML files crash parser | Medium | High | Comprehensive validation, try-catch with clear error messages |
| File watching causes performance issues | Low | Medium | Debounce file events, limit watch to .kml files only |
| Route with 10k+ points slows Grafana | Low | Medium | Downsample routes for display, keep original for calculations |
| Concurrent route uploads cause conflicts | Low | Low | Use unique filenames, atomic file operations |
| Route manager memory usage grows with routes | Very Low | Low | Implement route cache size limit if needed |

### User Experience Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| UI doesn't clearly show active route | Medium | Medium | Use prominent visual indicators (color, badge, highlighting) |
| Users accidentally delete routes | Medium | High | Confirmation dialog with clear warning about POI deletion |
| Upload UI confusing | Low | Medium | Simple design, clear labels, helpful error messages |
| Route not visible on map after activation | Medium | High | Auto-zoom to route bounds, show activation success message |

### Data Integrity Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Route file deleted outside application | Low | Low | Route manager handles file deletion gracefully |
| KML file corrupted during upload | Very Low | Medium | Validate before saving, atomic writes |
| Route-POI associations lost | Very Low | High | Store route_id in POI data, validate on access |

---

## Success Metrics

### Functional Metrics

1. **Route Upload:** KML files upload successfully 100% of valid files
2. **Route Display:** Active route displays on map within 2 seconds of activation
3. **Route Following:** Simulator follows route with < 100m accuracy
4. **API Performance:** All endpoints respond in < 500ms
5. **File Operations:** Upload/delete operations complete in < 2s for files < 5MB

### User Experience Metrics

1. **Ease of Use:** New users can upload and activate route in < 90 seconds
2. **Visual Clarity:** Active route clearly distinguishable from position history
3. **Error Handling:** All error messages clear and actionable
4. **UI Responsiveness:** UI updates within 3 seconds of backend changes

### Performance Metrics

1. **Upload Speed:** 1MB KML file uploads in < 5 seconds
2. **Parse Speed:** 1000-point route parses in < 100ms
3. **Grafana Load:** Map loads in < 3s with active route
4. **Memory Usage:** Route manager uses < 50MB for 100 routes

---

## Required Resources and Dependencies

### Software Dependencies

#### Backend
- **Existing:** FastAPI, Pydantic, watchdog, xml.etree, filelock
- **New:**
  - None required (all dependencies already installed)

#### Frontend (Web UI)
- **HTML/CSS/JS:**
  - Bootstrap 5 or Tailwind CSS (for styling)
  - Vanilla JavaScript or Alpine.js (for interactivity)
  - No heavy frameworks needed

#### Frontend (Grafana)
- **Existing:** Grafana 11.1.0+, Infinity plugin
- **New:** None required

### Infrastructure

- **Storage:** `/data/routes/` directory (must be persistent volume)
- **Network:** Backend API accessible from Grafana container
- **Volumes:** Ensure `/data` volume persists across container restarts

### Documentation

- Update `CLAUDE.md` - Route management instructions
- Update `docs/design-document.md` - Section 4 (APIs) and Section 5 (Routes)
- Create `docs/route-user-guide.md` - User guide with screenshots
- Update `docs/API-REFERENCE.md` - New route endpoints
- Update `README.md` - Add route management section

### Testing Resources

- Sample KML files (various sizes and formats)
- Test data directory: `/data/sample_routes/`
- Simulation mode for safe testing

---

## Timeline Estimates

| Phase | Description | Effort | Duration |
|-------|-------------|--------|----------|
| 1 | Backend Route Upload API | Medium | 3-4 days |
| 2 | Route Management Web UI | Medium-Large | 4-5 days |
| 3 | Grafana Route Visualization | Medium | 2-3 days |
| 4 | Route-POI Integration | Medium | 3-4 days |
| 5 | Simulation Mode Integration | Medium | 2-3 days |
| 6 | Testing & Documentation | Medium | 3-4 days |
| 7 | Feature Branch & Deployment | Small | 1-2 days |

**Total Estimated Duration:** 18-25 days (3.5-5 weeks)

### Critical Path
1. Phase 1 (API) → Phase 2 (UI) → Phase 3 (Grafana) → Phase 6 (Testing) → Phase 7 (Deploy)
2. Phase 4 (POI Integration) can partially overlap with Phase 3
3. Phase 5 (Simulation) can be developed in parallel with Phases 3-4

### Accelerated Timeline (Parallel Development)
- With focused development: **14-18 days** (2.5-3.5 weeks)
- Phases 3, 4, 5 can partially overlap

---

## Implementation Notes

### Design Decisions

#### Why File-based Storage?
- Already implemented (route manager watches `/data/routes/`)
- Simple and reliable for typical use cases
- Easy to backup and version control
- No database complexity
- Suitable for expected route counts (< 100 routes)

#### Why Single Active Route?
- Simplifies UI (clear which route is "in use")
- Matches typical use case (flying one route at a time)
- Reduces visual clutter on map
- Future: Could support multiple active routes if needed

#### Why Separate Upload from Grafana?
- Grafana is for visualization, not file management
- Custom UI allows better UX for file uploads
- Easier to add features like drag-drop, preview
- Keeps Grafana dashboard focused on monitoring

#### Route Display Color Scheme
- **Blue:** Position history (where we've been)
- **Orange/Red:** Active route (where we're going)
- **Green:** Current position marker
- Rationale: Distinct colors prevent confusion, traffic light metaphor

### Integration Points

#### Backend → Grafana
- **GeoJSON API:** `GET /api/route.geojson`
  - Returns active route as LineString feature
  - Grafana Infinity plugin queries this endpoint
- **Refresh interval:** 5 seconds (route changes are infrequent)

#### Route Manager → Simulation
- Simulator checks `route_manager.get_active_route()` on startup
- If route exists, uses route waypoints
- Otherwise, falls back to circular pattern

#### Routes → POIs
- POIs have optional `route_id` field
- When route is active, filter POIs by `route_id`
- When route is deleted, cascade delete associated POIs

---

## API Endpoint Summary

### New Endpoints (to be implemented)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/routes/upload` | Upload KML file |
| GET | `/api/routes` | List all routes |
| GET | `/api/routes/{id}` | Get route details |
| GET | `/api/routes/{id}/stats` | Get route statistics |
| POST | `/api/routes/{id}/activate` | Activate route |
| POST | `/api/routes/deactivate` | Deactivate current route |
| DELETE | `/api/routes/{id}` | Delete route |
| GET | `/api/routes/{id}/download` | Download KML file |
| GET | `/ui/routes` | Route management UI |

### Existing Endpoints (to be used)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/route.geojson` | Get active route as GeoJSON |
| GET | `/api/route.json` | Get route metadata |
| GET | `/api/pois?route_id={id}` | Get POIs for route |

---

## Future Enhancements (Out of Scope)

1. **Multi-route Display:** Show multiple routes simultaneously
2. **Route Editing:** Modify waypoints in UI
3. **Route Creation:** Draw routes directly on map
4. **Route Sharing:** Export/import route collections
5. **Route Analytics:** Track completion times, speed profiles
6. **Waypoint Alerts:** Alert when approaching waypoint
7. **Route Optimization:** Suggest route improvements
8. **GPX/TCX Support:** Import other route formats
9. **Route History:** Track which routes have been flown
10. **Collaborative Routes:** Share routes between users

---

## Conclusion

This comprehensive plan provides a clear roadmap for implementing KML route import and management. By leveraging existing infrastructure (route manager, KML parser, GeoJSON endpoints), we can deliver a powerful feature with manageable complexity.

The phased approach ensures incremental progress with testable milestones. The design follows the same pattern as the successful POI management feature, ensuring consistency and maintainability.

**Key Success Factors:**
- Leverage existing route infrastructure (60% of backend work already done)
- Follow POI management pattern for UI/API design
- Use simple file-based storage (no database complexity)
- Prioritize UX (clear upload flow, visual feedback, error handling)
- Test thoroughly with various KML files
- Document for future maintenance

**Next Steps:**
1. Review and approve this plan
2. Ensure on feature branch: `feature/kml-route-import` ✅ (already created)
3. Begin Phase 1: Backend Route Upload API
4. Proceed sequentially through phases, testing at each milestone

---

**Plan Status:** ✅ Ready for Review and Implementation

**Last Updated:** 2025-10-31
