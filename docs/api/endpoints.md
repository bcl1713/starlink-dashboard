# API Endpoints Reference

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [Root Endpoint](#root-endpoint)
2. [Health & Status Endpoints](#health--status-endpoints)
3. [Metrics Endpoints](#metrics-endpoints)
4. [Configuration Endpoints](#configuration-endpoints)
5. [POI Management Endpoints](#poi-management-endpoints)
6. [Flight Status Endpoints](#flight-status-endpoints)
7. [Route & Geographic Endpoints](#route--geographic-endpoints)
8. [ETA Route Timing Endpoints](#eta-route-timing-endpoints)
9. [UI Endpoints](#ui-endpoints)

---

## Root Endpoint

### GET `/`

Returns welcome message and API documentation links.

**Response:**

```json
{
  "message": "Welcome to Starlink Location Backend",
  "documentation": "API documentation available at /docs",
  "mode": "simulation",
  "version": "0.2.0"
}
```

**Status Code:** `200 OK`

---

## Health & Status Endpoints

### GET `/health`

Health check endpoint for service availability monitoring.

**Description:** Returns service status, uptime, mode information, and dish
connection status.

**Response:**

```json
{
  "status": "ok",
  "uptime_seconds": 3600.5,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2025-10-31T10:30:00.000000",
  "message": "Service is healthy",
  "dish_connected": true
}
```

**Status Codes:**

- `200 OK` - Service is healthy
- `500 Internal Server Error` - Service error

**Use Case:** Docker health checks, load balancer monitoring, uptime verification.

---

### GET `/api/status`

Current telemetry status in human-readable JSON format.

**Description:** Returns comprehensive current state of position, network, and
environmental metrics.

**Response:**

```json
{
  "timestamp": "2025-10-31T10:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 5000.0,
    "speed": 25.5,
    "heading": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5,
    "temperature_celsius": null
  }
}
```

**Status Codes:**

- `200 OK` - Current status available
- `500 Internal Server Error` - Cannot retrieve status

**Use Case:** Dashboard panels, status monitoring, API clients.

---

## Metrics Endpoints

### GET `/metrics`

Prometheus metrics in standard text format (OpenMetrics 1.0.0).

**Description:** Exports all metrics in Prometheus-compatible format. Compatible
with Prometheus scraper configuration.

**Response:** Text format (sample):

```text
# HELP starlink_dish_latitude_degrees Dish latitude in decimal degrees
# TYPE starlink_dish_latitude_degrees gauge
starlink_dish_latitude_degrees 40.7128

# HELP starlink_dish_longitude_degrees Dish longitude in decimal degrees
# TYPE starlink_dish_longitude_degrees gauge
starlink_dish_longitude_degrees -74.006

# HELP starlink_network_latency_ms Network round-trip latency
# TYPE starlink_network_latency_ms gauge
starlink_network_latency_ms 45.2
```

**Status Codes:**

- `200 OK` - Metrics available
- `500 Internal Server Error` - Cannot generate metrics

**Configuration:**

- Scrape interval: 1 second (backend update)
- Prometheus interval: 10 seconds (by default)

**Use Case:** Prometheus scraping, time-series database collection.

---

### GET `/api/metrics`

Raw metrics data as JSON (alternative to Prometheus format).

**Response:**

```json
{
  "position": {
    "latitude_degrees": 40.7128,
    "longitude_degrees": -74.0060,
    "altitude_meters": 5000.0,
    "speed_knots": 25.5,
    "heading_degrees": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5
  }
}
```

**Status Codes:**

- `200 OK` - Metrics available

**Use Case:** JSON API clients, custom integrations.

---

## Configuration Endpoints

### GET `/api/config`

Retrieve current service configuration.

**Response:**

```json
{
  "mode": "simulation",
  "update_interval_seconds": 1.0,
  "route": {
    "pattern": "circular",
    "latitude_start": 40.7128,
    "longitude_start": -74.0060,
    "radius_km": 100.0,
    "distance_km": 500.0
  },
  "network": {
    "latency_min_ms": 20.0,
    "latency_typical_ms": 50.0,
    "latency_max_ms": 80.0,
    "throughput_down_min_mbps": 50.0,
    "throughput_down_max_mbps": 200.0
  },
  "obstruction": {
    "min_percent": 0.0,
    "max_percent": 30.0,
    "variation_rate": 0.5
  }
}
```

**Status Codes:**

- `200 OK` - Configuration retrieved

**Use Case:** Configuration verification, admin dashboards.

---

### POST `/api/config`

Update service configuration at runtime.

**Request Body:**

```json
{
  "route": {
    "pattern": "straight",
    "radius_km": 150.0
  },
  "network": {
    "latency_max_ms": 100.0
  }
}
```

**Response:** Updated configuration (same as GET)

**Status Codes:**

- `200 OK` - Configuration updated
- `400 Bad Request` - Invalid configuration
- `422 Unprocessable Entity` - Validation error

**Use Case:** Runtime configuration adjustment, testing different parameters.

---

### PUT `/api/config`

Replace entire service configuration.

**Request Body:** Complete configuration object (same structure as GET response)

**Response:** Updated configuration

**Status Codes:**

- `200 OK` - Configuration replaced
- `400 Bad Request` - Invalid configuration
- `422 Unprocessable Entity` - Validation error

**Use Case:** Full configuration reset, environment-specific setup.

---

## POI Management Endpoints

### GET `/api/pois`

List all Points of Interest.

**Response:**

```json
[
  {
    "id": "poi-1",
    "name": "LaGuardia Airport",
    "latitude": 40.7769,
    "longitude": -73.8740,
    "description": "LGA - Major NYC airport",
    "created_at": "2025-10-30T10:00:00",
    "updated_at": "2025-10-30T10:00:00"
  }
]
```

**Status Codes:**

- `200 OK` - POI list retrieved
- `500 Internal Server Error` - Cannot read POI file

**Use Case:** POI display, Grafana dashboard queries.

---

### GET `/api/pois/count/total`

Get total count of POIs.

**Response:**

```json
{
  "total": 5
}
```

**Status Codes:**

- `200 OK` - Count retrieved
- `500 Internal Server Error` - Cannot read POI file

**Use Case:** Statistics, dashboard indicators.

---

### GET `/api/pois/etas`

Calculate real-time ETA to all POIs.

**Query Parameters:**

- `latitude` (float, optional) - Current latitude (default: from telemetry)
- `longitude` (float, optional) - Current longitude (default: from telemetry)
- `speed_knots` (float, optional) - Current speed (default: from telemetry)

**Response:**

```json
[
  {
    "poi_id": "poi-1",
    "name": "LaGuardia Airport",
    "latitude": 40.7769,
    "longitude": -73.8740,
    "distance_meters": 8500,
    "eta_seconds": 2640,
    "bearing_degrees": 45.5,
    "calculated_at": "2025-10-31T10:30:00.000000"
  }
]
```

**Status Codes:**

- `200 OK` - ETAs calculated
- `400 Bad Request` - Invalid coordinates/speed
- `500 Internal Server Error` - Calculation error

**Calculation Method:**

- **Distance:** Haversine formula (great-circle distance)
- **Bearing:** Inverse bearing calculation
- **ETA:** distance_meters / (speed_knots * 0.51444) seconds
- **Speed Default:** 67 knots (fallback if not available)

**Use Case:** Grafana ETA tooltips, real-time navigation.

---

### GET `/api/pois/{poi_id}`

Get specific POI details.

**Path Parameters:**

- `poi_id` (string) - POI identifier

**Response:**

```json
{
  "id": "poi-1",
  "name": "LaGuardia Airport",
  "latitude": 40.7769,
  "longitude": -73.8740,
  "description": "LGA - Major NYC airport",
  "created_at": "2025-10-30T10:00:00",
  "updated_at": "2025-10-30T10:00:00"
}
```

**Status Codes:**

- `200 OK` - POI found
- `404 Not Found` - POI not found

**Use Case:** POI detail views, confirmation dialogs.

---

### POST `/api/pois`

Create a new POI.

**Request Body:**

```json
{
  "name": "Central Park",
  "latitude": 40.7829,
  "longitude": -73.9654,
  "description": "NYC Central Park"
}
```

**Response:** Created POI with ID and timestamps

**Status Codes:**

- `201 Created` - POI created
- `400 Bad Request` - Invalid data
- `409 Conflict` - POI name already exists

**Use Case:** POI UI form submission, bulk POI import.

---

### PUT `/api/pois/{poi_id}`

Update existing POI.

**Path Parameters:**

- `poi_id` (string) - POI identifier

**Request Body:**

```json
{
  "name": "LaGuardia Airport (Updated)",
  "description": "LGA - Major NYC airport, departure point"
}
```

**Response:** Updated POI

**Status Codes:**

- `200 OK` - POI updated
- `404 Not Found` - POI not found
- `400 Bad Request` - Invalid data
- `409 Conflict` - POI name conflict

**Use Case:** POI editing, configuration updates.

---

### DELETE `/api/pois/{poi_id}`

Delete a POI.

**Path Parameters:**

- `poi_id` (string) - POI identifier

**Response:**

```json
{
  "message": "POI deleted successfully",
  "poi_id": "poi-1",
  "name": "LaGuardia Airport"
}
```

**Status Codes:**

- `200 OK` - POI deleted
- `404 Not Found` - POI not found
- `500 Internal Server Error` - Deletion error

**Use Case:** POI removal, cleanup operations.

---

## Flight Status Endpoints

Flight status endpoints manage the current flight phase (pre-departure, in-flight,
or post-arrival) and control ETA mode (anticipated vs. estimated). These
endpoints are essential for integration with Grafana dashboards and route
tracking systems.

### GET `/api/flight-status`

Get the current flight status including phase, ETA mode, countdowns, and route metadata.

**Description:** Returns comprehensive flight state information including current
phase, ETA calculation mode, active route context, timing information, and
countdown timers.

**Response:**

```json
{
  "phase": "in_flight",
  "eta_mode": "estimated",
  "active_route_id": "route-001",
  "active_route_name": "Cross-country Route",
  "has_timing_data": true,
  "scheduled_departure_time": "2025-12-03T14:00:00Z",
  "scheduled_arrival_time": "2025-12-03T18:30:00Z",
  "departure_time": "2025-12-03T14:05:00Z",
  "arrival_time": null,
  "time_until_departure_seconds": null,
  "time_since_departure_seconds": 300
}
```

**Status Codes:**

- `200 OK` - Flight status retrieved
- `500 Internal Server Error` - Cannot retrieve status

**Flight Phases:**

- `pre_departure` - Flight not yet started (uses `anticipated` ETA mode)
- `in_flight` - Flight is active (uses `estimated` ETA mode)
- `post_arrival` - Flight has completed

**Use Case:** Grafana dashboard updates, flight phase monitoring, ETA mode verification.

---

### POST `/api/flight-status/transition`

Manually transition to a new flight phase.

**Description:** Allows manual control of the flight state machine. Useful for
testing, correcting automatic detection errors, or triggering transitions that
don't depend on timing.

**Request Body:**

```json
{
  "phase": "in_flight",
  "reason": "Manual test transition"
}
```

**Response:** Current flight status (same as GET `/api/flight-status`)

**Status Codes:**

- `200 OK` - Transition successful
- `400 Bad Request` - Invalid phase transition
- `500 Internal Server Error` - Transition error

**Valid Transitions:**

- `pre_departure` → `in_flight` → `post_arrival`
- Invalid transitions are rejected

**Use Case:** Testing, state machine verification, error recovery.

---

### POST `/api/flight-status/depart`

Manually trigger departure, transitioning to IN_FLIGHT phase.

**Description:** Forces the flight into IN_FLIGHT phase with an optional
departure timestamp. Automatically switches ETA mode from `anticipated` to
`estimated`.

**Request Body (Optional):**

```json
{
  "timestamp": "2025-12-03T14:05:00Z",
  "reason": "Manual departure trigger for testing"
}
```

**Response:** Current flight status (same as GET `/api/flight-status`)

**Status Codes:**

- `200 OK` - Departure triggered successfully
- `400 Bad Request` - Flight already in-flight or post-arrival
- `500 Internal Server Error` - Departure error

**Behavior:**

- Sets `phase` to `in_flight`
- Switches `eta_mode` to `estimated`
- Records departure timestamp if provided
- Clears `time_until_departure_seconds`
- Initializes `time_since_departure_seconds`

**Use Case:** Manual flight start triggers, simulation testing, recovery from
detection failures.

---

### POST `/api/flight-status/arrive`

Manually trigger arrival, transitioning to POST_ARRIVAL phase.

**Description:** Forces the flight into POST_ARRIVAL phase with an optional
arrival timestamp. Freezes timing calculations and metrics.

**Request Body (Optional):**

```json
{
  "timestamp": "2025-12-03T18:30:00Z",
  "reason": "Manual arrival trigger for testing"
}
```

**Response:** Current flight status (same as GET `/api/flight-status`)

**Status Codes:**

- `200 OK` - Arrival triggered successfully
- `400 Bad Request` - Flight already post-arrival
- `500 Internal Server Error` - Arrival error

**Behavior:**

- Sets `phase` to `post_arrival`
- Records arrival timestamp if provided
- Freezes all timing metrics
- Disables further phase transitions until reset

**Use Case:** Manual flight completion, simulation testing, metrics finalization.

---

### POST `/api/flight-status`

Reset flight status to PRE_DEPARTURE phase and clear timing metadata.

**Description:** Resets the entire flight state to initial conditions. Useful
for starting a new mission or clearing test data.

**Request Body:** Empty

**Response:** Current flight status (same as GET `/api/flight-status`)

**Status Codes:**

- `200 OK` - Reset successful
- `500 Internal Server Error` - Reset error

**Behavior:**

- Sets `phase` to `pre_departure`
- Switches `eta_mode` to `anticipated`
- Clears all timing information
- Resets all countdown timers
- Allows new transitions

**Use Case:** Mission reset, test cleanup, state machine initialization.

---

## Route & Geographic Endpoints

### GET `/route.geojson`

Get route history as GeoJSON for map display.

**Description:** Returns the position history (route) as a GeoJSON LineString,
suitable for rendering on Grafana Geomap panels.

**Response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-74.0060, 40.7128],
          [-74.0050, 40.7138],
          [-74.0040, 40.7148]
        ]
      },
      "properties": {
        "name": "Position History"
      }
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Route data available
- `204 No Content` - No route data yet

**Use Case:** Grafana Geomap layer, position history visualization.

---

### GET `/geojson`

Alias for `/route.geojson` (for compatibility).

**Response:** Same as `/route.geojson`

---

## ETA Route Timing Endpoints

### GET `/api/routes/{route_id}/eta/waypoint/{waypoint_index}`

Calculate ETA to a specific waypoint on the active route.

**Description:** Returns estimated time to arrive at a waypoint, considering
current position and available timing data.

**Parameters:**

- `route_id` (path, required): Route identifier
- `waypoint_index` (path, required): Index of waypoint (0-based)
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

```json
{
  "waypoint_index": 5,
  "waypoint_name": "Departure Point",
  "eta_seconds": 3600,
  "eta_minutes": 60.0,
  "distance_meters": 150000,
  "distance_km": 150.0,
  "estimated_speed_knots": 150.0,
  "has_timing_data": true
}
```

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Route not found

**Use Case:** Real-time waypoint ETAs, flight plan tracking, progress monitoring.

---

### GET `/api/routes/{route_id}/eta/location`

Calculate ETA to an arbitrary geographic location.

**Description:** Returns estimated time to reach any specified coordinate,
supporting routes with or without timing data.

**Parameters:**

- `route_id` (path, required): Route identifier
- `target_lat` (query, required): Target latitude
- `target_lon` (query, required): Target longitude
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

```json
{
  "target_location": {"latitude": 40.7128, "longitude": -74.0060},
  "eta_seconds": 1800,
  "eta_minutes": 30.0,
  "distance_meters": 75000,
  "distance_km": 75.0,
  "estimated_speed_knots": 150.0,
  "route_id": "route-001"
}
```

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid coordinates
- `404 Not Found` - Route not found

**Use Case:** POI arrival predictions, arbitrary destination ETAs, navigation
planning.

---

### GET `/api/routes/{route_id}/progress`

Get overall route progress and timing metrics.

**Description:** Returns current progress along the route, next waypoint
information, and timing profile.

**Parameters:**

- `route_id` (path, required): Route identifier
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

```json
{
  "route_id": "route-001",
  "progress_percent": 35.5,
  "current_waypoint_index": 12,
  "total_waypoints": 34,
  "waypoints_remaining": 22,
  "distance_traveled_meters": 45000,
  "distance_remaining_meters": 84000,
  "total_distance_meters": 129000,
  "eta_to_destination_seconds": 2400,
  "average_speed_knots": 150.0,
  "has_timing_data": true,
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z",
    "total_expected_duration_seconds": 6300,
    "segment_count_with_timing": 28
  }
}
```

**Status Codes:**

- `200 OK` - Progress retrieved
- `404 Not Found` - Route not found

**Use Case:** Progress dashboards, ETA updates, route completion monitoring.

---

### GET `/api/routes/active/timing`

Get timing profile of the currently active route.

**Description:** Returns detailed timing information for the active route, if
available.

**Response:**

```json
{
  "route_id": "route-001",
  "has_timing_data": true,
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z",
    "total_expected_duration_seconds": 6300,
    "segment_count_with_timing": 28
  },
  "segments": [
    {
      "waypoint_index": 0,
      "waypoint_name": "Departure Point",
      "expected_arrival_time": "2025-10-27T16:45:00Z",
      "expected_segment_speed_knots": 150.0
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Timing profile available
- `404 Not Found` - No active route or no timing data

**Use Case:** Timing visualization, speed profile analysis, flight plan review.

---

### GET `/api/routes/metrics/eta-cache`

Get ETA caching performance metrics.

**Description:** Returns statistics about the ETA cache system, useful for
performance monitoring.

**Response:**

```json
{
  "cache_enabled": true,
  "ttl_seconds": 5,
  "total_cache_hits": 1250,
  "total_cache_misses": 342,
  "hit_rate_percent": 78.5,
  "cached_entries": 23,
  "average_calculation_time_ms": 12.5,
  "last_cleanup": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache metrics retrieved

**Use Case:** Performance monitoring, cache optimization, system diagnostics.

---

### GET `/api/routes/metrics/eta-accuracy`

Get historical ETA accuracy statistics.

**Description:** Returns how accurate the ETA predictions have been, comparing
predicted vs actual arrivals.

**Response:**

```json
{
  "total_predictions": 150,
  "total_arrivals": 127,
  "accuracy_stats": {
    "average_error_seconds": 45.3,
    "min_error_seconds": -120,
    "max_error_seconds": 240,
    "median_error_seconds": 30.0,
    "std_deviation_seconds": 67.5
  },
  "recent_predictions": [
    {
      "predicted_time": "2025-11-04T10:30:00Z",
      "actual_arrival_time": "2025-11-04T10:31:30Z",
      "error_seconds": 90,
      "destination": "waypoint_5"
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Accuracy metrics retrieved

**Use Case:** ETA algorithm validation, accuracy tracking, continuous improvement.

---

### POST `/api/routes/cache/cleanup`

Clean up expired cache entries.

**Description:** Removes TTL-expired entries from the ETA cache.

**Response:**

```json
{
  "cleaned_entries": 12,
  "remaining_entries": 23,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache cleaned

**Use Case:** Maintenance, memory management, periodic cleanup.

---

### POST `/api/routes/cache/clear`

Clear all ETA cache entries.

**Description:** Removes all entries from the ETA cache immediately.

**Response:**

```json
{
  "message": "Cache cleared",
  "cleared_entries": 35,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Status Codes:**

- `200 OK` - Cache cleared

**Use Case:** Cache reset, troubleshooting, system maintenance.

---

### POST `/api/routes/live-mode/active-route-eta`

Get ETA for active route using real-time position (live mode).

**Description:** Calculates ETA for the active route based on a real-time
position update, ideal for Starlink terminal position feeds.

**Parameters (JSON Body):**

```json
{
  "latitude": 40.7128,
  "longitude": -74.0060,
  "altitude": 5000.0,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Response:**

```json
{
  "current_position": {"latitude": 40.7128, "longitude": -74.0060},
  "route_progress": {
    "progress_percent": 45.5,
    "waypoints_remaining": 20,
    "distance_remaining_km": 75.0
  },
  "next_waypoint": {
    "index": 15,
    "name": "Waypoint 15",
    "eta_seconds": 1800,
    "distance_meters": 75000
  },
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z"
  }
}
```

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid position data
- `404 Not Found` - No active route

**Use Case:** Live aircraft tracking, real-time ETA updates, Starlink integration.

---

## UI Endpoints

### GET `/ui/pois`

POI management web interface.

**Description:** Returns a complete HTML page with interactive POI management UI,
including:

- Interactive map for click-to-place coordinates
- POI creation/editing/deletion form
- Real-time POI list with live ETAs
- Responsive design suitable for Grafana HTML panel

**Response:** HTML/CSS/JavaScript interface

**Status Codes:**

- `200 OK` - UI page loaded

**Use Case:** Grafana HTML text panel, standalone POI management.

---

## API Usage Examples

### cURL Examples

**Get Flight Status:**

```bash
curl http://localhost:8000/api/flight-status | jq .
```

**Trigger Departure:**

```bash
curl -X POST http://localhost:8000/api/flight-status/depart \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-12-03T14:05:00Z",
    "reason": "Manual departure trigger"
  }'
```

**Trigger Arrival:**

```bash
curl -X POST http://localhost:8000/api/flight-status/arrive \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-12-03T18:30:00Z",
    "reason": "Manual arrival trigger"
  }'
```

**Transition Flight Phase:**

```bash
curl -X POST http://localhost:8000/api/flight-status/transition \
  -H "Content-Type: application/json" \
  -d '{
    "phase": "in_flight",
    "reason": "Manual test transition"
  }'
```

**Reset Flight Status:**

```bash
curl -X POST http://localhost:8000/api/flight-status
```

**Get Health Status:**

```bash
curl http://localhost:8000/health | jq .
```

**Get Current Status:**

```bash
curl http://localhost:8000/api/status | jq .
```

**Create POI:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654,
    "description": "NYC Central Park"
  }'
```

**Get ETAs with Custom Location:**

```bash
curl "http://localhost:8000/api/pois/etas?latitude=40.7128&longitude=-74.0060&speed_knots=50"
```

**Update Configuration:**

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "route": {"pattern": "straight"}
  }'
```

### Python Examples

**Using requests library:**

```python
import requests

# Get flight status
response = requests.get('http://localhost:8000/api/flight-status')
flight_status = response.json()
print(f"Phase: {flight_status['phase']}")
print(f"ETA Mode: {flight_status['eta_mode']}")
print(f"Active Route: {flight_status['active_route_name']}")

# Trigger departure
response = requests.post(
    'http://localhost:8000/api/flight-status/depart',
    json={
        'timestamp': '2025-12-03T14:05:00Z',
        'reason': 'Manual departure'
    }
)
print(f"Phase after departure: {response.json()['phase']}")

# Trigger arrival
response = requests.post(
    'http://localhost:8000/api/flight-status/arrive',
    json={
        'timestamp': '2025-12-03T18:30:00Z',
        'reason': 'Manual arrival'
    }
)
print(f"Phase after arrival: {response.json()['phase']}")

# Reset flight status
response = requests.post('http://localhost:8000/api/flight-status')
print(f"Phase after reset: {response.json()['phase']}")

# Get current status
response = requests.get('http://localhost:8000/api/status')
status = response.json()
print(f"Position: {status['position']['latitude']}, {status['position']['longitude']}")

# Create POI
poi_data = {
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654
}
response = requests.post('http://localhost:8000/api/pois', json=poi_data)
poi = response.json()
print(f"Created POI: {poi['id']}")

# Get ETAs
response = requests.get('http://localhost:8000/api/pois/etas')
etas = response.json()
for poi in etas:
    print(f"{poi['name']}: {poi['eta_seconds']} seconds")
```

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
