# Waypoint and location ETA

| GET path                                               | Required query parameters                                                        |
| ------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `/api/routes/{route_id}/eta/waypoint/{waypoint_index}` | `current_position_lat`, `current_position_lon`                                   |
| `/api/routes/{route_id}/eta/location`                  | `latitude`, `longitude` (target), `current_position_lat`, `current_position_lon` |

All query coordinates are numeric. `waypoint_index` is zero-based. These
endpoints require explicit current position; they do not automatically read
telemetry. Target parameters are `latitude` and `longitude`, not `target_lat`
and `target_lon`.

```bash
curl 'http://localhost:8000/api/routes/ROUTE_ID/eta/waypoint/0?current_position_lat=40.7&current_position_lon=-74.0' | jq .
curl 'http://localhost:8000/api/routes/ROUTE_ID/eta/location?latitude=41&longitude=-73&current_position_lat=40.7&current_position_lon=-74.0' | jq .
```

Responses are calculator dictionaries with ETA/distance and route-timing
context. Consumers should handle missing timing and inspect the running schema
and `app/services/route_eta/calculator.py` for the selected calculation mode. A
published paced replay can augment the result with replay timing.

A missing route returns 404, out-of-range waypoint is rejected with 400,
missing/invalid query arguments return 422, and calculation failures or missing
manager return 500. Source: `app/api/routes/eta.py`.

See [ETA index](README.md).
