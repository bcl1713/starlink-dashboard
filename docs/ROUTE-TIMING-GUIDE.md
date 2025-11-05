# Route Timing Feature Guide

**Version:** 0.4.0
**Last Updated:** 2025-11-05
**Status:** Complete - All 451 tests passing

This guide covers the comprehensive ETA Route Timing feature that enables realistic simulation and tracking of timed flight paths with expected waypoint arrival times.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [How Route Timing Works](#how-route-timing-works)
4. [KML Format with Timing Data](#kml-format-with-timing-data)
5. [Using the API](#using-the-api)
6. [ETA Modes: Anticipated vs. Estimated](#eta-modes-anticipated-vs-estimated)
7. [Grafana Dashboard Visualization](#grafana-dashboard-visualization)
8. [Simulation Mode Behavior](#simulation-mode-behavior)
9. [Live Mode Integration](#live-mode-integration)
10. [Troubleshooting](#troubleshooting)
11. [Examples](#examples)

---

## Overview

The Route Timing feature allows you to:

- **Automatic Timing Extraction:** Parse expected waypoint arrival times from KML files
- **Speed Calculations:** Calculate expected segment speeds between consecutive waypoints
- **Real-time ETAs:** Get accurate estimates to waypoints and arbitrary locations
- **Realistic Simulation:** Simulator respects timing data and expected speeds for authentic movement
- **Performance Optimization:** Intelligent caching reduces calculation load
- **Accuracy Tracking:** Monitor how accurate your ETA predictions are

### Key Features

- Extracts timing from KML descriptions: `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
- Calculates distances using haversine formula for Earth-based accuracy
- Provides granular (waypoint-level) and aggregate (route-level) timing metrics
- Exposes timing data through REST API and Prometheus metrics
- Integrates seamlessly with existing route and POI systems
- Works with or without timing data (graceful degradation)

---

## Quick Start

### 1. Prepare a KML File with Timing Data

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Flight Route KADW-PHNL</name>
      <LineString>
        <coordinates>
          -76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z
          -75.0,38.0,2000 Time Over Waypoint: 2025-10-27 16:51:00Z
          -74.0,37.5,2500 Time Over Waypoint: 2025-10-27 17:05:00Z
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

### 2. Upload the Route

```bash
curl -X POST \
  -F "file=@your-timed-route.kml" \
  http://localhost:8000/api/routes/upload
```

Response includes `has_timing_data: true` if timing was found.

### 3. Activate the Route

```bash
curl -X POST http://localhost:8000/api/routes/{route_id}/activate
```

### 4. Check Timing Profile

```bash
curl http://localhost:8000/api/routes/active/timing | jq .
```

---

## How Route Timing Works

### 1. Timing Data Extraction

When you upload a KML file, the parser:

1. **Finds timing markers** in coordinate descriptions
2. **Extracts timestamps** using regex pattern: `Time Over Waypoint:\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})Z`
3. **Maps timestamps to waypoints** using haversine distance (within 1000m tolerance)
4. **Calculates segment speeds** between consecutive timestamped points
5. **Builds route profile** with departure, arrival, and duration

### 2. Speed Calculation

```
Speed (knots) = Distance (meters) / Time (seconds) * (3600 / 1852)
```

Example: If a point is 74,600 meters away and takes 600 seconds:
```
Speed = 74,600 / 600 * (3600 / 1852) = 124.33 / 1.852 = 200 knots
```

### 3. ETA Calculation

For routes with timing data:
```
ETA = Distance to waypoint (meters) / Speed (knots) * (1852 / 3600)
```

### 4. Simulator Behavior

In simulation mode, the simulator:

1. **Checks if route has timing data** at current waypoint
2. **If yes:** Uses expected speed from timing data (small ±0.5 knot variation)
3. **If no:** Falls back to default realistic speeds (45-75 knots)
4. **Result:** Arrival times match expected times when following timed routes

---

## KML Format with Timing Data

### Required Elements

Minimum valid KML with timing data:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Route Name</name>
      <LineString>
        <coordinates>
          longitude,latitude,altitude Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ
          longitude,latitude,altitude Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

### Format Requirements

- **Coordinates:** Standard KML format (lon,lat,altitude)
- **Timing Format:** `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
- **Timestamp Timezone:** Must be UTC (Z suffix required)
- **Spacing:** Timing marker must be on same line as coordinates
- **Optional:** Routes without timing data continue working

### Advanced Features

**Multiple Route Segments:**
```xml
<Placemark>
  <LineString>
    <coordinates>
      -76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z
      -75.0,38.0,2000 Time Over Waypoint: 2025-10-27 16:51:00Z
    </coordinates>
  </LineString>
</Placemark>
<Placemark>
  <LineString>
    <coordinates>
      -75.0,38.0,2000 Time Over Waypoint: 2025-10-27 16:51:00Z
      -74.0,37.5,2500 Time Over Waypoint: 2025-10-27 17:05:00Z
    </coordinates>
  </LineString>
</Placemark>
```

**POI Points:**
```xml
<Placemark>
  <name>Waypoint Name</name>
  <Point>
    <coordinates>-76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z</coordinates>
  </Point>
</Placemark>
```

---

## Using the API

### Get Route Timing Profile

```bash
curl http://localhost:8000/api/routes/active/timing
```

Response:
```json
{
  "route_id": "route-001",
  "has_timing_data": true,
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z",
    "total_expected_duration_seconds": 6300,
    "segment_count_with_timing": 28
  }
}
```

### Calculate ETA to Waypoint

```bash
# ETA to waypoint index 15
curl "http://localhost:8000/api/routes/{route_id}/eta/waypoint/15?current_position_lat=40.7&current_position_lon=-74.0"
```

Response:
```json
{
  "waypoint_index": 15,
  "waypoint_name": "Waypoint 15",
  "eta_seconds": 1800,
  "eta_minutes": 30.0,
  "distance_meters": 75000,
  "distance_km": 75.0,
  "estimated_speed_knots": 150.0,
  "has_timing_data": true
}
```

### Calculate ETA to Arbitrary Location

```bash
curl "http://localhost:8000/api/routes/{route_id}/eta/location?target_lat=40.7128&target_lon=-74.0060"
```

### Get Route Progress

```bash
curl "http://localhost:8000/api/routes/{route_id}/progress"
```

Response:
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

### Live Mode Integration

For real Starlink position feeds:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 5000.0,
    "timestamp": "2025-11-04T10:30:00Z"
  }' \
  http://localhost:8000/api/routes/live-mode/active-route-eta
```

---

## ETA Modes: Anticipated vs. Estimated

Dual-mode ETA calculations keep operators informed both before departure and during live operations. Anticipated mode projects the planned schedule, while estimated mode reacts to real performance.

### Anticipated Mode (Planned Timeline)

- **Phase:** `FlightPhase.PRE_DEPARTURE`
- **Source:** Planned timestamps and segment speeds from the timing profile
- **Behaviour:** Assumes the aircraft follows the filed plan; standalone POIs are labelled `is_pre_departure: true`
- **Surfaces:** `/api/flight-status` (`"eta_mode": "anticipated"`), `/api/pois/etas` (`"eta_type": "anticipated"`), Prometheus (`eta_type="anticipated"`), Grafana badges (**PLANNED**)

```json
{
  "name": "Gate Push",
  "eta_seconds": 900,
  "eta_type": "anticipated",
  "is_pre_departure": true,
  "flight_phase": "pre_departure"
}
```

### Estimated Mode (Live Performance)

- **Phase:** `FlightPhase.IN_FLIGHT` and `FlightPhase.POST_ARRIVAL`
- **Source:** Blends smoothed live speed (120 s window) with the timing profile; falls back to distance/speed when timing is absent
- **Behaviour:** Adjusts ETAs to reflect actual performance or manual depart/arrive triggers
- **Surfaces:** `/api/flight-status` (`"eta_mode": "estimated"`), `/api/pois/etas` (`"eta_type": "estimated"`), Prometheus (`eta_type="estimated"`), Grafana badges (**LIVE**)

### Automatic Switching Rules

| Trigger | Phase Transition | Resulting ETA Mode | Notes |
|---------|------------------|--------------------|-------|
| Speed rises above departure threshold (default 40 kn) | `pre_departure → in_flight` | Estimated | Detected by `FlightStateManager.check_departure`; can be forced via `/api/flight-status/depart` |
| Arrival threshold met (within 100 m for 60 s) or `/api/flight-status/arrive` called | `in_flight → post_arrival` | Estimated | Keeps last-known ETAs until reset |
| `/api/flight-status` reset or route deactivated | `post_arrival → pre_departure` | Anticipated | Clears actual departure/arrival timestamps and resumes planned timeline |

### Timed vs. Untimed Routes

- **Timed routes:** Anticipated mode mirrors the KML plan; estimated mode blends live speed with expected segment speeds for smoother updates.
- **Untimed routes:** Both modes fall back to distance-based estimation. `has_timing_data` stays `false`, but `eta_mode` still tracks the flight phase.

> Tip: During dashboard validation you can issue `/api/flight-status/depart` and `/api/flight-status/arrive` to cycle modes instantly without waiting for automatic detection.

---

## Grafana Dashboard Visualization

The route timing feature adds four new panels to the Fullscreen Overview dashboard:

### 1. Route Timing Profile Table

Displays:
- Route ID
- Departure time
- Arrival time
- Expected duration
- Segment count with timing

**Data Source:** `starlink_route_timing_*` metrics

### 2. Route Speed Analysis Chart

Shows:
- Expected segment speeds (from timing data)
- Actual speeds (calculated from position changes)
- Speed deviation from planned

**Data Source:** Prometheus queries on speed metrics

### 3. Route Progress Gauge

Displays:
- Overall route progress (0-100%)
- Color-coded thresholds:
  - 0-25%: Green (just starting)
  - 25-75%: Blue (in progress)
  - 75-100%: Orange (nearing completion)

**Data Source:** `starlink_route_progress_percent`

### 4. Distance to Destination Chart

Shows:
- Remaining distance (km)
- Estimated arrival time countdown
- Distance traveled vs planned

**Data Source:** `starlink_distance_to_waypoint_meters`

---

## Simulation Mode Behavior

### When Timing Data is Present

The simulator:

1. **Reads expected speeds** from KML timing data
2. **Applies small variations** (±0.5 knots) for realism
3. **Produces predictable movement** matching flight plan
4. **Enables validation:** Actual arrival times can be compared to expected

Example:
```
Route: KADW-PHNL with timing data
Expected Speed Segment 0-1: 200 knots
Actual Simulated Speed: 199.8 to 200.2 knots (with variation)
Result: Realistic movement following expected speeds
```

### When Timing Data is Absent

The simulator falls back to default behavior:

1. **Default speed range:** 45-75 knots (realistic cruising)
2. **Random variations:** Natural speed fluctuations
3. **Full backward compatibility:** Existing routes work unchanged

---

## Live Mode Integration

When connected to a real Starlink terminal:

1. **Position updates feed** into the active route
2. **ETA calculations** update in real-time
3. **Timing profile** available if route has timing data
4. **Metrics published** to Prometheus for monitoring

Use the `/api/routes/live-mode/active-route-eta` endpoint to:
- Feed real position data
- Get up-to-date progress metrics
- Track against expected timing

---

## Troubleshooting

### Timing Data Not Detected

**Symptoms:**
- Route uploaded successfully but `has_timing_data: false`

**Solutions:**
1. Verify timing format: `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
2. Check timezone: Must end with `Z` (UTC)
3. Ensure timing marker is on same line as coordinates
4. Check regex pattern matches your format

**Test extraction:**
```bash
# Check if timing was detected in route
curl http://localhost:8000/api/routes/{route_id} | jq '.has_timing_data'
```

### ETA Calculations Returning Zeros

**Symptoms:**
- `eta_seconds: 0` or `distance_meters: 0`

**Solutions:**
1. Verify route is activated: `GET /api/routes/active`
2. Check current position is valid
3. Verify waypoint indices are within route bounds
4. Check if route has timing data for that segment

### Simulator Not Respecting Timing Speeds

**Symptoms:**
- Simulator moving at different speeds than expected

**Solutions:**
1. Verify route has timing data: `GET /api/routes/active/timing`
2. Check that route is activated (not just loaded)
3. Ensure Docker container rebuilt after code changes
4. Rebuild Docker: `docker compose down && docker compose build --no-cache && docker compose up -d`

### High ETA Calculation Times

**Symptoms:**
- Dashboard queries slow, timeouts in API

**Solutions:**
1. Check cache hit rate: `GET /api/routes/metrics/eta-cache`
2. Clean expired cache: `POST /api/routes/cache/cleanup`
3. For high-volume queries, enable caching (default 5-second TTL)

---

## Examples

### Example 1: Flight Plan from KADW to PHNL

KML file with complete timing data:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>KADW-PHNL</name>
    <Placemark>
      <name>Departure Point - Andrews AFB</name>
      <Point>
        <coordinates>-76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Flight Path</name>
      <LineString>
        <coordinates>
          -76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z
          -75.0,38.0,5000 Time Over Waypoint: 2025-10-27 16:51:13Z
          -74.0,37.5,7500 Time Over Waypoint: 2025-10-27 17:05:13Z
          -72.0,36.0,10000 Time Over Waypoint: 2025-10-27 17:30:13Z
          -70.0,35.0,12500 Time Over Waypoint: 2025-10-27 17:55:13Z
          -150.0,20.0,15000 Time Over Waypoint: 2025-10-27 18:30:00Z
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Arrival Point - Honolulu</name>
      <Point>
        <coordinates>-157.9,21.3,500 Time Over Waypoint: 2025-10-27 18:30:00Z</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
```

Upload and use:
```bash
# Upload
curl -X POST -F "file=@kadw-phnl.kml" http://localhost:8000/api/routes/upload

# Activate
curl -X POST http://localhost:8000/api/routes/route-001/activate

# Check profile
curl http://localhost:8000/api/routes/active/timing

# Monitor progress
curl http://localhost:8000/api/routes/route-001/progress
```

### Example 2: Querying ETA During Flight

At any point during a simulated or live flight:

```bash
# Get progress
curl http://localhost:8000/api/routes/route-001/progress | jq '.progress_percent'
# Output: 45.5

# Get ETA to next waypoint
curl "http://localhost:8000/api/routes/route-001/eta/waypoint/15" | jq '.eta_minutes'
# Output: 30.0

# Get ETA to specific location
curl "http://localhost:8000/api/routes/route-001/eta/location?target_lat=157.9&target_lon=21.3" | jq '.eta_minutes'
# Output: 45.0

# Monitor accuracy
curl http://localhost:8000/api/routes/metrics/eta-accuracy | jq '.accuracy_stats.average_error_seconds'
# Output: 45.3
```

### Example 3: Live Mode Position Updates

For real Starlink terminal updates:

```bash
# Position update from real terminal
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 5000.0,
    "timestamp": "2025-11-04T10:30:00Z"
  }' \
  http://localhost:8000/api/routes/live-mode/active-route-eta

# Response includes current progress and next waypoint ETA
```

---

## Performance Considerations

### Cache Statistics

```bash
curl http://localhost:8000/api/routes/metrics/eta-cache
```

Typical output:
```json
{
  "cache_enabled": true,
  "ttl_seconds": 5,
  "total_cache_hits": 1250,
  "total_cache_misses": 342,
  "hit_rate_percent": 78.5
}
```

**Optimization Tips:**
- Cache hit rate above 70% is good
- Hit rate depends on position update frequency
- For dashboards updating every 1-2 seconds, expect 70-80% hit rate

### Large Route Handling

For routes with 1000+ waypoints:

1. **Upload time:** <2 seconds (parsing is efficient)
2. **Calculation time:** <50ms per ETA query
3. **Storage:** ~100KB per 1000 waypoints
4. **Memory:** Cache limited to 100 entries by default

---

**Last Updated:** 2025-11-04
**Feature Status:** Complete and Production Ready
**Test Coverage:** 451 tests passing (100%)
