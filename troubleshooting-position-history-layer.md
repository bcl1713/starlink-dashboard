# Position History Layer Troubleshooting Log

**Date:** October 24, 2025
**Issue:** Position history route layer not displaying on Position & Movement dashboard
**Current Status:** Plane marker shows, but route line does NOT show

---

## Current State

### What Works
- ✅ **Starlink Overview dashboard** - Shows BOTH route and plane marker correctly
- ✅ **Current position marker** (plane icon) on Position & Movement dashboard
- ✅ **All Prometheus queries return data** - verified via Network tab

### What Doesn't Work
- ❌ **Historical route line** does NOT display on Position & Movement dashboard

---

## Query Results (Verified Working)

From Network tab inspection:

**Instant Queries (Current Position):**
- Query A (latitude): ✅ Returns current lat (e.g., 40.27013040354489)
- Query B (longitude): ✅ Returns current lon (e.g., -72.9766536607164)
- Query C (altitude_feet): ✅ Returns current altitude (e.g., 5372.56 ft)
- Query D (heading): ✅ Returns current heading (e.g., 210.16°)

**Historical Queries (Route Path):**
- Query E (lat_history): ✅ Returns 21 data points with timestamps
- Query F (lon_history): ✅ Returns 21 data points with timestamps
- Query G (alt_history using altitude_feet): ✅ Returns 21 data points with timestamps
- Query H (head_history): ✅ Returns 21 data points with timestamps

**Telemetry Queries:**
- Query I (speed): ✅ Returns historical speed data
- Query J (latency): ❌ EMPTY (metric not available)
- Query K (throughput_down): ❌ EMPTY (metric not available)
- Query L (throughput_up): ❌ EMPTY (metric not available)
- Query M (obstructions): ✅ Returns data (constant 30%)

---

## Key Discovery: altitude_meters vs altitude_feet

**CRITICAL:** Backend exports `starlink_dish_altitude_feet`, NOT `starlink_dish_altitude_meters`

Initial implementation used `altitude_meters` which returned EMPTY data, preventing route display.
Changed to `altitude_feet` - now Query G returns 21 data points.

---

## Configuration Attempts (Chronological)

### Attempt 1: Initial Implementation (Commit 4c1133e)
- Queries: A-D instant, E-M historical with avg_over_time
- Transformations: Complex pipeline (join, organize, convert, filter)
- Route layer: coords mode, field-based altitude coloring
- Markers layer: coords mode
- **Result:** Neither route nor marker displayed

### Attempt 2: Separate Datasets (Commit 922f309)
- Added lat_marker, lon_marker separate from lat/lon history
- Tried to isolate marker and route data
- **Result:** Neither route nor marker displayed

### Attempt 3: Simplified Queries (Commit f5d6e92)
- **THIS ONE SHOWED THE ROUTE!**
- Removed instant queries entirely
- All queries A-I were time-series (instant: false)
- Simple merge transformation
- legendFormat: "latitude", "longitude", "altitude", "heading"
- Route layer: coords mode with "latitude"/"longitude" fields
- **Result:** ✅ Route displayed, ❌ No plane marker (no instant data)

### Attempt 4: Add Instant Queries (Commit bd78380)
- Added back instant queries A-D for current position
- Historical queries E-H with different legendFormat (lat_history, lon_history, etc.)
- Route layer: coords mode with lat_history/lon_history
- Markers layer: auto mode
- Transformation: joinByField by Time
- **Result:** ✅ Plane marker displayed, ❌ Route disappeared

### Attempt 5: Fixed Altitude Metric (Commit 38e4401)
- Changed altitude_meters → altitude_feet
- **Result:** Queries now return data, but route still not visible

### Attempt 6: Auto Mode for Route (Commit 7b253ca)
- Route layer: auto mode (to match overview dashboard exactly)
- **Result:** ❌ Route still not visible

### Attempt 7: Explicit Coords Mode (Commit 8601d9b - CURRENT)
- Route layer: coords mode with lat_history/lon_history
- Markers layer: auto mode
- **Result:** ✅ Plane shows, ❌ Route still not visible

---

## Working Configuration (Overview Dashboard)

**File:** `monitoring/grafana/provisioning/dashboards/overview.json`

**Queries:**
```json
{
  "expr": "starlink_dish_latitude_degrees",
  "instant": true,
  "legendFormat": "latitude",
  "refId": "A"
},
{
  "expr": "starlink_dish_longitude_degrees",
  "instant": true,
  "legendFormat": "longitude",
  "refId": "B"
},
{
  "expr": "starlink_dish_altitude_feet",
  "instant": true,
  "legendFormat": "altitude",
  "refId": "C"
},
{
  "expr": "starlink_dish_heading_degrees",
  "instant": true,
  "legendFormat": "heading",
  "refId": "D"
},
{
  "expr": "starlink_dish_latitude_degrees",
  "instant": false,
  "legendFormat": "lat_history",
  "refId": "E"
},
{
  "expr": "starlink_dish_longitude_degrees",
  "instant": false,
  "legendFormat": "lon_history",
  "refId": "F"
},
{
  "expr": "starlink_dish_altitude_feet",
  "instant": false,
  "legendFormat": "alt_history",
  "refId": "G"
},
{
  "expr": "starlink_dish_heading_degrees",
  "instant": false,
  "legendFormat": "heading_history",
  "refId": "H"
}
```

**Transformation:**
```json
{
  "id": "joinByField",
  "options": {
    "byField": "Time",
    "mode": "outer"
  }
}
```

**Route Layer:**
```json
{
  "type": "route",
  "name": "Historical Route",
  "config": {
    "style": {
      "color": {"fixed": "green"},
      "opacity": 0.6,
      "lineWidth": 3
    },
    "showLegend": true
  },
  "location": {"mode": "auto"},
  "tooltip": false
}
```

**Markers Layer:**
```json
{
  "type": "markers",
  "name": "Current Position",
  "config": {
    "style": {
      "color": {"fixed": "green"},
      "opacity": 1,
      "rotation": {
        "field": "heading",
        "mode": "field"
      },
      "size": {"fixed": 12},
      "symbol": {"fixed": "img/icons/marker/plane.svg"}
    }
  },
  "location": {"mode": "auto"},
  "tooltip": true
}
```

**THIS CONFIGURATION WORKS IN OVERVIEW DASHBOARD!**

---

## Current Configuration (Position & Movement)

**File:** `monitoring/grafana/provisioning/dashboards/position-movement.json`

**Queries:** Same as Overview (A-D instant, E-H historical, I-M telemetry)

**Transformation:** Same as Overview (joinByField by Time, outer mode)

**Route Layer:**
```json
{
  "type": "route",
  "name": "Position History Route",
  "config": {
    "style": {
      "color": {"fixed": "green"},
      "opacity": 0.6,
      "lineWidth": 3
    },
    "showLegend": true
  },
  "location": {
    "mode": "coords",
    "latitude": "lat_history",
    "longitude": "lon_history"
  },
  "tooltip": true
}
```

**Markers Layer:**
```json
{
  "type": "markers",
  "name": "Current Position",
  "config": {
    "style": {
      "color": {"fixed": "green"},
      "opacity": 1,
      "rotation": {"field": "heading", "mode": "field"},
      "size": {"fixed": 12},
      "symbol": {"fixed": "img/icons/marker/plane.svg"}
    }
  },
  "location": {"mode": "auto"},
  "tooltip": true
}
```

---

## Differences Between Working (Overview) and Not Working (Position & Movement)

1. **Route layer location mode:**
   - Overview: `"mode": "auto"`
   - Position & Movement: `"mode": "coords"` with explicit lat_history/lon_history

2. **Route layer tooltip:**
   - Overview: `"tooltip": false`
   - Position & Movement: `"tooltip": true`

3. **Queries:**
   - Overview: A-H only (position + history)
   - Position & Movement: A-M (position + history + telemetry)

4. **Panel-level fieldConfig:**
   - Overview: Simple, uses thresholds mode
   - Position & Movement: Uses continuous-GrYlRd color mode for altitude gradient

---

## Hypotheses for Why Route Doesn't Show

### Hypothesis 1: Layer Order or Z-Index
- ❓ Route layer is being rendered but hidden behind something
- Counterpoint: Route is listed first in layers array, should render first (behind markers)

### Hypothesis 2: Data Join Issue
- ❓ joinByField transformation causing issues with mixed instant/time-series data
- Note: Same transformation works in Overview dashboard

### Hypothesis 3: Field Mapping Issue
- ❓ lat_history/lon_history fields not being found or recognized
- Counterpoint: Query results show these fields are being created with displayNameFromDS

### Hypothesis 4: Grafana Version or Panel Config
- ❓ Some panel-level configuration is preventing route rendering
- Note: Both panels use same Grafana instance and same plugin version

### Hypothesis 5: Telemetry Queries Interference
- ❓ Empty telemetry queries (J, K, L) causing transformation issues
- Worth testing: Remove queries J, K, L and see if route appears

---

## Next Steps to Try

### Option 1: Exact Copy of Overview Config
Copy the EXACT working configuration from overview.json to position-movement.json:
- Use auto mode for route layer (not coords)
- Set route tooltip to false
- Remove queries I-M (telemetry)
- Simplify fieldConfig to match overview

### Option 2: Remove Empty Queries
Remove queries J, K, L (latency, throughput) that return empty data.
Test if joinByField transformation fails when some queries are empty.

### Option 3: Separate Panels
Create two separate Geomap panels:
- Panel 1: Just the route (using only historical queries E-H)
- Panel 2: Just the marker (using only instant queries A-D)
Then overlay them or place side-by-side.

### Option 4: Check Grafana Logs
Look at Grafana container logs during dashboard load:
```bash
docker compose logs grafana -f
```
Refresh dashboard and look for errors related to geomap rendering.

### Option 5: Browser Developer Tools
Open browser DevTools → Console tab during dashboard load.
Look for JavaScript errors related to route layer rendering.

---

## Files Modified

- `monitoring/grafana/provisioning/dashboards/position-movement.json` - Main dashboard configuration
- `CLAUDE.md` - Documentation (added Position History Layer section)
- `docs/grafana-setup.md` - User guide (added Position History Route section)
- `tasks/tasks-0007-prd-position-history-layer.md` - Task tracking

---

## Git Commits

```
7b253ca - fix: use auto mode for route layer to match overview dashboard
38e4401 - fix: use altitude_feet instead of altitude_meters (meters has no data)
e244e1d - fix: temporarily use fixed color for route layer debugging
bd78380 - fix: add instant queries and auto mode for current position marker
f5d6e92 - fix: simplify geomap configuration for visibility (ROUTE SHOWED HERE!)
922f309 - fix: restore current position marker and route layer visibility
18c2f00 - docs: mark PRD-0007 tasks as complete
4c1133e - feat: add position history layer with altitude-based coloring
```

**IMPORTANT:** Commit `f5d6e92` showed the route line, but no plane marker.

---

## Questions to Answer

1. Why does the EXACT same layer configuration work in overview.json but not in position-movement.json?
2. Is there a panel-level setting that's preventing route rendering?
3. Does Grafana's route layer have issues when some joined queries return empty data?
4. Is the fieldConfig color mode (continuous-GrYlRd) interfering with route rendering?

---

## End of Log

**Recommendation:** Start fresh session with Option 1 (exact copy) or Option 5 (browser DevTools inspection).
