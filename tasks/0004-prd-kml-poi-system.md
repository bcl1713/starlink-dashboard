# PRD: KML Route Loader & POI System

**Phase:** 4 **Feature Name:** KML Route Loader & POI System **Created:**
2025-10-23 **Status:** Draft

---

## 1. Introduction/Overview

This feature enables the Starlink monitoring system to display planned routes
and Points of Interest (POI) on the map dashboard, with real-time ETA and
distance calculations. Users can upload KML route files, define multiple POIs,
and track progress along planned journeys. This provides critical situational
awareness for mobile Starlink deployments (RVs, aircraft, maritime vessels,
etc.).

**Problem Statement:** Without route and POI visualization, users cannot:

- See their planned path overlaid on the real-time position map
- Know when they'll arrive at important waypoints or destinations
- Monitor progress against a planned route
- Prepare for connectivity changes at specific locations

**Goal:** Enable geographic context and journey planning capabilities by
integrating KML route visualization with real-time POI tracking and ETA
calculations.

---

## 2. Goals

1. **Support KML route uploads** for trajectory visualization on Grafana map
   panels
1. **Enable POI definition** with labels, icons, and optional metadata
   (categories, descriptions)
1. **Calculate and expose real-time ETA and distance metrics** for all defined
   POIs
1. **Support multiple routes** with leg-based selection (e.g., "Day 1", "Day 2",
   "Return Trip")
1. **Integrate with simulation mode** so simulated positions can follow uploaded
   routes with realistic deviations
1. **Serve route and POI data** in GeoJSON format for Grafana consumption

---

## 3. User Stories

### 3.1 Route Management

**As a** mobile Starlink operator, **I want to** upload a KML file containing my
planned route, **So that** I can see my intended path overlaid on the live map
and compare it to my actual trajectory.

**As a** user planning a multi-day trip, **I want to** upload multiple KML
routes and select which one is active for the current leg, **So that** I can
track different segments of my journey separately.

### 3.2 POI Tracking

**As a** user, **I want to** define Points of Interest (destinations, waypoints,
fuel stops, etc.), **So that** I can see how far away they are and when I'll
arrive.

**As a** user, **I want to** assign icons and categories to my POIs, **So that**
I can quickly identify different types of waypoints on the map (e.g., airport,
campsite, destination).

**As a** user, **I want to** see both global POIs (valid for all routes) and
route-specific POIs, **So that** I can have general waypoints plus
journey-specific markers.

### 3.3 ETA and Distance

**As a** user in motion, **I want to** see real-time ETA to all my POIs, **So
that** I can plan fuel stops, meal breaks, and arrival notifications.

**As a** user, **I want** ETA calculations to be based on smoothed average speed
(not instantaneous speed), **So that** the estimates are stable and realistic,
not jumping erratically.

**As a** user who has passed a waypoint, **I want** the POI to show negative ETA
values, **So that** I know how long ago I passed it (useful for logging).

### 3.4 Simulation Integration

**As a** developer or demo user, **I want** the simulator to follow uploaded KML
routes with realistic deviations, **So that** I can test the system behavior on
real flight paths without needing a live Starlink terminal.

**As a** developer, **I want** configurable simulation speed, **So that** I can
quickly test long routes or slow down to debug specific segments.

---

## 4. Functional Requirements

### 4.1 KML Route Management

**REQ-4.1.1:** The system MUST provide a `/data/routes/` directory where users
can upload KML route files.

**REQ-4.1.2:** The system MUST watch the `/data/routes/` directory for new or
modified `.kml` files.

**REQ-4.1.3:** When a new KML file is detected, the system MUST parse it and
queue it for manual activation (not auto-activate).

**REQ-4.1.4:** The system MUST support multiple KML routes stored
simultaneously.

**REQ-4.1.5:** The system MUST provide an API endpoint to list all available
routes (e.g., `GET /api/routes`).

**REQ-4.1.6:** The system MUST provide an API endpoint to select the active
route for the current leg (e.g., `POST /api/routes/activate?file=route1.kml`).

**REQ-4.1.7:** The system MUST NOT automatically delete or archive old KML
files.

**REQ-4.1.8:** The system MUST convert active KML routes to GeoJSON format.

**REQ-4.1.9:** The system MUST serve the active route as GeoJSON via the
`/route.geojson` endpoint.

**REQ-4.1.10:** The `/route.geojson` endpoint MUST return:

- The route path (LineString or MultiLineString)
- All POIs (both global and route-specific) as Point features
- Current position as a Point feature with distinct properties

**REQ-4.1.11:** The system MUST use the `fastkml` or `simplekml` library for KML
parsing.

**REQ-4.1.12:** The system MUST handle invalid or corrupted KML files gracefully
by:

- Logging an error with the filename and reason
- Notifying the user (via API status or health endpoint)
- Continuing to operate with the last valid route (if any)

**REQ-4.1.13:** The system MUST NOT perform route simplification (point
reduction) at this time.

### 4.2 POI Management

**REQ-4.2.1:** The system MUST support user-defined POIs via API endpoints (not
just configuration files).

**REQ-4.2.2:** Each POI MUST have the following required attributes:

- `id` (unique identifier)
- `name` (display label)
- `latitude` (decimal degrees)
- `longitude` (decimal degrees)
- `icon` (icon identifier or emoji)

**REQ-4.2.3:** Each POI MAY have the following optional attributes:

- `category` (e.g., "airport", "waypoint", "fuel", "destination")
- `description` (freeform text)

**REQ-4.2.4:** The system MUST support two types of POIs:

- **Global POIs:** Valid for all routes (e.g., home base, common destinations)
- **Route-specific POIs:** Associated with a particular KML route file

**REQ-4.2.5:** The system MUST store POI definitions in a JSON file (e.g.,
`/data/pois.json`).

**REQ-4.2.6:** The system MUST provide API endpoints for POI management:

- `GET /api/pois` → List all POIs
- `POST /api/pois` → Create a new POI
- `PUT /api/pois/{id}` → Update an existing POI
- `DELETE /api/pois/{id}` → Delete a POI

**REQ-4.2.7:** The system MUST support up to 50 POIs without performance
degradation.

**REQ-4.2.8:** POI data MUST be included in the `/route.geojson` response as
GeoJSON Point features with appropriate properties.

### 4.3 ETA and Distance Calculation

**REQ-4.3.1:** The system MUST calculate ETA (Estimated Time of Arrival) to all
defined POIs, regardless of whether they are on the active route.

**REQ-4.3.2:** ETA calculations MUST use the **smoothed average speed** over an
appropriate time window (see REQ-4.3.3).

**REQ-4.3.3:** The time window for average speed calculation MUST be:

- At least 5x the data update interval (e.g., if updates occur every 3 seconds,
  use a 15-second window)
- Smoothed using a moving average or exponential smoothing to prevent erratic
  jumps

**REQ-4.3.4:** Distance calculations MUST use the **Haversine formula**
(great-circle distance).

**REQ-4.3.5:** The system MUST expose the following Prometheus metrics for each
POI:

```text
starlink_eta_poi_seconds{name="POI_Name", id="POI_ID"}
starlink_distance_to_poi_meters{name="POI_Name", id="POI_ID"}
```

**REQ-4.3.6:** When a POI is passed, the system MUST:

- Continue calculating ETA (showing negative values to indicate time since
  passing)
- Use a **distance threshold** to determine when a POI is "passed":
  - If current position is within 100 meters of the POI, consider it "at" the
    POI
  - If current position was closer than 100m and is now moving away, consider it
    "passed"

**REQ-4.3.7:** ETA and distance metrics MUST update at the same frequency as
position updates (every 2–5 seconds per design document).

**REQ-4.3.8:** If no valid speed data is available (e.g., at startup), ETA MUST
be set to `-1` or marked as unavailable.

**REQ-4.3.9:** If distance to a POI is zero or below the threshold, ETA MUST be
`0`.

### 4.4 Simulation Mode Integration

**REQ-4.4.1:** When in simulation mode (`SIMULATION_MODE=true`), the simulator
MUST check for KML routes in the `/data/sim_routes/` directory.

**REQ-4.4.2:** If a KML route is found in `/data/sim_routes/`, the simulator
MUST:

- Use the route as a reference path
- Follow the route's waypoints sequentially
- Add realistic deviations (±0.0001–0.001 degrees lat/lon) to simulate GPS
  inaccuracy and course corrections

**REQ-4.4.3:** If no route is found in `/data/sim_routes/`, the simulator MUST
default to a circular or looping trajectory (per existing design).

**REQ-4.4.4:** The simulation MUST support a configurable speed multiplier:

- Exposed via environment variable: `SIMULATION_SPEED_MULTIPLIER` (default:
  `1.0`)
- Allowed range: `0.1` (10% speed) to `10.0` (10x speed)
- Used to speed up or slow down route playback for testing

**REQ-4.4.5:** The simulator MUST wrap around to the start of the route when it
reaches the end (looping behavior).

### 4.5 Error Handling

**REQ-4.5.1:** If no route is loaded but POIs are defined, the system MUST:

- Calculate straight-line distance and ETA to all POIs
- Display POIs on the map without a route overlay

**REQ-4.5.2:** If no POIs are defined, the system MUST:

- Skip POI metrics (not export empty metrics)
- Continue normal operation without errors

**REQ-4.5.3:** If an active route file is deleted while in use, the system MUST:

- Log a warning
- Clear the route overlay from `/route.geojson`
- Continue tracking current position and POIs (if any)

---

## 5. Non-Goals (Out of Scope)

The following are **explicitly excluded** from Phase 4:

1. **Route-aware ETA calculations** (following the path of the route, not
   straight-line) — deferred to future phase
1. **Automatic route selection based on time or position** — manual activation
   only
1. **Route editing or modification within the application** — users must edit
   KML files externally
1. **Multi-terminal support** (multiple dishes on one dashboard) — future
   enhancement
1. **3D altitude profiles** or terrain awareness
1. **Integration with external mapping services** (Google Maps, Mapbox) beyond
   OpenStreetMap
1. **Offline map caching** (beyond browser caching)
1. **User authentication or multi-user POI sharing** (single-user system for
   now)

---

## 6. Design Considerations

### 6.1 API Design

All API endpoints should follow RESTful conventions:

- `GET` for retrieval
- `POST` for creation
- `PUT` for updates
- `DELETE` for removal

Responses should be JSON-formatted with appropriate HTTP status codes:

- `200 OK` for successful operations
- `201 Created` for new resource creation
- `400 Bad Request` for invalid input
- `404 Not Found` for missing resources
- `500 Internal Server Error` for unexpected failures

### 6.2 GeoJSON Structure

The `/route.geojson` endpoint should return a FeatureCollection with:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "LineString", "coordinates": [[lon, lat], ...] },
      "properties": { "name": "Route Name", "type": "route" }
    },
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [lon, lat] },
      "properties": {
        "name": "POI Name",
        "type": "poi",
        "icon": "airport",
        "category": "destination",
        "description": "...",
        "eta_seconds": 1234,
        "distance_meters": 5000
      }
    },
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [lon, lat] },
      "properties": { "type": "current_position", "heading": 270, "speed": 150 }
    }
  ]
}
```

### 6.3 POI Data Storage

The `/data/pois.json` file should have this structure:

```json
{
  "global": [
    {
      "id": "home",
      "name": "Home Base",
      "latitude": 37.7749,
      "longitude": -122.4194,
      "icon": "home",
      "category": "base",
      "description": "Primary departure/arrival point"
    }
  ],
  "routes": {
    "route1.kml": [
      {
        "id": "waypoint1",
        "name": "Fuel Stop",
        "latitude": 38.5,
        "longitude": -121.5,
        "icon": "fuel",
        "category": "stop"
      }
    ]
  }
}
```

### 6.4 UI/UX Considerations

While Grafana handles the dashboard UI, the system should ensure:

- POI icons are distinct and recognizable (use emoji or Font Awesome icons)
- ETA values are formatted as human-readable strings in Grafana (e.g., "2h 34m"
  not "9240 seconds")
- Passed POIs are visually differentiated (e.g., grayed out or marked with a
  checkmark)

---

## 7. Technical Considerations

### 7.1 Libraries and Dependencies

- **KML Parsing:** `fastkml` (recommended) or `simplekml`
- **GeoJSON:** Python's built-in `json` module or `geojson` library
- **Haversine Distance:** Implement manually or use `haversine` PyPI package
- **File Watching:** `watchdog` library for monitoring `/data/routes/`

### 7.2 Performance

- KML parsing should be performed **asynchronously** to avoid blocking the main
  FastAPI event loop
- Route conversion to GeoJSON should be **cached** and only re-run when the file
  changes
- ETA/distance calculations should be **vectorized** if possible (using NumPy)
  to handle 50 POIs efficiently

### 7.3 Data Update Frequency

Per the design document, all metrics update every **2–5 seconds**. The POI
calculation loop should align with this interval to ensure:

- Consistent update latency
- Smooth ETA transitions
- Minimal CPU usage

### 7.4 Integration Points

- **Prometheus Metrics:** POI metrics must follow the existing naming convention
  (`starlink_*`)
- **Simulation Engine:** Must extend the existing simulator module to load and
  follow KML routes
- **Docker Volumes:** `/data/routes/` and `/data/sim_routes/` must be mounted in
  `docker-compose.yml`

---

## 8. Success Metrics

The feature will be considered successful when:

1. **Route Visibility:** Users can upload a KML file and see it rendered on the
   Grafana map within 10 seconds.
1. **POI Accuracy:** ETA calculations are within ±10% of actual arrival time
   (tested via simulation playback).
1. **Performance:** The system handles 50 POIs with <100ms latency for
   ETA/distance calculations.
1. **Resilience:** The system continues operating normally when:
   - Invalid KML files are uploaded (logs error, doesn't crash)
   - Routes are deleted mid-operation (clears overlay, continues tracking)
   - No POIs are defined (no metrics errors)
1. **Simulation Realism:** Simulated tracks follow KML routes with realistic
   deviations (visible on Grafana map).

---

## 9. Open Questions

1. **Route File Naming Convention:** Should route files have a specific naming
   pattern to auto-detect metadata (e.g., `2025-10-23_day1.kml`)?
   - **Resolution:** Not required for Phase 4; filenames can be arbitrary.

1. **POI Icons:** Should the system provide a predefined icon library, or allow
   arbitrary emoji/text?
   - **Resolution:** Start with emoji support (🏠✈️⛽🏁), add Font Awesome in
     future phase if needed.

1. **Route Activation API:** Should activation return the full route GeoJSON
   immediately, or just a success message?
   - **Resolution:** Return success message with route metadata (name, point
     count); client fetches GeoJSON separately.

1. **Distance Threshold for "Passing":** Is 100 meters appropriate for all use
   cases (aircraft, maritime, ground)?
   - **Resolution:** Start with 100m; make configurable per POI in future phase
     if needed.

1. **Negative ETA Format:** Should negative ETAs be displayed as "-5m" (5
   minutes ago) or "+5m" (5 minutes past)?
   - **Resolution:** Use negative values (`-300` seconds) in metrics; Grafana
     dashboard handles formatting.

---

## 10. Acceptance Criteria

Phase 4 is **complete** when:

- [ ] Users can upload KML files to `/data/routes/` and they are detected
      automatically
- [ ] The system provides API endpoints to list and activate routes
- [ ] The `/route.geojson` endpoint returns valid GeoJSON with route, POIs, and
      current position
- [ ] Users can create, update, list, and delete POIs via REST API
- [ ] POIs support required fields (name, lat, lon, icon) and optional fields
      (category, description)
- [ ] Both global and route-specific POIs are supported
- [ ] Prometheus metrics expose `starlink_eta_poi_seconds` and
      `starlink_distance_to_poi_meters` for all POIs
- [ ] ETA calculations use smoothed average speed (not instantaneous)
- [ ] Passed POIs show negative ETA values
- [ ] Distance calculations use Haversine formula
- [ ] Invalid KML files are logged and ignored gracefully
- [ ] Simulation mode uses KML routes from `/data/sim_routes/` with realistic
      deviations
- [ ] Simulation speed is configurable via environment variable
- [ ] The system handles edge cases (no route, no POIs, deleted route) without
      crashing
- [ ] Grafana map panel displays the route overlay and POI markers correctly
- [ ] All functionality is validated via Docker Compose deployment

---

## End of PRD
