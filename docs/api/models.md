# API Data Models

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [Common Types](#common-types)
2. [Health & Status Models](#health--status-models)
3. [Position & Network Models](#position--network-models)
4. [POI Models](#poi-models)
5. [Route Models](#route-models)
6. [Configuration Models](#configuration-models)
7. [ETA Models](#eta-models)

---

## Common Types

### Coordinate Types

All geographic coordinates use decimal degrees:

```typescript
latitude: float; // -90 to 90 (negative = South)
longitude: float; // -180 to 180 (negative = West)
altitude: float; // Meters above sea level
```

### Timestamp Format

All timestamps use ISO-8601 format in UTC:

```text
"2025-10-31T10:30:00.000000"
```

### Distance Units

- Distances: meters (convert to km by dividing by 1000)
- Speed: knots
- Altitude: meters

---

## Health & Status Models

### HealthResponse

Response from `/health` endpoint.

```json
{
  "status": "ok", // "ok" or "error"
  "uptime_seconds": 3600.5, // float
  "mode": "simulation", // "simulation" or "live"
  "version": "0.2.0", // string
  "timestamp": "2025-10-31T10:30:00.000000", // ISO-8601
  "message": "Service is healthy", // string
  "dish_connected": true // bool
}
```

**Fields:**

- `status`: Overall health status
- `uptime_seconds`: Time since service started
- `mode`: Operating mode (simulation or live)
- `version`: Backend version
- `timestamp`: Current server time
- `message`: Human-readable status message
- `dish_connected`: Whether connected to Starlink dish (live mode only)

---

### StatusResponse

Response from `/api/status` endpoint.

```json
{
  "timestamp": "2025-10-31T10:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.006,
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

---

## Position & Network Models

### Position

```json
{
  "latitude": 40.7128, // float: -90 to 90
  "longitude": -74.006, // float: -180 to 180
  "altitude": 5000.0, // float: meters
  "speed": 25.5, // float: knots
  "heading": 45.0 // float: degrees (0=North)
}
```

### Network

```json
{
  "latency_ms": 45.2, // float: milliseconds
  "throughput_down_mbps": 125.3, // float: megabits/sec
  "throughput_up_mbps": 25.1, // float: megabits/sec
  "packet_loss_percent": 0.5 // float: 0-100
}
```

### Obstruction

```json
{
  "obstruction_percent": 15.0 // float: 0-100
}
```

### Environmental

```json
{
  "signal_quality_percent": 85.0, // float: 0-100
  "uptime_seconds": 3600.5, // float
  "temperature_celsius": null // float or null
}
```

---

## POI Models

### POI (Base Model)

```json
{
  "id": "poi-1", // string: unique ID
  "name": "LaGuardia Airport", // string
  "latitude": 40.7769, // float
  "longitude": -73.874, // float
  "description": "LGA - Major NYC airport", // string (optional)
  "created_at": "2025-10-30T10:00:00", // ISO-8601
  "updated_at": "2025-10-30T10:00:00" // ISO-8601
}
```

**Fields:**

- `id`: Unique POI identifier (auto-generated)
- `name`: POI name (required)
- `latitude`: Decimal degrees latitude (required)
- `longitude`: Decimal degrees longitude (required)
- `description`: Optional description text
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp

---

### POIWithETA (Extended Model)

```json
{
  "poi_id": "poi-1",
  "name": "LaGuardia Airport",
  "latitude": 40.7769,
  "longitude": -73.874,
  "distance_meters": 8500,
  "eta_seconds": 2640,
  "bearing_degrees": 45.5,
  "calculated_at": "2025-10-31T10:30:00.000000"
}
```

**Additional Fields:**

- `distance_meters`: Straight-line distance from current position
- `eta_seconds`: Estimated time to arrival
- `bearing_degrees`: Direction to POI (0=North, 90=East)
- `calculated_at`: When ETA was calculated

---

### POICreateRequest

Request body for `POST /api/pois`.

```json
{
  "name": "Central Park",
  "latitude": 40.7829,
  "longitude": -73.9654,
  "description": "NYC Central Park"
}
```

**Required Fields:**

- `name`: POI name
- `latitude`: Decimal degrees latitude
- `longitude`: Decimal degrees longitude

**Optional Fields:**

- `description`: POI description

---

### POIUpdateRequest

Request body for `PUT /api/pois/{poi_id}`.

```json
{
  "name": "LaGuardia Airport (Updated)",
  "description": "LGA - Major NYC airport, departure point"
}
```

**All fields are optional** - only include fields you want to update.

---

## Route Models

### RouteProgress

Response from `/api/routes/{route_id}/progress`.

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

**Fields:**

- `route_id`: Route identifier
- `progress_percent`: Progress along route (0-100)
- `current_waypoint_index`: Index of current/next waypoint
- `total_waypoints`: Total number of waypoints
- `waypoints_remaining`: How many waypoints left
- `distance_traveled_meters`: Distance covered so far
- `distance_remaining_meters`: Distance left to destination
- `total_distance_meters`: Total route distance
- `eta_to_destination_seconds`: Estimated time to final waypoint
- `average_speed_knots`: Current average speed
- `has_timing_data`: Whether route has timing information
- `timing_profile`: Timing data (if available)

---

### RouteTimingProfile

```json
{
  "departure_time": "2025-10-27T16:45:00Z",
  "arrival_time": "2025-10-27T18:30:00Z",
  "total_expected_duration_seconds": 6300,
  "segment_count_with_timing": 28
}
```

**Fields:**

- `departure_time`: Expected departure time (ISO-8601)
- `arrival_time`: Expected arrival time (ISO-8601)
- `total_expected_duration_seconds`: Flight duration
- `segment_count_with_timing`: Number of segments with timing data

---

### GeoJSON Feature Collection

Response from `/route.geojson` endpoint.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-74.006, 40.7128],
          [-74.005, 40.7138]
        ]
      },
      "properties": {
        "name": "Position History"
      }
    }
  ]
}
```

**Note:** Coordinates are in `[longitude, latitude]` order (GeoJSON standard).

---

## Configuration Models

### Configuration

Response from `/api/config` endpoint.

```json
{
  "mode": "simulation",
  "update_interval_seconds": 1.0,
  "route": {
    "pattern": "circular",
    "latitude_start": 40.7128,
    "longitude_start": -74.006,
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

**Top-Level Fields:**

- `mode`: "simulation" or "live"
- `update_interval_seconds`: How often metrics update

**Route Configuration:**

- `pattern`: "circular" or "straight"
- `latitude_start`: Starting latitude
- `longitude_start`: Starting longitude
- `radius_km`: Circular route radius
- `distance_km`: Straight route distance

**Network Configuration:**

- `latency_min_ms`: Minimum latency
- `latency_typical_ms`: Typical latency
- `latency_max_ms`: Maximum latency
- `throughput_down_min_mbps`: Minimum download speed
- `throughput_down_max_mbps`: Maximum download speed

**Obstruction Configuration:**

- `min_percent`: Minimum obstruction percentage
- `max_percent`: Maximum obstruction percentage
- `variation_rate`: How quickly obstruction changes

---

## ETA Models

### WaypointETA

Response from `/api/routes/{route_id}/eta/waypoint/{waypoint_index}`.

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

**Fields:**

- `waypoint_index`: Waypoint sequence number
- `waypoint_name`: Name of waypoint (if available)
- `eta_seconds`: Time to reach waypoint (seconds)
- `eta_minutes`: Time to reach waypoint (minutes)
- `distance_meters`: Distance to waypoint
- `distance_km`: Distance to waypoint (km)
- `estimated_speed_knots`: Speed used for calculation
- `has_timing_data`: Whether route has timing information

---

### LocationETA

Response from `/api/routes/{route_id}/eta/location`.

```json
{
  "target_location": {
    "latitude": 40.7128,
    "longitude": -74.006
  },
  "eta_seconds": 1800,
  "eta_minutes": 30.0,
  "distance_meters": 75000,
  "distance_km": 75.0,
  "estimated_speed_knots": 150.0,
  "route_id": "route-001"
}
```

**Fields:**

- `target_location`: Target coordinates
- `eta_seconds`: Time to reach target (seconds)
- `eta_minutes`: Time to reach target (minutes)
- `distance_meters`: Distance to target
- `distance_km`: Distance to target (km)
- `estimated_speed_knots`: Speed used for calculation
- `route_id`: Associated route

---

### ETACacheMetrics

Response from `/api/routes/metrics/eta-cache`.

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

**Fields:**

- `cache_enabled`: Whether caching is active
- `ttl_seconds`: Time-to-live for cache entries
- `total_cache_hits`: Total successful cache lookups
- `total_cache_misses`: Total cache misses
- `hit_rate_percent`: Cache hit percentage
- `cached_entries`: Current number of cached items
- `average_calculation_time_ms`: Average time per calculation
- `last_cleanup`: Last cache cleanup time

---

### ETAAccuracyMetrics

Response from `/api/routes/metrics/eta-accuracy`.

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

**Fields:**

- `total_predictions`: Total ETA predictions made
- `total_arrivals`: Total actual arrivals recorded
- `accuracy_stats`: Statistical accuracy metrics
- `recent_predictions`: Recent prediction accuracy samples

---

## Validation Rules

### Coordinate Validation

- `latitude`: Must be between -90 and 90
- `longitude`: Must be between -180 and 180
- `altitude`: No strict bounds (can be negative for below sea level)

### Name Validation

- POI names must be unique
- Names cannot be empty strings
- Maximum length typically 255 characters

### Speed Validation

- Speed must be non-negative
- Typical range: 0-500 knots
- Speed of 0 indicates stationary

### Percentage Validation

- All percentages must be between 0 and 100
- Includes: obstruction_percent, signal_quality_percent, packet_loss_percent,
  progress_percent

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
