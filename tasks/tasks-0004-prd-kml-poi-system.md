# Task List: KML Route Loader & POI System

**PRD Reference:** `0004-prd-kml-poi-system.md`
**Phase:** 4
**Created:** 2025-10-23

---

## Current State Assessment

### Existing Infrastructure
- ✅ FastAPI application structure in place (`app.py`, `main.py`)
- ✅ Simulation framework exists (`app/simulation/`)
- ✅ Route generation utilities (`app/simulation/route.py`) with CircularRoute and StraightRoute classes
- ✅ Haversine calculations already implemented in `route.py`
- ✅ Configuration management system (`app/core/config.py`)
- ✅ Prometheus metrics infrastructure (`app/core/metrics.py`)
- ✅ Docker volumes configured for `/data/routes` and `/data/sim_routes`
- ✅ Test infrastructure with pytest

### Gaps to Address
- ❌ No KML parsing capability
- ❌ No file watching system for route detection
- ❌ No POI data models or storage
- ❌ No POI API endpoints
- ❌ No GeoJSON conversion/serving
- ❌ No ETA/distance calculation for POIs
- ❌ No smoothed speed averaging
- ❌ Simulation doesn't follow KML routes

---

## Relevant Files

### New Files to Create
- `app/models/poi.py` - POI data models (Pydantic schemas)
- `app/models/route.py` - Route/KML data models
- `app/services/kml_parser.py` - KML to Python object conversion
- `app/services/geojson.py` - GeoJSON generation service
- `app/services/poi_manager.py` - POI storage and retrieval
- `app/services/route_manager.py` - Route file watching and management
- `app/services/eta_calculator.py` - ETA and distance calculations with speed smoothing
- `app/api/routes.py` - Route management API endpoints
- `app/api/pois.py` - POI CRUD API endpoints
- `app/api/geojson.py` - GeoJSON serving endpoint
- `app/simulation/kml_follower.py` - KML route following for simulation
- `tests/unit/test_kml_parser.py` - KML parser tests
- `tests/unit/test_geojson.py` - GeoJSON generation tests
- `tests/unit/test_poi_manager.py` - POI management tests
- `tests/unit/test_route_manager.py` - Route manager tests
- `tests/unit/test_eta_calculator.py` - ETA calculation tests
- `tests/unit/test_kml_follower.py` - KML follower tests
- `tests/integration/test_route_api.py` - Route API integration tests
- `tests/integration/test_poi_api.py` - POI API integration tests

### Files to Modify
- `backend/starlink-location/requirements.txt` - Add fastkml, watchdog, geojson libraries
- `backend/starlink-location/main.py` - Integrate background tasks for file watching and ETA calculations
- `backend/starlink-location/app.py` - Register new API routers
- `app/core/metrics.py` - Add POI-related Prometheus metrics
- `app/models/config.py` - Add simulation speed multiplier configuration
- `app/simulation/coordinator.py` - Integrate KML route following
- `backend/starlink-location/config.yaml` - Add default POI and route settings
- `data/pois.json` - POI storage file (create during runtime)

### Notes
- Tests use pytest and should be run with `pytest` or `pytest tests/unit/test_file.py` for specific files
- All API endpoints follow RESTful conventions with JSON responses
- Use existing Haversine functions from `app/simulation/route.py` where possible

---

## Tasks

- [ ] 1.0 Set up KML parsing and file watching infrastructure
  - [ ] 1.1 Add required dependencies to `requirements.txt`: `fastkml>=2.0.0`, `watchdog>=3.0.0`, `geojson>=3.0.0`
  - [ ] 1.2 Create `app/models/route.py` with Pydantic models: `RoutePoint`, `RouteMetadata`, `ParsedRoute`
  - [ ] 1.3 Create `app/services/kml_parser.py` with `parse_kml_file()` function to convert KML to `ParsedRoute` objects
  - [ ] 1.4 Create `app/services/route_manager.py` with `RouteManager` class that uses `watchdog` to monitor `/data/routes/`
  - [ ] 1.5 Implement route list/get/activate methods in `RouteManager` (stores active route in memory)
  - [ ] 1.6 Add error handling for invalid KML files (log warning, skip file, notify via status endpoint)
  - [ ] 1.7 Create `tests/unit/test_kml_parser.py` with sample KML fixtures and test valid/invalid parsing
  - [ ] 1.8 Create `tests/unit/test_route_manager.py` to test file watching, route activation, and error handling

- [ ] 2.0 Implement POI data models, storage, and API endpoints
  - [ ] 2.1 Create `app/models/poi.py` with `POI`, `POICreate`, `POIUpdate`, `POIResponse` Pydantic models
  - [ ] 2.2 Ensure `POI` model includes: `id`, `name`, `latitude`, `longitude`, `icon`, optional `category`, `description`
  - [ ] 2.3 Create `app/services/poi_manager.py` with `POIManager` class for loading/saving POIs from `/data/pois.json`
  - [ ] 2.4 Implement `POIManager` methods: `list_pois()`, `get_poi(id)`, `create_poi()`, `update_poi()`, `delete_poi()`
  - [ ] 2.5 Support both global POIs and route-specific POIs in JSON structure (see PRD section 6.3)
  - [ ] 2.6 Create `app/api/pois.py` with FastAPI router for POI CRUD endpoints (`GET /api/pois`, `POST /api/pois`, etc.)
  - [ ] 2.7 Add request validation and error responses (400 for invalid input, 404 for missing POI)
  - [ ] 2.8 Create `tests/unit/test_poi_manager.py` to test POI storage, retrieval, and JSON persistence
  - [ ] 2.9 Create initial `/data/pois.json` file with empty structure during first run if it doesn't exist

- [ ] 3.0 Build GeoJSON conversion and serving system
  - [ ] 3.1 Create `app/services/geojson.py` with `GeoJSONBuilder` class
  - [ ] 3.2 Implement `build_route_feature()` to convert `ParsedRoute` to GeoJSON LineString feature
  - [ ] 3.3 Implement `build_poi_feature()` to convert `POI` to GeoJSON Point feature with properties
  - [ ] 3.4 Implement `build_current_position_feature()` to create Point feature from current telemetry
  - [ ] 3.5 Implement `build_feature_collection()` to combine route + POIs + current position into FeatureCollection
  - [ ] 3.6 Create `app/api/geojson.py` with `GET /route.geojson` endpoint that returns current FeatureCollection
  - [ ] 3.7 Handle edge cases: no route loaded (return POIs + position only), no POIs (return route + position)
  - [ ] 3.8 Create `tests/unit/test_geojson.py` to validate GeoJSON structure matches PRD specification (section 6.2)
  - [ ] 3.9 Test that coordinates are in [lon, lat] order (GeoJSON standard, not lat/lon)

- [ ] 4.0 Implement ETA and distance calculations with speed smoothing
  - [ ] 4.1 Create `app/services/eta_calculator.py` with `ETACalculator` class
  - [ ] 4.2 Implement speed smoothing using exponential moving average or rolling window (5x update interval per PRQ-4.3.3)
  - [ ] 4.3 Add `update_speed(current_speed)` method to maintain smoothed average
  - [ ] 4.4 Implement `calculate_distance(lat1, lon1, lat2, lon2)` using Haversine formula (reuse from `app/simulation/route.py`)
  - [ ] 4.5 Implement `calculate_eta(distance_meters, smoothed_speed_knots)` returning seconds (handle zero speed case)
  - [ ] 4.6 Implement `calculate_poi_metrics(current_position, pois)` returning dict of `{poi_id: {eta, distance, passed}}`
  - [ ] 4.7 Add 100-meter distance threshold logic to detect when POI is passed (REQ-4.3.6)
  - [ ] 4.8 Support negative ETA values for passed POIs
  - [ ] 4.9 Create `tests/unit/test_eta_calculator.py` with test cases for speed smoothing, distance, ETA, and passed POIs

- [ ] 5.0 Integrate KML route following into simulation engine
  - [ ] 5.1 Create `app/simulation/kml_follower.py` with `KMLRouteFollower` class
  - [ ] 5.2 Implement `load_kml_route(file_path)` to parse KML from `/data/sim_routes/` directory
  - [ ] 5.3 Implement `get_position(progress)` to return lat/lon/heading along route with realistic deviations (±0.0001-0.001 degrees)
  - [ ] 5.4 Add wrapping logic to loop back to start when route completes (REQ-4.4.5)
  - [ ] 5.5 Add `simulation_speed_multiplier` to `app/models/config.py` (default 1.0, range 0.1-10.0)
  - [ ] 5.6 Modify `app/simulation/coordinator.py` to check for KML routes in `/data/sim_routes/` at startup
  - [ ] 5.7 If KML route found, use `KMLRouteFollower` instead of `CircularRoute` or `StraightRoute`
  - [ ] 5.8 Apply speed multiplier to simulation update rate
  - [ ] 5.9 Create `tests/unit/test_kml_follower.py` to test route loading, position generation, deviations, and looping

- [ ] 6.0 Add Prometheus metrics for POI tracking
  - [ ] 6.1 Add POI metric definitions to `app/core/metrics.py`: `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters` (both Gauges with labels `name`, `id`)
  - [ ] 6.2 Create background task in `main.py` to run ETA calculations every update interval (2-5 seconds)
  - [ ] 6.3 Integrate `ETACalculator` to compute metrics for all POIs on each update
  - [ ] 6.4 Update Prometheus gauges with calculated ETA and distance values
  - [ ] 6.5 Handle edge cases: no POIs (skip metrics), no speed data (set ETA to -1), distance at threshold (ETA = 0)
  - [ ] 6.6 Test metric export by calling `/metrics` endpoint and validating output format

- [ ] 7.0 Integration testing and validation
  - [ ] 7.1 Create `tests/integration/test_route_api.py` to test full route upload/list/activate workflow
  - [ ] 7.2 Create `tests/integration/test_poi_api.py` to test POI CRUD operations end-to-end
  - [ ] 7.3 Create integration test for file watching: add KML to `/data/routes/`, verify it appears in route list
  - [ ] 7.4 Test `/route.geojson` endpoint returns valid GeoJSON with all components
  - [ ] 7.5 Test ETA calculations update in real-time during simulation
  - [ ] 7.6 Validate Prometheus metrics appear with correct labels and values
  - [ ] 7.7 Test error scenarios: invalid KML upload, deleted active route, missing POI file
  - [ ] 7.8 Run full stack with `docker compose up` and verify all features work together
  - [ ] 7.9 Create sample KML route and POI configuration for demo/validation purposes
  - [ ] 7.10 Document any deviations from PRD requirements and create follow-up tasks if needed

---

**Phase 2 Complete: Detailed sub-tasks generated.**

All tasks are now ready for implementation. Each sub-task is actionable and includes specific file paths, function names, and acceptance criteria based on the PRD.
