# Additional API Endpoints

Endpoints not covered in other endpoint docs.

---

## Flight Status

**Prefix:** `/api/flight-status`
**Source:** `app/api/flight_status.py`

### GET `/api/flight-status`

Get current flight status including phase, ETA mode,
route metadata, and timing data.

### POST `/api/flight-status`

Reset flight status to PRE_DEPARTURE and clear timing
metadata.

### POST `/api/flight-status/transition`

Manually transition flight phase (for testing or
correction).

### POST `/api/flight-status/depart`

Manually trigger departure (forces IN_FLIGHT phase).

### POST `/api/flight-status/arrive`

Manually trigger arrival (forces POST_ARRIVAL phase).

---

## GPS v2

**Source:** `app/api/gps.py`

### GET `/api/v2/gps/config`

Get current GPS configuration and status from the
Starlink dish.

### POST `/api/v2/gps/config`

Update GPS configuration on the Starlink dish.

**Request Body:**

- `enabled` (bool) - Enable or disable GPS

**Errors:** 503 if dish unavailable, 403 if permission
denied.

---

## Starlink CSV Export

**Source:** `app/api/export/csv_export.py`

### GET `/starlink-csv`

Export Starlink telemetry data to CSV file.

**Query Parameters:**

- `start` (required) - Start datetime (ISO 8601)
- `end` (required) - End datetime (ISO 8601)
- `step` (optional) - Step interval in seconds (min 1s,
  auto-calculated if omitted)

**Rate Limit:** 10 requests/minute.
**Returns:** Streaming CSV file download.
**Errors:** 400 if start >= end.

---

## POI Statistics

**Prefix:** `/api/pois`
**Source:** `app/api/pois/stats.py`

### GET `/api/pois/count/total`

Get POI count, optionally filtered by route ID.

**Query Parameters:**

- `route_id` (optional) - Filter by route

### GET `/api/pois/stats/next-destination`

Get name of closest POI (next destination) with ETA.

### GET `/api/pois/stats/next-eta`

Get ETA in seconds to closest POI.

### GET `/api/pois/stats/approaching`

Get count of approaching POIs (< 30 min ETA threshold).

**Common Query Parameters (stats endpoints):**

- `latitude` (optional) - Current latitude
- `longitude` (optional) - Current longitude
- `speed_knots` (optional) - Current speed in knots

---

## GeoJSON Hemisphere Variants

**Prefix:** `/api`
**Source:** `app/api/geojson.py`

These endpoints handle International Date Line (IDL)
crossings by splitting routes into hemisphere-specific
segments for Grafana geomap visualization.

### GET `/api/route/coordinates`

Get route coordinates as tabular data (all hemispheres).

### GET `/api/route/coordinates/west`

Get route coordinates in western hemisphere (IDL-safe,
longitude < 0).

### GET `/api/route/coordinates/east`

Get route coordinates in eastern hemisphere (IDL-safe,
longitude >= 0).

**Common Query Parameters:**

- `route_id` (optional) - Use specific route instead of
  active route

**Response fields:** `coordinates`, `total`, `route_id`,
`route_name`.

---

## Position Table

**Source:** `app/api/metrics.py`

### GET `/position-table`

Position data as a simple table for Grafana.

**Response:**

```json
{
  "columns": [
    {"text": "aircraft_id", "type": "string"},
    {"text": "latitude", "type": "number"},
    {"text": "longitude", "type": "number"},
    {"text": "altitude", "type": "number"}
  ],
  "rows": [
    ["starlink-dish", 41.61, -74.01, 5134.94]
  ]
}
```
