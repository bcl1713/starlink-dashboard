# API Data Models Reference

**Note:** This is a redirect file. The full models documentation has been
preserved.

For the complete data models reference (558 lines), see:
**[models.md](./models.md)**

---

## Quick Model Reference

### Core Models

- **Position** - Latitude, longitude, altitude
- **Route** - Waypoints, timing, metadata
- **POI** - Point of interest with ETA
- **Mission** - Complete mission configuration
- **Timeline** - Communication timeline segments

### Common Fields

```json
{
  "id": "uuid",
  "name": "string",
  "created_at": "ISO 8601 timestamp",
  "updated_at": "ISO 8601 timestamp"
}
```

### Example: Route Model

```json
{
  "id": "route-001",
  "name": "Flight Route",
  "waypoints": [{ "latitude": 40.7, "longitude": -74.0, "altitude": 5000 }],
  "has_timing_data": true,
  "total_distance_meters": 150000
}
```

---

[Full Models Documentation →](./models.md)

[Back to API Reference](./README.md)
