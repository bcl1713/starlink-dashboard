# POI Management Endpoints

[Back to API Reference](../README.md) | [POI Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## POST `/api/pois`

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

## PUT `/api/pois/{poi_id}`

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

## DELETE `/api/pois/{poi_id}`

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

## Examples

### cURL Examples

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

**Update POI:**

```bash
curl -X PUT http://localhost:8000/api/pois/poi-1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "LaGuardia Airport (Updated)",
    "description": "LGA - Major NYC airport, departure point"
  }'
```

**Delete POI:**

```bash
curl -X DELETE http://localhost:8000/api/pois/poi-1 | jq .
```

---

### Python Examples

```python
import requests

# Create POI
poi_data = {
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654
}
response = requests.post('http://localhost:8000/api/pois', json=poi_data)
poi = response.json()
print(f"Created POI: {poi['id']}")

# Update POI
update_data = {
    "name": "Central Park (Updated)",
    "description": "NYC Central Park - Updated description"
}
response = requests.put(f'http://localhost:8000/api/pois/{poi["id"]}', json=update_data)
updated_poi = response.json()
print(f"Updated: {updated_poi['name']}")

# Delete POI
response = requests.delete(f'http://localhost:8000/api/pois/{poi["id"]}')
result = response.json()
print(f"Deleted: {result['message']}")
```

---

[Back to API Reference](../README.md) | [POI Index](./README.md)
