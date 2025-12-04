# Route API Endpoints

Complete reference for the Route Management API endpoints and response models.

## Overview

The Starlink Dashboard backend implements a complete KML route management system
with support for route timing profiles, waypoint extraction, and POI
integration. The system uses FastAPI endpoints to expose route functionality and
integrates with the Prometheus metrics system.

## Current Route API Endpoints (8 Total)

### 1. List Routes

**Endpoint:** `GET /api/routes` **Response Model:** `RouteListResponse` **Query
Parameters:**

- `active` (optional bool): Filter by active status

Returns list of routes with metadata. Supports filtering by active status.

### 2. Get Route Details

**Endpoint:** `GET /api/routes/{route_id}` **Response Model:**
`RouteDetailResponse` **Path Parameters:**

- `route_id`: Route identifier (filename without .kml)

Returns complete route data including all points, waypoints, statistics, and
timing profile.

### 3. Activate Route

**Endpoint:** `POST /api/routes/{route_id}/activate` **Response Model:**
`RouteResponse`

Activates a route for tracking and simulation. Only one route can be active at a
time.

### 4. Deactivate Route

**Endpoint:** `POST /api/routes/deactivate` **Response Model:** `dict`

Deactivates the currently active route.

### 5. Get Route Statistics

**Endpoint:** `GET /api/routes/{route_id}/stats` **Response Model:**
`RouteStatsResponse`

Returns distance metrics and geographic bounds for a route.

### 6. Upload Route (KML File)

**Endpoint:** `POST /api/routes/upload` **Response Model:** `RouteResponse`
(HTTP 201) **Form Data:**

- `file`: KML file (multipart, .kml extension required)
- `import_pois` (optional query param, bool): Import waypoints as POIs

Uploads and parses a KML route file. Optional POI import from waypoint
placemarks.

### 7. Download Route (KML File)

**Endpoint:** `GET /api/routes/{route_id}/download`

Returns the original KML file with media type
`application/vnd.google-earth.kml+xml`.

### 8. Delete Route

**Endpoint:** `DELETE /api/routes/{route_id}` **Returns:** HTTP 204 No Content

Deletes route and cascades deletion of associated POIs.

---

## Response Models

| Model                   | Purpose                              | Fields                                                                                                             |
| ----------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| **RouteResponse**       | Basic route info (list/activate)     | id, name, description, point_count, is_active, imported_at, imported_poi_count, skipped_poi_count, has_timing_data |
| **RouteListResponse**   | List endpoint container              | routes[], total                                                                                                    |
| **RouteDetailResponse** | Full route with all data             | RouteResponse fields + file_path, points[], statistics, poi_count, waypoints[], timing_profile                     |
| **RoutePoint**          | Individual route coordinate          | latitude, longitude, altitude, sequence, expected_arrival_time, expected_segment_speed_knots                       |
| **RouteWaypoint**       | Extracted waypoint (Point placemark) | name, description, style_url, latitude, longitude, altitude, order, role, expected_arrival_time                    |
| **RouteTimingProfile**  | ETA and timing metadata              | departure_time, arrival_time, total_expected_duration_seconds, has_timing_data, segment_count_with_timing          |
| **RouteStatsResponse**  | Statistics only                      | distance_meters, distance_km, point_count, bounds                                                                  |

---

## File Locations

### API Endpoints

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/api/routes.py`
- Contains all 8 route endpoints
- Functions for validation, error handling, POI import coordination
- Uses global route_manager and poi_manager instances

### Response Model Definitions

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/models/route.py`
- RouteResponse, RouteListResponse, RouteDetailResponse
- RoutePoint, RouteWaypoint, RouteMetadata
- RouteTimingProfile, ParsedRoute, RouteStatsResponse

### Route Manager Service

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/services/route_manager.py`
- RouteManager class: File watching, route caching, active route tracking
- Methods: start_watching(), stop_watching(), list_routes(), get_route(),
  activate_route(), deactivate_route()
- RouteChangeHandler: Watchdog listener for file system events

### KML Parser Service

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/services/kml_parser.py`
- parse_kml_file(): Main parsing entry point
- Handles LineString (route segments) and Point (waypoints) geometries
- Extracts timing data from waypoint descriptions
- Calculates segment speeds from consecutive timestamps
- Key functions:
  - extract_timestamp_from_description(): Pattern "Time Over Waypoint:
    YYYY-MM-DD HH:MM:SSZ"
  - \_partition_placemarks(): Split placemarks into waypoints and segments
  - \_identify_primary_waypoints(): Identify departure/arrival from route name
  - \_build_primary_route(): Chain segments by matching endpoints
  - \_assign_waypoint_timestamps_to_points(): Map waypoint times to route points
  - \_calculate_segment_speeds(): Calculate speeds between timed points
  - \_build_route_timing_profile(): Create route-level ETA profile

### POI Manager Service

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/services/poi_manager.py`
- Methods: delete_route_pois(), count_pois(route_id=...)
- Used for route POI management and cascade deletion

### Metrics Export Integration

- **File:**
  `/home/brian/Projects/starlink-dashboard-dev/backend/starlink-location/app/api/metrics_export.py`
- GET /metrics endpoint
- Integrates active route with ETA calculation
- Updates Prometheus gauges for POI distance/ETA metrics
- Uses route_manager.get_active_route() for active route data

---

## Usage Examples

### Upload Route with POI Import

```bash
curl -X POST \
  -F "file=@flight-plan.kml" \
  -F "import_pois=true" \
  <http://localhost:8000/api/routes/upload>
```

### List Active Routes

```bash
curl "<http://localhost:8000/api/routes?active=true">
```

### Get Detailed Route with Timing

```bash
curl <http://localhost:8000/api/routes/{route_id}>
```

### Activate Route for Simulation

```bash
curl -X POST <http://localhost:8000/api/routes/{route_id}/activate>
```

### Download Route KML

```bash
curl -O <http://localhost:8000/api/routes/{route_id}/download>
```

---

## Testing

### Test Files

- `tests/integration/test_route_eta.py` - ETA extraction from real KML files
- `tests/unit/test_route_manager.py` - RouteManager functionality
- `tests/unit/test_route.py` - Route models and distance calculations
- `tests/unit/test_route_timing.py` - Timing profile and speed calculations
- `tests/unit/test_kml_parser.py` - KML parsing functionality

---

## Storage

- Routes stored as KML files in /data/routes/
- Route metadata cached in memory at runtime
- Prometheus integration for ETA and distance calculations
- POIs stored in /data/pois.json with route_id linking
