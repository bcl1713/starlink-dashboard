# Phase 6: Testing & Documentation Plan

**Date:** 2025-11-03 (Session 15)
**Status:** In Progress
**Branch:** feature/kml-route-import

---

## Executive Summary

Phase 6 involves comprehensive testing of all completed phases (1-5) and documentation updates. This phase validates that all features work correctly individually and together, identifies edge cases, and prepares the codebase for production merge to dev branch.

### What's Already Done
- ✅ Phases 1-4: Core KML route management features (51 tasks)
- ✅ Phase 5.1-5.5: Simulation mode route following with full integration testing (5 sub-phases)
- ✅ Session 14: Phase 5.5 integration testing complete - all tests passing

### Phase 6 Scope
This phase covers:
1. End-to-end feature testing (all phases)
2. UI/UX testing across different scenarios
3. Performance validation
4. Documentation updates
5. Sample KML files for testing/examples
6. Automated test suite

---

## Testing Strategy

### Test Categories

#### 1. End-to-End Functionality Testing (6.1)

**Objective:** Validate complete user workflows from upload to simulation

**Test Cases:**

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1.1 | Simple route upload | 1. Upload simple 10-point KML<br>2. Verify in route list<br>3. Activate<br>4. Check on map<br>5. Delete | Route appears, activates, displays, deletes cleanly |
| 1.2 | Complex route handling | 1. Upload 1000+ point route<br>2. Verify parsing correct<br>3. Check distance calculation<br>4. Activate and view | Large routes parse without errors, display correctly |
| 1.3 | Route with embedded POIs | 1. Upload KML with Placemarks<br>2. Enable POI import<br>3. Verify POIs created<br>4. Check POI visibility | POIs import correctly, appear on map, filter works |
| 1.4 | Invalid KML handling | 1. Upload malformed KML<br>2. Check error message<br>3. Verify graceful failure | Clear error shown, no crashes, system stable |
| 1.5 | Route switching | 1. Upload 2 routes<br>2. Activate route A<br>3. Activate route B<br>4. Activate route A again | Routes switch correctly, metrics reset, no overlap |
| 1.6 | Simulation following | 1. Activate route in simulation mode<br>2. Monitor position updates<br>3. Check progress metrics<br>4. Verify waypoint tracking | Position follows route, metrics update, accuracy < 100m |
| 1.7 | Route deactivation | 1. Activate route<br>2. Deactivate<br>3. Check position behavior<br>4. Verify metrics clear | Position returns to default, metrics zero out cleanly |
| 1.8 | Concurrent operations | 1. Upload while route active<br>2. Delete while simulating<br>3. Rapid activation switching | No race conditions, all operations complete successfully |

**Pass Criteria:** ✅ All 8 test cases pass

**Test Files Needed:**
- `simple-route.kml` - 10 waypoint route
- `complex-route.kml` - 1000+ waypoint route
- `route-with-pois.kml` - Route with embedded Placemarks
- `invalid-route.kml` - Malformed KML file

---

#### 2. UI/UX Testing (6.2)

**Objective:** Ensure user interface is intuitive and responsive

**Test Scenarios:**

| Scenario | Tests |
|----------|-------|
| **Route Management UI** | - Upload button accessible<br>- File picker filters .kml files<br>- Drag-drop upload works (if implemented)<br>- Error messages clear and actionable<br>- Success messages confirm action<br>- Route table updates automatically |
| **Route Table** | - Shows all routes with correct metadata<br>- Active route highlighted<br>- Action buttons functional (Activate, Download, Delete)<br>- Details modal opens/closes<br>- Delete confirmation shows warning<br>- Sorting/filtering works (if implemented) |
| **Grafana Map** | - Route layer appears when route active<br>- Route displays with correct styling<br>- Layer ordering correct (behind position history)<br>- Map pans to route bounds on activation<br>- Route hides when deactivated<br>- Empty state handled gracefully |
| **Browser Compatibility** | - Chrome/Chromium<br>- Firefox<br>- Safari<br>- Edge |
| **Responsive Design** | - Desktop (1920x1080)<br>- Tablet (768px)<br>- Mobile (375px)<br>- All content accessible without scrolling (where reasonable) |
| **Network Simulation** | - Slow upload (>1s)<br>- Intermittent connection<br>- Timeout handling |

**Pass Criteria:** ✅ All scenarios pass in primary browsers (Chrome, Firefox)

---

#### 3. Performance Testing (6.3)

**Objective:** Validate system performance under expected load

| Metric | Target | Test Method |
|--------|--------|-------------|
| **Upload Time** | < 5s for 1MB file | Time route upload endpoint |
| **Parse Time** | < 100ms for 1000-point route | Measure parser duration |
| **Route Display** | < 2s after activation | Time map refresh |
| **Grafana Load** | < 3s map fully interactive | Measure from browser load to map ready |
| **Memory Usage** | < 50MB for 100 routes | Monitor during stress test |
| **File Watching** | No CPU spike on file change | Monitor CPU during upload/delete |
| **API Response** | < 500ms for all endpoints | Query /api/routes, /api/route/{id}, etc |

**Test Methods:**
```bash
# Measure API response time
time curl http://localhost:8000/api/routes

# Monitor memory
docker stats starlink-location

# Monitor CPU
docker stats --no-stream starlink-location

# Check backend logs for parser timing
docker logs starlink-location | grep "parse"
```

**Pass Criteria:** ✅ All metrics meet targets, no performance regressions

---

#### 4. Integration Testing (6.4)

**Objective:** Validate that all phases work together correctly

**Integration Points:**

| Phase | Integration Tests |
|-------|-------------------|
| **1 + 2** | Upload via API → appears in UI |
| **2 + 3** | UI activation → map updates |
| **3 + 4** | Route active → POIs visible and filtered |
| **4 + 5** | POIs on active route → simulation routes to them |
| **5 + 1** | Simulation running → metrics exported, position follows |
| **All** | Full workflow: Upload → Activate → Simulate → Switch → Delete |

---

## Detailed Testing Checklist

### 6.1 End-to-End Testing

**Setup:**
```bash
# Ensure Docker is running
docker compose ps

# Verify services healthy
curl http://localhost:8000/health
curl http://localhost:3000  # Grafana
```

**Test Execution:**

- [ ] **Test 1.1: Simple Route Upload**
  - [ ] Access http://localhost:8000/ui/routes
  - [ ] Click "Upload New Route"
  - [ ] Select simple-route.kml (10 points)
  - [ ] Verify "Upload successful" message
  - [ ] Route appears in table
  - [ ] Metadata shows correct point count and distance
  - [ ] Click "Activate" button
  - [ ] Badge changes to "ACTIVE"
  - [ ] Access http://localhost:3000 (Grafana)
  - [ ] Route line visible on map (dark orange)
  - [ ] Return to UI and click "Delete"
  - [ ] Confirm deletion
  - [ ] Route removed from list

- [ ] **Test 1.2: Complex Route (1000+ points)**
  - [ ] Repeat above with complex-route.kml
  - [ ] Verify distance calculation is accurate
  - [ ] Check Grafana map renders smoothly
  - [ ] Monitor backend logs for warnings
  - [ ] Verify no performance issues

- [ ] **Test 1.3: Route with Embedded POIs**
  - [ ] Upload route-with-pois.kml
  - [ ] Check `import_pois: true` option (if available)
  - [ ] Verify POIs appear in POI management
  - [ ] Activate route
  - [ ] Verify POIs visible on Grafana map
  - [ ] Test POI category filter
  - [ ] Delete route
  - [ ] Verify associated POIs deleted

- [ ] **Test 1.4: Invalid KML**
  - [ ] Upload invalid-route.kml
  - [ ] Verify error message shown
  - [ ] Check error is actionable (e.g., "Invalid KML: missing linestring")
  - [ ] No system crash
  - [ ] UI remains responsive

- [ ] **Test 1.5: Route Switching**
  - [ ] Upload and activate route A
  - [ ] Verify route A on map
  - [ ] Upload route B (different route)
  - [ ] Activate route B
  - [ ] Verify route A disappears, route B shows
  - [ ] Check Prometheus metrics switch correctly
  - [ ] Activate route A again
  - [ ] Verify smooth switching, no conflicts

- [ ] **Test 1.6: Simulation Following**
  - [ ] Ensure STARLINK_MODE=simulation in .env
  - [ ] Activate a route
  - [ ] Monitor position on Grafana map
  - [ ] Verify position updates along route
  - [ ] Check metrics: starlink_route_progress_percent updates
  - [ ] Verify starlink_current_waypoint_index increments
  - [ ] Let simulation run for 1+ minute
  - [ ] Verify no errors in logs
  - [ ] Check accuracy is reasonable (< 100m deviation)

- [ ] **Test 1.7: Deactivation**
  - [ ] Activate a route
  - [ ] Call deactivate endpoint: `curl -X POST http://localhost:8000/api/routes/deactivate`
  - [ ] Verify API returns success
  - [ ] Route disappears from Grafana
  - [ ] Position returns to default pattern (Arctic circle)
  - [ ] Metrics show progress = 0

- [ ] **Test 1.8: Concurrent Operations**
  - [ ] Activate route A
  - [ ] While running, upload route B
  - [ ] While B uploading, delete route C (if exists)
  - [ ] While running, activate route B
  - [ ] Verify all operations complete without errors
  - [ ] Check logs for any warnings or race conditions

### 6.2 UI/UX Testing

- [ ] **Route Management Page Loads**
  - [ ] Page loads in < 2 seconds
  - [ ] All controls visible and functional
  - [ ] No console errors in browser DevTools

- [ ] **Upload Form**
  - [ ] Click "Upload" button
  - [ ] File picker opens
  - [ ] Only .kml files selectable (if filtered)
  - [ ] Can select and upload file
  - [ ] Success message appears
  - [ ] Route added to table

- [ ] **Route Table**
  - [ ] All columns visible and readable
  - [ ] Route names truncated appropriately
  - [ ] Active route highlighted
  - [ ] Action buttons aligned and clickable
  - [ ] Hover states visible

- [ ] **Details Modal**
  - [ ] Click "Details" button
  - [ ] Modal opens with full route info
  - [ ] Distance accurate
  - [ ] Point count matches
  - [ ] Bounds displayed correctly
  - [ ] Modal closes cleanly

- [ ] **Delete Confirmation**
  - [ ] Click "Delete" button
  - [ ] Confirmation dialog shown
  - [ ] Warning message about POI deletion clear
  - [ ] Cancel button works
  - [ ] Confirm button deletes

- [ ] **Grafana Map**
  - [ ] Activate route from UI
  - [ ] Grafana map updates within 5 seconds
  - [ ] Route displays with correct color (dark orange)
  - [ ] Route layer appears under position history
  - [ ] Map is interactive (pan, zoom works)
  - [ ] Deactivate route
  - [ ] Route disappears from map

- [ ] **Error Handling**
  - [ ] Invalid file upload shows clear error
  - [ ] Network error handled gracefully
  - [ ] Large file timeout handled
  - [ ] Duplicate filename handled (renames or shows error)

- [ ] **Responsive Design**
  - [ ] Test on desktop (1920x1080)
    - [ ] All content visible
    - [ ] No horizontal scrolling
  - [ ] Test on tablet (768px)
    - [ ] Table responsive
    - [ ] Modals fit screen
  - [ ] Test on mobile (375px)
    - [ ] Touch-friendly buttons
    - [ ] No overflow

- [ ] **Browser Testing**
  - [ ] Chrome - [ ] All features work
  - [ ] Firefox - [ ] All features work
  - [ ] Safari (if available) - [ ] All features work

### 6.3 Performance Testing

**Setup:**
```bash
# Terminal 1: Monitor backend
docker logs -f starlink-location

# Terminal 2: Monitor containers
docker stats --no-stream

# Terminal 3: Run tests
cd /home/brian/Projects/starlink-dashboard-dev
```

**Tests:**

- [ ] **Upload Performance**
  ```bash
  # Measure time to upload 1MB route
  time curl -X POST \
    -F "file=@route.kml" \
    http://localhost:8000/api/routes/upload
  ```
  - [ ] Time < 5 seconds ✅
  - [ ] Backend logs show parse time
  - [ ] Memory usage stable

- [ ] **API Response Time**
  ```bash
  # Test all endpoints
  time curl http://localhost:8000/api/routes
  time curl http://localhost:8000/api/routes/{route_id}
  time curl http://localhost:8000/api/route.geojson
  ```
  - [ ] All < 500ms ✅
  - [ ] No timeouts
  - [ ] Consistent response times

- [ ] **Grafana Load Time**
  - [ ] Open http://localhost:3000/d/starlink/fullscreen-overview
  - [ ] Time from page load to fully interactive
  - [ ] With route active vs inactive
  - [ ] Should be < 3 seconds for both

- [ ] **File Watching Performance**
  - [ ] Upload new route
  - [ ] Monitor CPU with `docker stats`
  - [ ] CPU should return to baseline within 2 seconds
  - [ ] No sustained high CPU from file watcher

- [ ] **Memory Leak Testing**
  - [ ] Monitor memory for 5 minutes while idle
  - [ ] Memory should be stable
  - [ ] Upload/delete 5 routes rapidly
  - [ ] Memory should return to baseline

### 6.4 Integration Testing

- [ ] **Upload → List**
  - [ ] Upload route via API
  - [ ] Query /api/routes
  - [ ] Route appears in list immediately

- [ ] **List → Activate → Map**
  - [ ] Query /api/routes
  - [ ] Call activate endpoint
  - [ ] Query /api/route.geojson
  - [ ] Route appears on Grafana map

- [ ] **Activate → POI Filter**
  - [ ] Activate route with associated POIs
  - [ ] Check /api/pois?route_id={route_id}
  - [ ] Verify only route POIs returned
  - [ ] Activate different route
  - [ ] Verify different POIs returned

- [ ] **Active Route → Simulation**
  - [ ] Activate route
  - [ ] Monitor position updates
  - [ ] Verify position follows route
  - [ ] Check Prometheus metrics update
  - [ ] Deactivate route
  - [ ] Position returns to default

- [ ] **Full Workflow**
  - [ ] Upload Route A
  - [ ] Activate Route A
  - [ ] Verify on map
  - [ ] Upload Route B
  - [ ] Activate Route B
  - [ ] Verify switch works
  - [ ] Delete Route A
  - [ ] Delete Route B
  - [ ] Verify both removed cleanly

---

## Documentation Updates (6.4)

### Files to Update

#### 1. `/CLAUDE.md` - Add Route Management Section

Add to "Development Commands" section:

```markdown
### Route Management

**Upload a KML route:**
```bash
curl -X POST \
  -F "file=@myroute.kml" \
  http://localhost:8000/api/routes/upload
```

**List all routes:**
```bash
curl http://localhost:8000/api/routes
```

**Activate a route:**
```bash
curl -X POST http://localhost:8000/api/routes/{route_id}/activate
```

**Deactivate all routes:**
```bash
curl -X POST http://localhost:8000/api/routes/deactivate
```

**Delete a route:**
```bash
curl -X DELETE http://localhost:8000/api/routes/{route_id}
```

**Access Route Management UI:**
- Browser: http://localhost:8000/ui/routes
```

#### 2. `docs/design-document.md` - Update API Reference

Update Section 4 with new endpoints:
- POST /api/routes/upload
- GET /api/routes
- GET /api/routes/{route_id}
- POST /api/routes/{route_id}/activate
- POST /api/routes/deactivate
- DELETE /api/routes/{route_id}
- GET /api/routes/{route_id}/download
- GET /api/routes/{route_id}/stats
- GET /api/route.geojson
- GET /api/route/coordinates

#### 3. `docs/design-document.md` - Update Section 5 (KML & Routes)

Add details on:
- Route file structure requirements
- POI import capabilities
- Simulation mode route following
- Metrics exported

#### 4. Create `docs/route-user-guide.md`

New document with:
- Quick start guide
- Screenshots of route management UI
- Steps to upload and activate routes
- Troubleshooting common issues
- Example KML file format

#### 5. Update `README.md`

Add Route Management section:
- Link to route user guide
- Features summary
- Supported KML formats

#### 6. Create `docs/API-REFERENCE.md` (if not exists)

Document all route endpoints with:
- Request/response examples
- Query parameters
- Error codes
- Authentication (if applicable)

### Documentation Checklist

- [ ] CLAUDE.md route management section added
- [ ] design-document.md Section 4 (APIs) updated
- [ ] design-document.md Section 5 (KML & Routes) updated
- [ ] route-user-guide.md created
- [ ] API-REFERENCE.md created/updated
- [ ] README.md route section added
- [ ] All documentation reviewed for accuracy
- [ ] Screenshots taken and added to guides
- [ ] Troubleshooting guide created

---

## Sample KML Files (6.6)

### Files to Create

#### 1. `data/sample_routes/simple-circular.kml`
- **Description:** Simple circular route around known city
- **Points:** ~20 waypoints
- **Distance:** ~50 km
- **Use Case:** Testing basic functionality
- **Source:** Generate procedurally or use real route

#### 2. `data/sample_routes/cross-country.kml`
- **Description:** Long-distance route across region
- **Points:** ~100+ waypoints
- **Distance:** ~2000+ km
- **Use Case:** Testing performance with complex routes
- **Source:** Real flight plan or procedural generation

#### 3. `data/sample_routes/with-embedded-pois.kml`
- **Description:** Route with embedded Placemark waypoints
- **Points:** ~30 waypoints + 5 POIs
- **Distance:** ~300 km
- **Use Case:** Testing POI import and integration
- **Source:** Create with route + POI markers

#### 4. `data/sample_routes/invalid-malformed.kml`
- **Description:** Intentionally malformed KML
- **Issues:** Missing closing tags, invalid structure
- **Use Case:** Testing error handling
- **Source:** Create with various error types

### Sample KML Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Sample Route</name>
    <Placemark>
      <name>Route Segment</name>
      <LineString>
        <coordinates>
          -122.0,37.0,0
          -122.1,37.1,1000
          -122.2,37.2,2000
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Point of Interest</name>
      <Point>
        <coordinates>-122.0,37.0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
```

### Sample KML Checklist

- [ ] simple-circular.kml created and validated
- [ ] cross-country.kml created and validated
- [ ] with-embedded-pois.kml created and validated
- [ ] invalid-malformed.kml created
- [ ] All samples tested with parser
- [ ] README created describing each sample
- [ ] Samples added to data/sample_routes/

---

## Automated Testing (6.5)

### Test Structure

Create `backend/starlink-location/tests/test_routes.py` with:

```python
# Unit Tests
- test_parse_simple_kml()
- test_parse_complex_kml()
- test_parse_invalid_kml()
- test_calculate_distance()
- test_route_activation()

# Integration Tests
- test_upload_route_flow()
- test_route_geojson_generation()
- test_poi_import_with_route()
- test_route_simulation_following()

# API Tests
- test_upload_endpoint()
- test_list_routes_endpoint()
- test_activate_route_endpoint()
- test_delete_route_endpoint()
```

### Testing Checklist

- [ ] Test file created: tests/test_routes.py
- [ ] Unit tests written for parser
- [ ] Unit tests written for route manager
- [ ] Integration tests written for upload flow
- [ ] API endpoint tests written
- [ ] All tests passing locally
- [ ] Test coverage > 80%
- [ ] CI configuration updated (if applicable)

---

## Testing Execution Timeline

### Day 1 (Today)
- [ ] Set up test environment
- [ ] Execute end-to-end tests (6.1)
- [ ] Document any issues found
- [ ] Plan fixes

### Day 2
- [ ] Execute UI/UX tests (6.2)
- [ ] Execute performance tests (6.3)
- [ ] Create sample KML files (6.6)
- [ ] Document results

### Day 3
- [ ] Write automated tests (6.5)
- [ ] Fix any issues from testing
- [ ] Update documentation (6.4)
- [ ] Final review and validation

### Day 4 (Finalization)
- [ ] Create Phase 6 summary
- [ ] Prepare task checklist for Phase 7
- [ ] Code review and cleanup
- [ ] Ready for Phase 7

---

## Success Criteria

### Phase 6 Complete When:

- ✅ All 8 end-to-end tests pass
- ✅ UI/UX testing complete and documented
- ✅ Performance metrics meet targets
- ✅ Integration tests all pass
- ✅ Sample KML files created (4 types)
- ✅ Documentation updated (6 files)
- ✅ Automated test suite written (> 80% coverage)
- ✅ No open bugs or critical issues
- ✅ All changes documented in Session Notes

### Phase 6 Success Indicators:

- **No crashes** in any test scenario
- **Performance acceptable** (meets targets)
- **Documentation complete** and accurate
- **Sample files provided** for users
- **Test coverage > 80%** of new code
- **Codebase ready** for Phase 7 PR

---

## Risk Mitigation

### Identified Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Edge cases discovered | Medium | Medium | Test with diverse KML sources |
| Performance issues with large files | Low | Medium | Load testing with 1000+ point routes |
| Documentation gaps | Medium | Low | Review all updated docs |
| Broken integration between phases | Low | High | Execute full workflow tests |

### Contingency Plans

**If tests fail:**
1. Document specific failure
2. Create issue in task list
3. Debug in isolated environment
4. Fix and re-test
5. Update documentation if needed

**If performance issues found:**
1. Profile with appropriate tools
2. Identify bottleneck
3. Optimize or redesign
4. Re-test and validate

---

## Phase 6 Session Notes Template

**Date:** [Session date]
**Focus:** [Specific testing area]
**Results:** [Summary of findings]
**Issues Found:** [Any bugs or issues]
**Fixes Applied:** [Solutions implemented]
**Status:** [Complete or In Progress]

---

## Next Phase (Phase 7)

Once Phase 6 is complete, Phase 7 will involve:
- Code review and cleanup
- Pull request creation
- Code review feedback addressed
- Merge to dev branch
- Production monitoring

---

**Plan Created:** 2025-11-03 Session 15
**Responsible:** Claude Code
**Status:** Approved for execution
