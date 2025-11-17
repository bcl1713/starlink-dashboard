# Context for poi-active-field

**Branch:** `feat/poi-active-field`
**Folder:** `dev/active/poi-active-field/`
**Last Updated:** 2025-11-17
**Reviewed:** 2025-11-17 - All assumptions and risks remain valid

---

## Background

The `/api/pois/etas` endpoint currently returns all POIs regardless of whether
their associated route or mission is active. This creates confusion in the UI
because POIs from inactive missions and routes are displayed alongside active
ones, with no way to distinguish or filter them. Users need to see only POIs
relevant to the currently active route or mission unless they explicitly request
otherwise. This work adds a computed `active` boolean field to POI responses and
implements filtering to address this limitation.

---

## Relevant Code Locations

### POI Models

- `backend/starlink-location/app/models/poi.py` — POI model definitions
  - Lines 9-53: `POI` core model (has `route_id` and `mission_id` fields)
  - Lines 141-181: `POIResponse` model (needs `active` field)
  - Lines 204-267: `POIWithETA` model (needs `active` field)
  - Lines 270-288: `POIETAListResponse` wrapper

### POI API Endpoints

- `backend/starlink-location/app/api/pois.py` — POI endpoints
  - Lines 113-178: GET `/api/pois` (needs `active_only` parameter)
  - Lines 181-491: GET `/api/pois/etas` (needs `active_only` parameter and
    active calculation)
  - Line 310: Current POI retrieval logic

### Route System

- `backend/starlink-location/app/models/route.py`
  - Lines 211-243: `RouteResponse` (has `is_active` field at line 218)
- `backend/starlink-location/app/services/route_manager.py`
  - Line 238: `_active_route_id` in-memory tracking
  - Lines 220-249: `activate_route()` method
  - Lines 209-218: `get_active_route()` method

### Mission System

- `backend/starlink-location/app/mission/models.py`
  - Lines 294-361: `Mission` model (has `is_active` field at lines 331-334)
- `backend/starlink-location/app/mission/routes.py`
  - Line 883: `_active_mission_id` global variable
  - Lines 864-939: `activate_mission()` function
  - Lines 304-335: `get_active_mission()` function
  - Lines 1108-1110: `get_active_mission_id()` function
- `backend/starlink-location/app/mission/storage.py`
  - Mission persistence to `/data/missions/` directory

---

## Dependencies

- **FastAPI:** Backend web framework
- **Pydantic:** Data validation and model definitions
- **Docker:** Containerization (requires `--no-cache` rebuild for Python
  changes)
- **RouteManager service:** Provides active route information
- **Mission storage system:** Provides active mission information
- **POIManager service:** Manages POI storage and retrieval

### Environment

- No new environment variables required
- Uses existing `/data/pois.json` storage
- Uses existing route and mission activation mechanisms

---

## Constraints & Assumptions

- Only one route can be active at a time (enforced by RouteManager)
- Only one mission can be active at a time (enforced by mission activation)
- Global POIs (no `route_id` or `mission_id`) are always considered active
- Active status is computed on-demand, not persisted in POI storage
- The `active_only=true` default is a **breaking API change** but provides
  desired behavior
- Existing API consumers must explicitly pass `?active_only=false` to see all
  POIs

---

## Risks

- **Breaking change:** Default `active_only=true` may break existing API
  consumers that expect all POIs
  - Mitigation: Document in CHANGELOG, ensure parameter can be set to `false`
- **Performance:** Computing active status for many POIs could slow down
  responses
  - Mitigation: Active checks are simple boolean comparisons; minimal overhead
    expected
- **Synchronization:** If route/mission activation state is inconsistent, active
  field may be incorrect
  - Mitigation: Use existing activation mechanisms (RouteManager and mission
    storage)

---

## Testing Strategy

Define exactly what "done and verified" means:

### Unit Test Coverage (if tests exist)

- Active status calculation for global POIs returns `true`
- Active status calculation for route POIs checks active route
- Active status calculation for mission POIs checks mission `is_active`

### Manual Test Steps

1. **Setup:**
   - Run: `docker compose down && docker compose build --no-cache && docker
     compose up -d`
   - Wait for containers to be healthy: `docker compose ps`

2. **Test Global POIs:**
   - Create a POI with no `route_id` or `mission_id`
   - Call: `curl http://localhost:8000/api/pois/etas`
   - Confirm POI has `"active": true`

3. **Test Route POIs - Active:**
   - Upload and activate a route
   - Create a POI associated with that route
   - Call: `curl http://localhost:8000/api/pois/etas`
   - Confirm POI has `"active": true`

4. **Test Route POIs - Inactive:**
   - Deactivate the route
   - Call: `curl http://localhost:8000/api/pois/etas`
   - Confirm POI is **not** in the response (filtered out)
   - Call: `curl http://localhost:8000/api/pois/etas?active_only=false`
   - Confirm POI is in response with `"active": false`

5. **Test Mission POIs - Active:**
   - Create and activate a mission
   - Create a POI associated with that mission
   - Call: `curl http://localhost:8000/api/pois/etas`
   - Confirm POI has `"active": true`

6. **Test Mission POIs - Inactive:**
   - Deactivate the mission
   - Call: `curl http://localhost:8000/api/pois/etas`
   - Confirm POI is **not** in the response
   - Call: `curl http://localhost:8000/api/pois/etas?active_only=false`
   - Confirm POI is in response with `"active": false`

7. **Test `/api/pois` endpoint:**
   - Repeat similar tests for `/api/pois` endpoint
   - Confirm `active_only` parameter works identically

8. **Check logs:**
   - Run: `docker logs starlink-location`
   - Confirm no errors or warnings

---

---

## Final Architecture Notes

### Implementation Pattern

The active status calculation follows a simple, efficient pattern:

1. **Helper Function** (`_calculate_poi_active_status`): Encapsulates all business logic
   - Takes POI object, RouteManager, and mission storage
   - Returns boolean indicating active status
   - Handles three scenarios: global, route-based, mission-based

2. **Endpoint Integration**:
   - Both `/api/pois` and `/api/pois/etas` call the helper during response building
   - Active status is computed at response time (not persisted)
   - Filtering applied after all active values are calculated

3. **Route ID Extraction**:
   - Critical detail: Use `Path(active_route.metadata.file_path).stem` to get route ID
   - ParsedRoute objects don't have direct `.id` attribute
   - See LESSONS-LEARNED.md entry for [2025-11-17]

### Backward Compatibility

- **Breaking Change:** Default `active_only=true` filters POIs from inactive routes/missions
- **Recovery Path:** Clients can use `?active_only=false` to get all POIs with `active` field populated
- **Migration Note:** API documentation should clearly state this change with examples

### Performance Characteristics

- **Time Complexity:** O(n) where n = number of POIs (single pass to calculate active status)
- **Space Complexity:** O(n) for response building (same as before)
- **Caching:** None needed; active status checks are simple boolean comparisons
- **Impact:** Negligible performance impact from active status calculation

### Error Handling

- Mission loading failures are caught and treated as inactive (safe fallback)
- Route manager lookups are direct and fast
- No null pointer risks due to early returns in helper function

## References

- POI system architecture: `docs/design-document.md` (section 5)
- Route management: `CLAUDE.md` (Route Management section)
- Mission system: `dev/completed/mission-comm-planning/` (archived feature)
