# Route Timing Implementation Guide

This guide covers the practical aspects of using the route timing feature
including KML format, API usage, and examples.

## KML Format with Timing Data

### Required Elements

Minimum valid KML with timing data:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="<http://www.opengis.net/kml/2.2">>
  <Document>
    <Placemark>
      `name`Route Name</name>
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
  `name`Waypoint Name</name>
  <Point>
    <coordinates>-76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z</coordinates>
  </Point>
</Placemark>
```

## Using the API

### Get Route Timing Profile

```bash
curl <http://localhost:8000/api/routes/active/timing>
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
curl "<http://localhost:8000/api/routes/{route_id}/eta/waypoint/15?current_position_lat=40.7&current_position_lon=-74.0">
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
curl "<http://localhost:8000/api/routes/{route_id}/eta/location?target_lat=40.7128&target_lon=-74.0060">
```

### Get Route Progress

```bash
curl "<http://localhost:8000/api/routes/{route_id}/progress">
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
  "<http://localhost:8000/api/routes/live-mode/active-route-eta">
```

## Examples

### Example 1: Flight Plan from KADW to PHNL

KML file with complete timing data:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="<http://www.opengis.net/kml/2.2">>
  <Document>
    `name`KADW-PHNL</name>
    <Placemark>
      `name`Departure Point - Andrews AFB</name>
      <Point>
        <coordinates>-76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      `name`Flight Path</name>
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
      `name`Arrival Point - Honolulu</name>
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
curl -X POST -F "file=@kadw-phnl.kml" <http://localhost:8000/api/routes/upload>

# Activate
curl -X POST <http://localhost:8000/api/routes/route-001/activate>

# Check profile
curl <http://localhost:8000/api/routes/active/timing>

# Monitor progress
curl <http://localhost:8000/api/routes/route-001/progress>
```

### Example 2: Querying ETA During Flight

At any point during a simulated or live flight:

```bash
# Get progress
curl <http://localhost:8000/api/routes/route-001/progress> | jq '.progress_percent'
# Output: 45.5

# Get ETA to next waypoint
curl "<http://localhost:8000/api/routes/route-001/eta/waypoint/15"> | jq '.eta_minutes'
# Output: 30.0

# Get ETA to specific location
curl "<http://localhost:8000/api/routes/route-001/eta/location?\>
target_lat=157.9&target_lon=21.3" | jq '.eta_minutes'
# Output: 45.0

# Monitor accuracy
curl <http://localhost:8000/api/routes/metrics/eta-accuracy> | jq '.accuracy_stats.average_error_seconds'
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
  "<http://localhost:8000/api/routes/live-mode/active-route-eta">

# Response includes current progress and next waypoint ETA
```
