# POI Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## POI (Base Model)

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

## POIWithETA (Extended Model)

```json
{
  "poi_id": "jfk-airport",
  "name": "JFK Airport",
  "latitude": 40.6413,
  "longitude": -73.7781,
  "category": "airport",
  "icon": "airport",
  "active": true,
  "eta_seconds": 1080.0,
  "eta_type": "estimated",
  "is_pre_departure": false,
  "flight_phase": "in_flight",
  "distance_meters": 45000.0,
  "bearing_degrees": 125.0,
  "course_status": "on_course",
  "is_on_active_route": true,
  "projected_latitude": 40.64,
  "projected_longitude": -73.78,
  "projected_waypoint_index": 42,
  "projected_route_progress": 45.5,
  "route_aware_status": "ahead_on_route"
}
```

**Additional Fields (beyond base POI):**

- `category` (string?) - POI category
- `icon` (string) - Icon identifier
- `active` (bool) - Whether POI is currently active
- `eta_seconds` (float) - ETA in seconds (-1 if no
  speed)
- `eta_type` (string) - `anticipated` or `estimated`
- `is_pre_departure` (bool) - True before departure
- `flight_phase` (string?) - `pre_departure`,
  `in_flight`, or `post_arrival`
- `distance_meters` (float) - Distance to POI in meters
- `bearing_degrees` (float?) - Bearing (0=North)
- `course_status` (string?) - `on_course`,
  `slightly_off`, `off_track`, or `behind`
- `is_on_active_route` (bool) - Projects to active route
- `projected_latitude` (float?) - Projected route point
- `projected_longitude` (float?) - Projected route point
- `projected_waypoint_index` (int?) - Closest route
  point index
- `projected_route_progress` (float?) - Progress % on
  route
- `route_aware_status` (string?) - `ahead_on_route`,
  `already_passed`, `not_on_route`, or `pre_departure`

---

## POICreateRequest

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

## POIUpdateRequest

Request body for `PUT /api/pois/{poi_id}`.

```json
{
  "name": "LaGuardia Airport (Updated)",
  "description": "LGA - Major NYC airport, departure point"
}
```

**All fields are optional** - only include fields you want to update.

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
