# Route API Implementation Guide

Detailed implementation information for the Route Management system.

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

## Phase 2 Enhancements (Recent)

Added comprehensive ETA/timing support:

- RouteTimingProfile model with departure/arrival times and duration
- expected_arrival_time and expected_segment_speed_knots fields on RoutePoint
- Timestamp extraction from waypoint descriptions
- Segment speed calculation between timed waypoints
- timing_profile field in response models
- has_timing_data flag for routes with timing metadata
- Integration with Prometheus ETA metrics
