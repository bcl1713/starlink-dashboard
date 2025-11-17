# Checklist for poi-active-field

**Branch:** `feat/poi-active-field`
**Folder:** `dev/active/poi-active-field/`
**Status:** In Progress
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Initialization

- [x] Ensure you are on the correct branch:
  - [x] Run:
    ```bash
    git branch
    ```
  - [x] Confirm that the current branch line is:
    ```text
    * feat/poi-active-field
    ```
  - [x] If you are on a different branch, switch with:
    ```bash
    git checkout feat/poi-active-field
    ```

---

## Phase 1: Preparation (Complete)

This phase is already complete - the branch, plan documents, and codebase
exploration are done.

---

## Phase 2: Model Updates

### Task 2.1: Add `active` field to POIResponse model

- [x] Open the file:
  ```bash
  # Just for reference - use your editor/Read tool
  backend/starlink-location/app/models/poi.py
  ```
- [x] Locate the `POIResponse` class (starts around line 141)
- [x] Add the `active` field after the existing fields
  - [x] Add this line in the appropriate position within the class:
    ```python
    active: bool = Field(
        ...,
        description="Whether this POI is currently active (based on associated route/mission active status)",
    )
    ```
  - [x] Place it after the `category` field and before the `Config` class
- [x] Expected result: `POIResponse` now has an `active: bool` field

### Task 2.2: Add `active` field to POIWithETA model

- [x] In the same file (`app/models/poi.py`), locate the `POIWithETA` class
  (starts around line 204)
- [x] Add the `active` field after the existing POI-related fields
  - [x] Add this line in the appropriate position within the class:
    ```python
    active: bool = Field(
        ...,
        description="Whether this POI is currently active (based on associated route/mission active status)",
    )
    ```
  - [x] Place it near the core POI fields (after `category`, before ETA fields
    like `eta_seconds`)
- [x] Expected result: `POIWithETA` now has an `active: bool` field

### Task 2.3: Commit model changes

- [x] Stage the changes:
  ```bash
  git add backend/starlink-location/app/models/poi.py
  ```
- [x] Commit with message:
  ```bash
  git commit -m "feat: add active field to POI response models"
  ```
- [x] Push to remote:
  ```bash
  git push -u origin feat/poi-active-field
  ```
- [x] Expected result: Changes are committed and pushed to the feature branch

---

## Phase 3: API Endpoint Updates

### Task 3.1: Add helper function to calculate active status

- [x] Open the file:
  ```bash
  # Just for reference - use your editor/Read tool
  backend/starlink-location/app/api/pois.py
  ```
- [x] Add a new helper function near the top of the file (after imports, before
  endpoint definitions)
  - [x] Add this complete function:
    ```python
    def _calculate_poi_active_status(
        poi: POI,
        route_manager: RouteManager,
        mission_storage,
    ) -> bool:
        """
        Calculate whether a POI is currently active based on its associated
        route or mission.

        Logic:
        - Global POIs (no route_id/mission_id): always active
        - Route POIs: active if their route is the active route
        - Mission POIs: active if their mission has is_active=true

        Args:
            poi: The POI to check
            route_manager: RouteManager instance to check active route
            mission_storage: Mission storage instance to check mission status

        Returns:
            bool: True if POI is active, False otherwise
        """
        # Global POIs are always active
        if poi.route_id is None and poi.mission_id is None:
            return True

        # Check route-based POIs
        if poi.route_id is not None:
            active_route = route_manager.get_active_route()
            return active_route is not None and active_route.id == poi.route_id

        # Check mission-based POIs
        if poi.mission_id is not None:
            try:
                mission = mission_storage.load_mission(poi.mission_id)
                return mission.is_active if mission else False
            except Exception:
                # Mission not found or error loading
                return False

        return False
    ```
- [x] Expected result: Helper function is added and ready to use

### Task 3.2: Update GET /api/pois/etas endpoint - Add parameter and imports

- [x] Locate the `/api/pois/etas` endpoint function (around line 181)
- [x] Add the `active_only` query parameter to the function signature
  - [x] Find the existing parameters like `route_id`, `status_filter`,
    `category`
  - [x] Add this new parameter:
    ```python
    active_only: bool = Query(
        True,
        description="Filter to show only active POIs (default: true). Set to false to see all POIs with active field populated.",
    ),
    ```
- [x] Ensure necessary imports are present at the top of the file:
  - [x] Check for: `from app.mission.storage import MissionStorage`
  - [x] Check for: `from app.mission.routes import get_active_mission_id`
  - [x] If missing, add them to the imports section
- [x] Expected result: Endpoint signature includes `active_only` parameter

### Task 3.3: Update GET /api/pois/etas endpoint - Calculate and filter by
active status

- [x] In the `/api/pois/etas` endpoint function, find where POIs are retrieved
  (around line 310):
  ```python
  pois = poi_manager.list_pois(route_id=route_id)
  ```
- [x] After the POI loop where `POIWithETA` objects are created (around line
  480), add active status calculation and filtering:
  - [x] Find the section where `pois_with_eta` list is built
  - [x] For each POI being added to `pois_with_eta`, calculate its active status
    using the helper function
  - [x] Add the active status to the `POIWithETA` object creation
  - [x] After all POIs are processed, filter by `active_only` if needed
  - [x] The logic should look like this (adapt to fit the existing code
    structure):
    ```python
    # Inside the loop where POIWithETA objects are created:
    active_status = _calculate_poi_active_status(
        poi=poi,
        route_manager=route_manager,
        mission_storage=MissionStorage(),  # Or get from dependency injection if available
    )

    poi_with_eta = POIWithETA(
        # ... existing fields ...
        active=active_status,
        # ... rest of fields ...
    )

    # After building the list, before sorting:
    if active_only:
        pois_with_eta = [p for p in pois_with_eta if p.active]
    ```
- [x] Expected result: Endpoint calculates `active` for each POI and filters if
  `active_only=True`

### Task 3.4: Update GET /api/pois endpoint - Add parameter

- [x] Locate the `/api/pois` endpoint function (around line 113)
- [x] Add the `active_only` query parameter to the function signature:
  ```python
  active_only: bool = Query(
      True,
      description="Filter to show only active POIs (default: true). Set to false to see all POIs with active field populated.",
  ),
  ```
- [x] Expected result: `/api/pois` endpoint signature includes `active_only`
  parameter

### Task 3.5: Update GET /api/pois endpoint - Calculate and filter by active
status

- [x] In the `/api/pois` endpoint function, find where `POIResponse` objects are
  created (likely in a list comprehension or loop)
- [x] For each POI, calculate active status using the helper function
- [x] Add the `active` field to the `POIResponse` object creation
- [x] Filter the results based on `active_only` parameter
- [x] The logic should look like this (adapt to existing structure):
  ```python
  # When building POIResponse objects:
  responses = []
  for poi in pois:
      active_status = _calculate_poi_active_status(
          poi=poi,
          route_manager=route_manager,
          mission_storage=MissionStorage(),
      )

      poi_response = POIResponse(
          # ... existing fields ...
          active=active_status,
          # ... rest of fields ...
      )

      responses.append(poi_response)

  # Apply filtering if needed:
  if active_only:
      responses = [r for r in responses if r.active]
  ```
- [x] Expected result: `/api/pois` calculates `active` and filters by
  `active_only`

### Task 3.6: Commit API endpoint changes

- [x] Stage the changes:
  ```bash
  git add backend/starlink-location/app/api/pois.py
  ```
- [x] Commit with message:
  ```bash
  git commit -m "feat: add active filtering to POI endpoints"
  ```
- [x] Push to remote:
  ```bash
  git push
  ```
- [x] Expected result: API changes are committed and pushed

---

## Phase 4: Testing & Verification

### Task 4.1: Rebuild Docker containers

- [ ] **CRITICAL:** Stop, rebuild, and restart all containers:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- [ ] Wait for services to become healthy:
  ```bash
  docker compose ps
  ```
- [ ] Expected result: All containers show "healthy" status
- [ ] Verify backend is running:
  ```bash
  curl http://localhost:8000/health
  ```
- [ ] Expected result: JSON response with `"status": "ok"`

### Task 4.2: Test global POIs

- [ ] Create a test global POI (no route_id or mission_id):
  ```bash
  curl -X POST http://localhost:8000/api/pois \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Global Test POI",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "category": "waypoint"
    }'
  ```
- [ ] Expected result: POI created successfully
- [ ] Retrieve POIs with ETAs:
  ```bash
  curl http://localhost:8000/api/pois/etas
  ```
- [ ] Expected result: Response includes the global POI with `"active": true`
- [ ] Clean up: Delete the test POI (use the ID from creation response):
  ```bash
  curl -X DELETE http://localhost:8000/api/pois/{poi_id}
  ```

### Task 4.3: Test route POIs - Active scenario

- [ ] Upload a test route:
  ```bash
  curl -X POST http://localhost:8000/api/routes/upload \
    -F "file=@/data/sample_routes/simple-circular.kml"
  ```
- [ ] Note the route ID from the response
- [ ] Activate the route:
  ```bash
  curl -X POST http://localhost:8000/api/routes/{route_id}/activate
  ```
- [ ] Create a POI associated with this route:
  ```bash
  curl -X POST http://localhost:8000/api/pois \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Route Test POI",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "category": "waypoint",
      "route_id": "{route_id}"
    }'
  ```
- [ ] Retrieve POIs with ETAs:
  ```bash
  curl http://localhost:8000/api/pois/etas
  ```
- [ ] Expected result: POI appears in response with `"active": true`

### Task 4.4: Test route POIs - Inactive scenario

- [ ] Deactivate all routes:
  ```bash
  curl -X POST http://localhost:8000/api/routes/deactivate
  ```
- [ ] Retrieve POIs with default filtering:
  ```bash
  curl http://localhost:8000/api/pois/etas
  ```
- [ ] Expected result: Route POI is **NOT** in response (filtered out)
- [ ] Retrieve POIs with `active_only=false`:
  ```bash
  curl http://localhost:8000/api/pois/etas?active_only=false
  ```
- [ ] Expected result: Route POI **IS** in response with `"active": false`
- [ ] Clean up: Delete the test route POI and route

### Task 4.5: Test mission POIs (if mission system is available)

- [ ] Create and activate a test mission (refer to mission API docs)
- [ ] Create a POI associated with the mission
- [ ] Verify POI shows as `"active": true` when mission is active
- [ ] Deactivate the mission
- [ ] Verify POI is filtered out by default
- [ ] Verify POI shows `"active": false` with `?active_only=false`
- [ ] Clean up test data

### Task 4.6: Test /api/pois endpoint

- [ ] Repeat similar tests for the `/api/pois` endpoint:
  ```bash
  curl http://localhost:8000/api/pois
  curl http://localhost:8000/api/pois?active_only=false
  ```
- [ ] Expected result: Filtering works identically to `/api/pois/etas`

### Task 4.7: Check backend logs for errors

- [ ] View backend logs:
  ```bash
  docker logs starlink-location | tail -n 100
  ```
- [ ] Expected result: No errors or warnings related to POI active status
- [ ] If errors exist, debug and fix before proceeding

---

## Documentation Maintenance

- [ ] Update PLAN.md status to "Completed" when all tasks are done
- [ ] Update CONTEXT.md if any assumptions or risks changed during
  implementation
- [ ] Add entry to dev/LESSONS-LEARNED.md if anything surprising happened:
  - [ ] Open `dev/LESSONS-LEARNED.md`
  - [ ] Add dated entry with what was learned
  - [ ] Commit the update

---

## Verification Tasks

- [ ] Confirm all objectives from PLAN.md are met:
  - [ ] POI response models include `active: bool` field
  - [ ] Active status logic works for global POIs
  - [ ] Active status logic works for route POIs
  - [ ] Active status logic works for mission POIs
  - [ ] `/api/pois/etas` accepts `active_only` parameter
  - [ ] `/api/pois` accepts `active_only` parameter
  - [ ] API responses filter correctly when `active_only=true`
  - [ ] API responses include all POIs when `active_only=false`
  - [ ] Docker rebuild completed successfully

---

## Pre-Wrap Checklist

All of the following must be checked before handoff to `wrapping-up-plan`:

- [ ] All implementation tasks above are marked `- [x]`
- [ ] All verification tests passed
- [ ] No TODOs remain in code
- [ ] Backend runs without errors: `docker logs starlink-location`
- [ ] PLAN.md updated to "Completed" status
- [ ] CONTEXT.md finalized
- [ ] LESSONS-LEARNED.md updated if applicable
- [ ] All changes committed and pushed to feature branch
