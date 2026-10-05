# POI Management Troubleshooting

Troubleshooting guide for Points of Interest (POI) management issues.

---

## POI List Empty or Missing

**Check POI file:**

```bash
# File exists?
ls -la backend/starlink-location/data/pois.json

# Content valid?
cat backend/starlink-location/data/pois.json | jq .

# If corrupted, reset
echo '[]' > backend/starlink-location/data/pois.json
docker compose restart starlink-location
```

---

## Can't Create/Edit POIs

**Check API:**

```bash
# Test POI creation
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "latitude": 40.7, "longitude": -74.0}'

# Check response for errors
# If 500 error, check backend logs:
docker compose logs starlink-location | tail -20
```

**Check file permissions:**

```bash
# POI file writable?
docker compose exec starlink-location ls -la /app/data/pois.json

# Fix if needed
docker compose exec starlink-location chmod 666 /app/data/pois.json
```

---

## ETA Calculations Incorrect

**Verify POI coordinates:**

```bash
# List POIs
curl http://localhost:8000/api/pois | jq '.[] | {name, latitude, longitude}'

# Manually calculate distance
# Using Haversine formula to NYC (40.7128, -74.0060)

# Verify ETAs
curl http://localhost:8000/api/pois/etas | \
  jq '.[] | {name, distance_meters, eta_seconds}'
```

**Check speed used in calculation:**

```bash
# If not specified, uses fallback 67 knots
# To use current speed:
curl "http://localhost:8000/api/pois/etas?speed_knots=50"
```

---

## POI Display Not Updating

Verify the POI endpoint and reload the POI management page:

```bash
curl --fail http://localhost:8000/api/pois/etas | jq length
open http://localhost:8000/ui/pois
```

For the native Overview arrival panel, verify the active Mission V2 leg and its
matching route. See the Overview features guide for timing and freshness rules.
