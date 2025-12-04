# Development Tools

Utility scripts for testing, development, and operations.

## Available Tools

### setup_pois.py

Creates a set of evenly-spaced POIs around a circular test track for course
tracking and ETA testing.

**Purpose:** Generate test waypoints in a controlled circular pattern for
validating POI and ETA functionality without manual data entry.

**Requirements:**

- Python 3.7+
- `requests` library
- Backend service running at `<http://localhost:8000`>

**Usage:**

```bash
python3 tools/setup_pois.py
```

**Configuration:**

Edit the script's configuration section to customize:

- `CENTER_LAT`, `CENTER_LON` - Circle center point (default: NYC)
- `RADIUS_KM` - Distance from center (default: 100 km)
- `NUM_POIS` - Number of waypoints to create (default: 20)

**What It Does:**

1. **Deletes all existing POIs** - Cleans slate for fresh testing
2. **Creates evenly-spaced waypoints** - Places POIs at regular angular
   intervals around the circle
3. **Displays progress** - Shows each created waypoint with coordinates

**Example Output:**

```
Deleting 20 existing POIs...
  Deleted: Waypoint 01
  ...

Creating 20 POIs around circular track...
Center: 40.7128°N, 74.0060°W
Radius: 100 km
Spacing: 18° apart

  ✓ Waypoint 01         at 40.6410°, -74.5643°
  ✓ Waypoint 02         at 40.1234°, -75.0567°
  ...
✓ Successfully created 20 evenly-spaced POIs!
✓ POIs are ready for course tracking tests!
```

**Testing Workflow:**

```bash
# 1. Start the backend and Grafana
docker compose up -d

# 2. Create test POIs
python3 tools/setup_pois.py

# 3. Open Grafana and view the POI Management dashboard
# <http://localhost:3000> (admin/admin)

# 4. Observe ETA calculations as the simulated aircraft moves
# around the circular path
```

**Technical Details:**

- Uses **Haversine formula** to calculate waypoint coordinates based on bearing
  and distance
- **Evenly distributed** - Places POIs at 360°/N intervals around the center
  point
- **REST API** - Creates POIs via FastAPI `/api/pois` endpoint
- **Idempotent** - Safe to run multiple times; clears old POIs first

**Troubleshooting:**

**"Connection refused"**

```bash
# Ensure backend is running
docker compose logs -f starlink-location
curl <http://localhost:8000/health>
```

**"No module named requests"**

```bash
pip install requests
```

**POIs don't appear in Grafana**

- Check that the Infinity datasource is configured correctly
- Verify POI API endpoint returns data: `curl <http://localhost:8000/api/pois`>
- Refresh Grafana dashboard (F5)
