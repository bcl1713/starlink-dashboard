# Grafana Geomap Troubleshooting Log

## Problem Statement
Grafana geomap panels were displaying green overlays on each country with progress bars instead of showing a red position marker from the current location data.

## Root Causes Identified

### 1. Numeric Properties in GeoJSON (FIXED)
- **Issue**: GeoJSON feature properties contained numeric values: `latitude`, `longitude`, `altitude`, `speed_knots`, `heading_degrees`
- **Effect**: Grafana normalized these values (e.g., 41.6° latitude → 41% fill) and rendered them as choropleth across all countries
- **Fix Applied**: Removed all numeric properties from feature properties, keeping only: `type`, `name`, `timestamp`
- **File**: `/app/services/geojson.py` - `build_current_position_feature()` method

### 2. Root-Level Properties in FeatureCollection (FIXED)
- **Issue**: FeatureCollection had root-level `properties` object with `feature_count: 1`
- **Effect**: Grafana interpreted this as data and created choropleth visualization
- **Fix Applied**: Removed entire root-level `properties` object from FeatureCollection
- **File**: `/app/services/geojson.py` - `build_feature_collection()` method

### 3. FieldConfig Thresholds (PARTIALLY ADDRESSED)
- **Issue**: Grafana was adding threshold colors to panels (green for null value)
- **Effect**: Even with no data, thresholds were being applied to geographic regions
- **Fix Attempted**:
  - Set `allowUiUpdates: false` in `/monitoring/grafana/provisioning/dashboards/dashboards.yml`
  - Cleaned up fieldConfig to empty defaults in dashboard JSONs
  - Deleted Grafana persistent data and restarted fresh
- **Status**: Thresholds persist in Grafana UI even though provisioned file is clean

### 4. Grafana Database Override (PARTIALLY FIXED)
- **Issue**: `allowUiUpdates: true` was saving UI changes to Grafana's database, overriding provisioned configs
- **Fix Applied**: Changed to `allowUiUpdates: false` in `dashboards.yml`
- **Status**: Database was cleared, but issue may reappear if UI modifications are made

## Attempted Solutions (All Failed)

### Attempt 1: GeoJSON Layer with Style Configuration
**Configuration**:
- GeoJSON layer with `jsonEndpoint` mode
- Explicit `style` object with red color and opacity settings
- Empty Prometheus targets

**Result**: ❌ Green overlays still appeared, no marker visible

**Theory**: GeoJSON layer rendering with style might be triggering choropleth even with no data

---

### Attempt 2: Removed GeoJSON Layer, Added Prometheus Coords Mode
**Configuration**:
- No layers array (empty)
- Prometheus datasource with targets for latitude/longitude metrics
- Location mode: `"coords"` with `lat: "latitude"`, `lng: "longitude"`
- Time series queries

**Result**: ❌ Data flowed correctly (21 rows showing), but no marker displayed on map

**Theory**: `coords` mode might not work with time series data (multiple rows)

---

### Attempt 3: Same as Attempt 2 but with Instant Queries
**Configuration**:
- Changed queries to use `last_over_time(metric[5m])` with `instant: true`
- Added `legendFormat` to name fields correctly
- Result: Single row of data (one latitude/longitude pair)

**Result**: ❌ Field names correct ("latitude", "longitude"), single data point present, but still no marker

**Theory**: `coords` mode might have a different field naming requirement or might not support this data structure in Grafana 12.2.1

---

### Attempt 4: Added FieldConfig Overrides for Coords Mode
**Configuration**:
- Added `fieldConfig.overrides` to explicitly set units and visibility for latitude/longitude fields
- Kept instant queries and legendFormat

**Result**: ❌ Still no marker displayed

**Theory**: Field overrides for visibility/units don't help with coordinate detection

---

### Attempt 5: Switched Back to GeoJSON Layer (Current State)
**Configuration**:
- GeoJSON layer with `jsonEndpoint` mode pointing to `/api/position.geojson`
- No Prometheus targets
- Location mode: empty object `{}`
- Marker: circle, dark-red, size 8

**Result**: ❌ Green overlays returned, no marker visible

**Theory**: GeoJSON layer rendering is being overridden by some default Grafana behavior

---

## Current State

### Backend
- ✅ GeoJSON endpoint (`/api/position.geojson`) working correctly
- ✅ Returns clean FeatureCollection with single Point feature
- ✅ Properties contain only: type, name, timestamp (no numeric values)
- ✅ Coordinates correct: [-74.006, 41.612...]

### Grafana Configuration
- ✅ Dashboard files cleaned (empty fieldConfig with no thresholds)
- ✅ Provisioning set to `allowUiUpdates: false`
- ✅ Grafana database cleared and fresh restart
- ⚠️ Green overlays still visible (unexplained)
- ❌ No position marker rendering

### Files Modified
1. `/app/services/geojson.py` - Removed numeric properties and root-level properties
2. `/monitoring/grafana/provisioning/dashboards/dashboards.yml` - Set `allowUiUpdates: false`
3. `/monitoring/grafana/provisioning/dashboards/overview.json` - Multiple panel config attempts
4. `/monitoring/grafana/provisioning/dashboards/position-movement.json` - Same changes as overview
5. `backend/starlink-location/app/services/geojson.py` - Rebuilt Docker image

## Hypotheses for Next Investigation

1. **Grafana Version Issue**: Grafana 12.2.1 might have different geomap behavior than earlier versions
   - Need to check Grafana geomap plugin release notes
   - Might need to downgrade or upgrade Grafana

2. **GeoJSON Layer Bug**: The `jsonEndpoint` mode in this Grafana version might not properly render Point features
   - Try using `table` layer type instead
   - Try inline GeoJSON instead of jsonEndpoint

3. **Data Format Issue**: Grafana's geomap might expect a different GeoJSON structure
   - Try adding non-numeric feature properties
   - Try different geometry types or feature structures

4. **Browser/UI Cache Issue**: Despite hard refreshes, UI might be caching old configuration
   - Try different browser
   - Try incognito/private mode
   - Clear all Grafana cookies

5. **Hidden Grafana Setting**: Some configuration might be overriding the panel settings
   - Check Grafana's data source JSON model
   - Check if there's a default marker/layer config being applied

## Next Steps to Try Tomorrow

1. Check Grafana version and geomap plugin compatibility
2. Try using a table layer instead of geojson layer
3. Try inline GeoJSON in the panel config instead of jsonEndpoint
4. Inspect Grafana's API response for the dashboard to see actual panel config vs provisioned file
5. Try a completely different visualization type (e.g., Nodesgraph) just to verify data flow works
6. Consider using a different approach: stat panel with map overlay, or custom plugin

## Useful Commands

```bash
# Verify backend endpoint
curl -s http://localhost:8000/api/position.geojson | jq '.'

# Check Grafana logs
docker compose logs grafana | grep -i "error\|dashboard\|provision"

# Restart services
docker compose restart grafana
docker compose restart starlink-location

# Check Grafana health
curl -s http://localhost:3000/api/health | jq '.'

# Rebuild backend
docker compose build --no-cache starlink-location
```

## Timeline
- 2025-10-24 03:14:22 - Investigation started, identified green overlays from numeric GeoJSON properties
- 2025-10-24 03:28:38 - Removed numeric properties from GeoJSON, green overlays persisted
- 2025-10-24 03:31:02 - Removed root-level properties from FeatureCollection, issue continued
- 2025-10-24 03:35:10 - Set allowUiUpdates=false, cleared Grafana DB, restarted fresh
- 2025-10-24 03:42:33 - Switched to Prometheus coords mode with time series data
- 2025-10-24 03:44:21 - Used instant queries instead, data correct but no marker
- 2025-10-24 03:50+ - Added field overrides, switched back to GeoJSON layer
- **Status**: Green overlays back, no marker visible, cause unknown
