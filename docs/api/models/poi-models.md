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
