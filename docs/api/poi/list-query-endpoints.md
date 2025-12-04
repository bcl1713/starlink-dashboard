# POI List & Query Endpoints

[Back to API Reference](../README.md) | [POI Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## GET `/api/pois`

List all Points of Interest.

**Response:**

```json
[
  {
    "id": "poi-1",
    "name": "LaGuardia Airport",
    "latitude": 40.7769,
    "longitude": -73.874,
    "description": "LGA - Major NYC airport",
    "created_at": "2025-10-30T10:00:00",
    "updated_at": "2025-10-30T10:00:00"
  },
  {
    "id": "poi-2",
    "name": "Newark Airport",
    "latitude": 40.6895,
    "longitude": -74.1745,
    "description": "EWR - Regional airport"
  }
]
```

**Status Codes:**

- `200 OK` - POI list retrieved
- `500 Internal Server Error` - Cannot read POI file

**Query Parameters:** None

**Use Case:** POI display, Grafana dashboard queries.

---

## GET `/api/pois/count/total`

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

## GET `/api/pois/{poi_id}`

Get specific POI details.

**Path Parameters:**

- `poi_id` (string) - POI identifier

**Response:**

```json
{
  "id": "poi-1",
  "name": "LaGuardia Airport",
  "latitude": 40.7769,
  "longitude": -73.874,
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

## Examples

### cURL Examples

**List All POIs:**

```bash
curl http://localhost:8000/api/pois | jq .
```

**Get Specific POI:**

```bash
curl http://localhost:8000/api/pois/poi-1 | jq .
```

**Get POI Count:**

```bash
curl http://localhost:8000/api/pois/count/total | jq .
```

---

### Python Examples

```python
import requests

# List all POIs
response = requests.get('http://localhost:8000/api/pois')
pois = response.json()
print(f"Total POIs: {len(pois)}")

# Get specific POI
response = requests.get('http://localhost:8000/api/pois/poi-1')
poi = response.json()
print(f"POI: {poi['name']} at ({poi['latitude']}, {poi['longitude']})")
```

---

[Back to API Reference](../README.md) | [POI Index](./README.md)
