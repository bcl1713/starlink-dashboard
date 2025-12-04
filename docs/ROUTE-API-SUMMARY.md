# Starlink Dashboard Route API - Comprehensive Summary

## Overview

The Starlink Dashboard backend implements a complete KML route management system
with support for route timing profiles, waypoint extraction, and POI
integration. The system uses FastAPI endpoints to expose route functionality and
integrates with the Prometheus metrics system.

## Current Route API Endpoints (8 Total)

### 1. List Routes

**Endpoint:** `GET /api/routes`  
**Response Model:** `RouteListResponse`  
**Query Parameters:**

- `active` (optional bool): Filter by active status

Returns list of routes with metadata. Supports filtering by active status.

### 2. Get Route Details

**Endpoint:** `GET /api/routes/{route_id}`  
**Response Model:** `RouteDetailResponse`  
**Path Parameters:**

- `route_id`: Route identifier (filename without .kml)

Returns complete route data including all points, waypoints, statistics, and
timing profile.

### 3. Activate Route

**Endpoint:** `POST /api/routes/{route_id}/activate`  
**Response Model:** `RouteResponse`

Activates a route for tracking and simulation. Only one route can be active at a
time.

### 4. Deactivate Route

**Endpoint:** `POST /api/routes/deactivate`  
**Response Model:** `dict`

Deactivates the currently active route.

### 5. Get Route Statistics

**Endpoint:** `GET /api/routes/{route_id}/stats`  
**Response Model:** `RouteStatsResponse`

Returns distance metrics and geographic bounds for a route.

### 6. Upload Route (KML File)

**Endpoint:** `POST /api/routes/upload`  
**Response Model:** `RouteResponse` (HTTP 201)  
**Form Data:**

- `file`: KML file (multipart, .kml extension required)
- `import_pois` (optional query param, bool): Import waypoints as POIs

Uploads and parses a KML route file. Optional POI import from waypoint
placemarks.

### 7. Download Route (KML File)

**Endpoint:** `GET /api/routes/{route_id}/download`

Returns the original KML file with media type
`application/vnd.google-earth.kml+xml`.

### 8. Delete Route

**Endpoint:** `DELETE /api/routes/{route_id}`  
**Returns:** HTTP 204 No Content

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

### Response Models

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

## Current Integration with KML Parser

### Route Upload Flow

1. File uploaded via `POST /api/routes/upload`
2. File saved to `/data/routes/` directory
3. Watchdog detects file creation event
4. RouteManager.\_load_route_file() calls parse_kml_file()
5. parse_kml_file() returns ParsedRoute with:
   - Parsed route points (coordinates)
   - Extracted waypoints (Point placemarks)
   - Timing profile (if timestamps found)
6. Route cached in route_manager.\_routes
7. If import_pois=true, waypoints converted to POIs via
   \_import_waypoints_as_pois()

### Timestamp Extraction

- Parser searches waypoint descriptions for:
  `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
- Extracted times stored in RouteWaypoint.expected_arrival_time
- Times assigned to nearest route points within 1000m tolerance
- Speeds calculated between consecutive timed points

### Timing Profile Creation

- \_build_route_timing_profile() extracts:
  - Departure time from first waypoint or first timed point
  - Arrival time from last waypoint or last timed point
  - Total duration in seconds
- Counts segments with calculated speed data

### ETA Service Integration

- RouteTimingProfile accessible via GET /api/routes/{route_id}
- Prometheus /metrics endpoint uses timing data for ETA calculations
- Speed data from RoutePoint.expected_segment_speed_knots available for
  conversions

---

## Key Features

### Timing Data Extraction

- Extracts timestamps from waypoint descriptions using regex pattern
- Assigns times to nearest route points (tolerance: 1000m)
- Calculates segment speeds:
  `speed_knots = distance_meters / time_seconds * (3600 / 1852)`
- Builds route-level timing profile with departure/arrival/duration

### Route Segment Handling

- Supports multiple LineString geometries (multi-segment routes)
- Filters segments by style color (main route = ffddad05 orange, alternates =
  ffb3b3b3 gray)
- Chains segments by matching endpoint coordinates
- Falls back to flattening if color-filtered segments don't connect

### Waypoint Classification

- Identifies departure/arrival by parsing route name (format: "KADW-PHNL")
- Falls back to style_url matching (#destWaypointIcon)
- Falls back to first/last waypoint with coordinates
- Assigns roles: "departure", "arrival", "waypoint", "alternate"

### POI Integration

- Waypoints can be imported as POIs via import_pois=true parameter
- Waypoint roles mapped to POI categories/icons:
  - departure → category "departure", icon "airport"
  - arrival → category "arrival", icon "flag"
  - alternate → category "alternate", icon "star"
  - default → category "waypoint", icon "waypoint"
- Cascade delete: removing route removes associated POIs

### File Management

- Routes stored as KML files in /data/routes/ directory
- Directory watched for changes (create, modify, delete)
- Uses watchdog library with Observer pattern
- Routes auto-discovered and auto-removed based on file system events

---

## Data Flow Diagram

```text
KML Upload via /api/routes/upload
    ↓
File saved to /data/routes/
    ↓
Watchdog detects file creation
    ↓
RouteManager._load_route_file()
    ↓
parse_kml_file() returns ParsedRoute with:
  - RouteMetadata (name, description, file path)
  - RoutePoint[] (coordinates with timing if available)
  - RouteWaypoint[] (Point placemarks with extracted timestamps)
  - RouteTimingProfile (departure/arrival/duration/speeds)
    ↓
Cached in route_manager._routes
    ↓
(Optional) _import_waypoints_as_pois() for POI creation
    ↓
GET /api/routes/{route_id} → RouteDetailResponse
    ↓
GET /metrics → Uses timing data for ETA calculations
```

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

## Phase 2 Enhancements (Recent)

Added comprehensive ETA/timing support:

- RouteTimingProfile model with departure/arrival times and duration
- expected_arrival_time and expected_segment_speed_knots fields on RoutePoint
- Timestamp extraction from waypoint descriptions
- Segment speed calculation between timed waypoints
- timing_profile field in response models
- has_timing_data flag for routes with timing metadata
- Integration with Prometheus ETA metrics

---

## Storage

- Routes stored as KML files in /data/routes/
- Route metadata cached in memory at runtime
- Prometheus integration for ETA and distance calculations
- POIs stored in /data/pois.json with route_id linking
