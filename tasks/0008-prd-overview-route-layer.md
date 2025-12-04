# PRD-0008: Position History Route on Fullscreen Overview Dashboard

## 1. Introduction/Overview

This feature adds a visual route layer to the Fullscreen Overview dashboard's
Geomap panel, displaying the Starlink terminal's position history over the
dashboard's selected time range. The implementation will be done entirely
through provisioned configuration files (JSON/YAML), modifying
`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`.

**Problem Statement:** The current Fullscreen Overview dashboard only shows the
terminal's current position with a marker. Users cannot visualize where the
terminal has been over time. The existing Position & Movement dashboard was
intended to solve this but doesn't work as expected and may be deprecated.

**Goal:** Add a route layer to the existing Geomap panel in the provisioned
dashboard JSON to display both the current position marker and a route showing
position history, using the dashboard's time range (respecting 1-second data
sampling intervals).

## 2. Goals

1. Display a route line showing position history over the dashboard's selected
   time range
1. Maintain 1-second sampling intervals consistent with other overview dashboard
   panels
1. Show the current position marker on top of the historical route
1. Use a simple single-color route line (with future capability to add
   metric-based coloring)
1. Start with no interactivity (tooltips), with plans to add detailed telemetry
   tooltips later
1. Handle data gaps with straight-line interpolation
1. Implement entirely through JSON/YAML configuration edits (no UI clicking)
1. Use Grafana's Route layer if feasible, fallback to alternative approaches if
   needed

## 3. User Stories

1. **As a user viewing the overview dashboard**, I want to see where my Starlink
   terminal has traveled during the selected time range so that I can understand
   my movement patterns alongside real-time metrics.

1. **As a user analyzing terminal performance**, I want the route to use the
   same time range as all other dashboard panels so that I can correlate
   position history with network metrics over the same period.

1. **As a user monitoring in real-time**, I want to see the current position
   marker clearly visible on top of the route so that I can distinguish between
   where I am now and where I've been.

1. **As a user with intermittent connectivity**, I want data gaps to be
   interpolated with straight lines so that my route remains continuous even
   when the terminal was offline.

1. **As a future user**, I want the system designed to eventually support
   metric-based route coloring (altitude, speed, latency) so that I can
   visualize additional context on the route.

## 4. Functional Requirements

### 4.1 Route Visualization

1. The system must add a new layer to the existing Geomap panel in
   `fullscreen-overview.json`
1. The route layer must render position history as a continuous line/path
1. The route line must use a **single solid color** that provides good contrast
   on the map
1. The route line must not interfere with or obscure the current position marker
1. The current position marker layer must be ordered **after** the route layer
   in the layers array (rendered on top)
1. The route line should have a **width of 2-3 pixels**
1. The route must update automatically as new position data arrives from
   Prometheus
1. When data gaps exist, the system must **interpolate linearly** with a solid
   line

### 4.2 Time Range Integration

1. The route must use **range queries** (not instant queries) to fetch
   historical data
1. The queries must respect the **dashboard's global time range selector**
1. When the user changes the dashboard time range, the route must update
   automatically
1. The system must work with any time range (5 minutes to 15 days)

### 4.3 Data Requirements

1. Add new Prometheus query targets for historical position data:
   - Latitude time series (`starlink_dish_latitude_degrees`)
   - Longitude time series (`starlink_dish_longitude_degrees`)
2. Use **range queries** (not instant queries) with 1-second interval
3. The existing instant queries for current position marker remain unchanged
4. Transformations must merge historical lat/lon data into fields for the route
   layer

### 4.4 JSON Configuration Structure

1. Modify the Geomap panel (currently at ID 1) in `fullscreen-overview.json`
2. Add new query targets (refIds E, F for historical lat/lon)
3. Add or modify transformations to prepare data for route layer
4. Add new route layer configuration to the `options.layers` array
5. Ensure route layer is positioned before the marker layer in the array

### 4.5 Implementation Approach

1. **Primary approach:** Use Grafana's Route layer type in the layers
   configuration
1. **Fallback approach:** If Route layer has issues, use alternative layer type
   or configuration
1. All work done through direct JSON editing of the provisioned dashboard file
1. Test by reloading the dashboard in Grafana (dashboard auto-updates from
   provisioned files)

### 4.6 Performance

1. Use 1-second sampling (`interval: "1s"`) for historical queries
2. For very long time ranges, Grafana/Prometheus will automatically downsample
3. Monitor dashboard load performance after implementation
4. If performance issues occur, implement dynamic interval based on time range

### 4.7 Compatibility

1. Must work with current Grafana version (12.2.1 based on pluginVersion in
   JSON)
1. Must work in both simulation mode and live mode
1. Must not break existing dashboard functionality
1. Must maintain compatibility with existing provisioning setup

## 5. Non-Goals (Out of Scope)

1. **Separate time range selector:** Use dashboard's global time range only
2. **Toggle control:** No show/hide toggle in initial implementation
3. **Altitude-based color gradient:** Initial implementation uses single solid
   color
4. **Interactive tooltips:** Not included initially (planned for future)
5. **Dashed line styling for gaps:** Use solid lines (Grafana limitation)
6. **Multiple discontinuous route segments:** All points connected as single
   route
7. **UI-based configuration:** No clicking around Grafana UI (pure JSON/YAML)
8. **Preserving Position & Movement dashboard:** May be deprecated

## 6. Design Considerations

### 6.1 Route Color

- Use a color that contrasts well with the green current position marker
- Suggested colors: `"blue"`, `"dark-blue"`, or `"semi-dark-blue"`
- Avoid red (often used for alerts) and green (current position marker)
- Test visibility on OpenStreetMap basemap

### 6.2 Layer Ordering in JSON

```json
"layers": [
  {
    "type": "route",  // or appropriate type
    "name": "Position History",
    // ... route configuration
  },
  {
    "type": "markers",
    "name": "Current Position",
    // ... existing marker configuration
  }
]
```

**Important:** In Grafana's Geomap, layers array is rendered in order. First
layer is bottom, last layer is on top. So route should come **before** marker in
the array.

### 6.3 Query Structure

**Existing queries (keep as-is):**

- Query A: `starlink_dish_latitude_degrees` (instant: true) - for current
  position
- Query B: `starlink_dish_longitude_degrees` (instant: true) - for current
  position
- Query C: `starlink_dish_altitude_feet` (instant: true)
- Query D: `starlink_dish_heading_degrees` (instant: true)

**New queries to add:**

- Query E: `starlink_dish_latitude_degrees` (instant: false, range: true) - for
  route
- Query F: `starlink_dish_longitude_degrees` (instant: false, range: true) - for
  route

### 6.4 Transformation Strategy

The panel currently has a `joinByField` transformation to merge instant queries.
Need to extend this to handle both instant (current position) and range
(historical route) queries.

**Approach:**

1. Keep existing transformation for current position marker data
2. Route layer can reference the range query data directly (if Grafana Route
   layer supports this)
3. OR add additional transformations to format route data separately

**Note:** This will be determined during implementation based on Grafana's layer
data binding capabilities.

## 7. Technical Considerations

### 7.1 Current Panel Structure

The Geomap panel (ID 1) currently has:

- **Type:** `geomap`
- **Queries:** 4 instant queries (A, B, C, D)
- **Transformations:** `joinByField` with `byField: "Time"`, `mode: "outer"`
- **Layers:** 1 marker layer for current position
- **Plugin Version:** 12.2.1

### 7.2 Route Layer Configuration (Grafana 12.x)

Based on Grafana Geomap Route layer documentation, the configuration should look
like:

```json
{
  "type": "route",
  "name": "Position History",
  "config": {
    "style": {
      "color": {
        "fixed": "blue"
      },
      "opacity": 0.8,
      "lineWidth": 3
    }
  },
  "location": {
    "mode": "coords",
    "latitude": "latitude_history", // field name from query/transformation
    "longitude": "longitude_history" // field name from query/transformation
  },
  "tooltip": false
}
```

**Note:** Field names and exact structure may need adjustment during
implementation based on actual Grafana behavior.

### 7.3 Alternative Approach: Path Layer

If Route layer doesn't work well, Grafana also supports a "path" layer type or
line-based visualization:

```json
{
  "type": "line", // or "path"
  "name": "Position History"
  // ... similar configuration
}
```

### 7.4 Data Binding Strategy

**Challenge:** How to bind range query data to the route layer while keeping
instant query data for the marker layer.

**Possible solutions:**

1. **Data links:** Each layer can filter/select which query data it uses
2. **Multiple transformations:** Create separate data frames for route vs.
   marker
3. **Field naming:** Use distinct field names for route lat/lon vs. marker
   lat/lon

**Decision:** To be determined during implementation through testing.

### 7.5 File Modification Process

1. Edit `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
2. Grafana should auto-reload provisioned dashboards on file change
3. If not auto-reloading, restart Grafana: `docker compose restart grafana`
4. Verify changes in browser (may need hard refresh: Ctrl+Shift+R)

### 7.6 Testing Strategy

1. Make incremental JSON changes
2. After each change, reload dashboard to verify
3. Use browser DevTools console to check for Grafana errors
4. Inspect panel query results in Grafana's Query Inspector
5. If JSON is malformed, Grafana will fail to load dashboard

### 7.7 JSON Validation

Before reloading in Grafana:

1. Validate JSON syntax using `jq` or online validator
2. Check that all brackets/braces are balanced
3. Ensure no trailing commas in arrays/objects
4. Verify string escaping is correct

**Command to validate:**

```bash
jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
# No output = valid JSON
# Error message = syntax issue
```

### 7.8 Grafana Documentation References

For implementation, consult:

- Grafana Geomap panel documentation
- Grafana Route layer (beta) documentation
- Grafana panel JSON schema
- Grafana provisioning documentation

The Grafana bot's response mentioned these key points:

- Use coords location mode with lat/lon field names
- Route layer can display path with optional arrows
- Transformations can extract and organize fields
- Same Prometheus data can feed multiple layers

## 8. Implementation Steps for Junior Developer

### Phase 1: Setup and Preparation

**Task 1.1: Backup Current Dashboard**

```bash
cd /path/to/starlink-dashboard-dev

# Create backup
cp monitoring/grafana/provisioning/dashboards/fullscreen-overview.json \
   monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup

# Or with timestamp
cp monitoring/grafana/provisioning/dashboards/fullscreen-overview.json \
   monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup-$(date +%Y%m%d-%H%M%S)
```

**Task 1.2: Validate Current JSON**

```bash
# Ensure current JSON is valid
jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json

# Pretty-print to verify structure
jq '.' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json | head -50
```

**Task 1.3: Review Grafana Documentation**

1. Open Grafana documentation for version 12.x
2. Search for "Geomap" panel type
3. Look for "Route layer" or "layers configuration"
4. Review the JSON schema for Geomap layers
5. Note any examples of route/path visualization

**Task 1.4: Identify Panel Structure**

```bash
# Extract just the Geomap panel (ID 1) for easier viewing
jq '.panels[] | select(.id == 1)' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/geomap-panel.json

# View the current layers configuration
jq '.panels[] | select(.id == 1) | .options.layers' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json

# View the current queries
jq '.panels[] | select(.id == 1) | .targets' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
```

### Phase 2: Add Historical Data Queries

**Task 2.1: Add Range Query for Historical Latitude**

Locate the `targets` array in the Geomap panel and add a new query:

```json
{
  "expr": "starlink_dish_latitude_degrees",
  "instant": false,
  "range": true,
  "intervalFactor": 1,
  "legendFormat": "latitude_history",
  "refId": "E",
  "interval": "1s"
}
```

**Task 2.2: Add Range Query for Historical Longitude**

Add another query to the `targets` array:

```json
{
  "expr": "starlink_dish_longitude_degrees",
  "instant": false,
  "range": true,
  "intervalFactor": 1,
  "legendFormat": "longitude_history",
  "refId": "F",
  "interval": "1s"
}
```

**Task 2.3: Apply Changes and Verify Queries**

1. Save the JSON file
2. Reload Grafana dashboard in browser
3. Open the "Current Position" panel in edit mode (if needed)
4. Check Query Inspector to verify queries E and F are returning data
5. Confirm data is time-series (not instant) with ~1-second intervals

**Validation command:**

```bash
# Verify JSON is still valid after edits
jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
```

### Phase 3: Add Route Layer Configuration

**Task 3.1: Understand Current Layers Structure**

Current structure (simplified):

```json
"layers": [
  {
    "type": "markers",
    "name": "Current Position",
    // ... existing marker config
  }
]
```

**Task 3.2: Add Route Layer Before Marker Layer**

Modify the `layers` array to:

```json
"layers": [
  {
    "type": "route",
    "name": "Position History",
    "config": {
      "style": {
        "color": {
          "fixed": "blue"
        },
        "opacity": 0.8,
        "lineWidth": 3
      },
      "showLegend": false
    },
    "location": {
      "mode": "coords",
      "latitude": "Value #E",
      "longitude": "Value #F"
    },
    "tooltip": false
  },
  {
    "type": "markers",
    "name": "Current Position",
    // ... keep existing marker config unchanged
  }
]
```

**Notes:**

- Field names may be `"Value #E"` and `"Value #F"` (Grafana's default naming for
  query results)
- May need to be `"latitude_history"` and `"longitude_history"` depending on how
  Grafana processes the `legendFormat`
- This will require testing to determine correct field names

**Task 3.3: Save and Test**

1. Save JSON file
2. Validate:
   `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
3. Reload dashboard in browser
4. Check if route appears
5. If route doesn't appear, check browser console for errors

**Task 3.4: Debug Field Names**

If route doesn't appear:

1. Open panel in Grafana UI (just for inspection, don't save changes)
2. Go to Transform tab to see actual field names from queries
3. Note the exact field names for query E and F results
4. Update the route layer's `latitude` and `longitude` field names in JSON
5. Save and reload

### Phase 4: Handle Data Transformations

**Task 4.1: Review Current Transformation**

Current transformation:

```json
"transformations": [
  {
    "id": "joinByField",
    "options": {
      "byField": "Time",
      "mode": "outer"
    }
  }
]
```

This joins all instant queries by timestamp.

**Task 4.2: Determine if Additional Transformations are Needed**

**Scenario A:** Route layer can read range query data directly

- No additional transformations needed
- Route layer just needs correct field names

**Scenario B:** Route layer needs data in specific format

- May need to add transformations to organize/rename fields
- Possible transformations: "organize fields", "filter fields by name"

**Action:** Test Scenario A first. If route doesn't render, investigate Scenario
B.

**Task 4.3: Add Field Organization if Needed**

If field names are confusing or route layer can't find data, add transformation:

```json
"transformations": [
  {
    "id": "joinByField",
    "options": {
      "byField": "Time",
      "mode": "outer"
    }
  },
  {
    "id": "organize",
    "options": {
      "excludeByName": {},
      "indexByName": {},
      "renameByName": {
        "Value #E": "route_lat",
        "Value #F": "route_lon"
      }
    }
  }
]
```

Then update route layer to use `"route_lat"` and `"route_lon"`.

### Phase 5: Fine-Tuning and Testing

**Task 5.1: Adjust Route Appearance**

Once route renders, fine-tune in JSON:

- **Line width:** Change `"lineWidth"` value (2-4 pixels)
- **Color:** Try different colors (`"blue"`, `"dark-blue"`, `"purple"`)
- **Opacity:** Adjust `"opacity"` (0.6-1.0)

**Task 5.2: Test with Different Time Ranges**

In Grafana UI:

1. Change dashboard time range to "Last 5 minutes"
2. Verify route updates and shows last 5 minutes of movement
3. Try "Last 1 hour"
4. Try "Last 24 hours"
5. Note any performance issues

**Task 5.3: Test in Both Operating Modes**

6. **Simulation mode:**

   ```bash
   # Ensure STARLINK_MODE=simulation in .env
   docker compose restart backend
   ```

   - Wait for simulated data to accumulate
   - Verify route displays simulated movement

1. **Live mode (if available):**

   ```bash
   # Set STARLINK_MODE=live in .env
   docker compose restart backend
   ```

   - Verify route displays actual movement

**Task 5.4: Verify Layer Ordering**

1. Ensure current position marker (green plane) is visible on top of route
2. If marker is hidden under route, swap layer order in JSON:
   - Route layer should come **first** in the `layers` array
   - Marker layer should come **last** in the `layers` array

**Task 5.5: Test Edge Cases**

3. **No data:**

   ```bash
   docker compose stop backend
   ```

   - Reload dashboard
   - Verify it shows "No data" gracefully (no errors)
   - Restart: `docker compose start backend`

1. **Very short time range:**
   - Set to "Last 30 seconds"
   - Verify route displays correctly (may be very short or single point)

1. **Very long time range:**
   - Set to "Last 7 days"
   - Verify route loads and renders (may take a few seconds)

### Phase 6: Fallback to Alternative Approach (if Route Layer Fails)

**If Route layer type doesn't work or has issues, try alternative:**

**Task 6.1: Try "heatmap" or "line" Layer Type**

Change layer type from `"route"` to `"heatmap"` or another supported type:

```json
{
  "type": "heatmap", // or "markers" with special styling
  "name": "Position History"
  // ... adapt configuration
}
```

**Task 6.2: Consult Grafana Source/Examples**

1. Check Grafana GitHub repository for Geomap examples
2. Look for example dashboards with route/path visualization
3. Import example dashboard JSON to study configuration

**Task 6.3: Consider Two-Marker-Layers Approach**

If route layer is not available in this Grafana version:

1. Create multiple marker layers with connected points
2. Or use a very small marker size to simulate a line
3. This is a workaround and may not look as clean

**Task 6.4: Document Findings**

If route layer doesn't work:

- Document the issue in a comment or separate file
- Note the Grafana version and limitation
- Propose alternative solution or upgrade path

### Phase 7: Documentation and Finalization

**Task 7.1: Validate Final JSON**

```bash
# Ensure JSON is valid
jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json

# Format nicely (optional, creates formatted version)
jq '.' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/formatted.json
cp /tmp/formatted.json monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
```

**Task 7.2: Update CLAUDE.md**

Add section documenting the new feature:

```markdown
### Position History Route (Fullscreen Overview)

The Fullscreen Overview dashboard's map panel displays both current position and
historical route.

**Features:**

- Route shows position history over the selected dashboard time range
- Uses 1-second sampling intervals matching other overview panels
- Simple blue route line (future: metric-based coloring)
- Current position marker (green plane) displays on top of route
- Data gaps interpolated with straight lines

**Implementation:**

- Configured in
  `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- Uses Grafana Geomap Route layer (or alternative if Route layer unavailable)
- Queries Prometheus for historical lat/lon time series

**Known Limitations:**

- No interactive tooltips in initial version (planned future enhancement)
- Single solid color (no gradient or metric-based coloring yet)
- All points connected as continuous route (no segment breaks)
```

**Task 7.3: Remove Backup File (if Everything Works)**

```bash
# Once confident everything works
rm monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup*

# Or keep backup if you want
```

**Task 7.4: Git Commit**

```bash
git add monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
git add CLAUDE.md

git commit -m "Add position history route layer to fullscreen overview dashboard

- Add historical lat/lon range queries (1s interval)
- Configure Grafana Geomap route layer for position history
- Display route with simple blue line under current position marker
- Route respects dashboard time range selector
- Handle data gaps with linear interpolation
"
```

**Task 7.5: Final Testing Checklist**

- [ ] JSON is valid (passes `jq empty` check)
- [ ] Dashboard loads without errors in Grafana
- [ ] Route displays correctly over dashboard time range
- [ ] Current position marker visible on top of route
- [ ] Route updates when changing dashboard time range
- [ ] Works in simulation mode
- [ ] Works in live mode (if testable)
- [ ] No console errors in browser DevTools
- [ ] Performance is acceptable for typical time ranges
- [ ] Changes are committed to git
- [ ] Documentation updated in CLAUDE.md

### Phase 8: Future Enhancements (Not in Scope)

Once basic route is working, future work could include:

1. **Add tooltips:** Configure route layer with `"tooltip": true` and add
   telemetry data
1. **Metric-based coloring:** Use altitude, speed, or latency to color the route
1. **Dynamic sampling:** Adjust interval based on time range for better
   performance
1. **Separate route segments:** Detect gaps and create multiple layers
1. **Export functionality:** Add buttons to export route as GPX/KML

## 9. Success Metrics

1. **Functionality:**
   - Route displays correctly when dashboard time range is set to various
     intervals (5m, 1h, 24h)
   - Current position marker remains visible on top
   - Route updates automatically when time range changes

1. **Performance:**
   - Dashboard loads in <5 seconds with route enabled (24-hour time range)
   - No browser lag or freezing when rendering route
   - JSON file is well-formed and loads without Grafana errors

1. **Data Accuracy:**
   - Route visualization matches Prometheus data
   - All available position points are displayed (no missing segments except
     data gaps)
   - Route interpolates gaps as expected

1. **Maintainability:**
   - Changes are made entirely through JSON configuration (no manual UI changes)
   - JSON structure is clean and well-organized
   - Documentation clearly explains the configuration

1. **Compatibility:**
   - Works in both simulation and live modes
   - Works with current Grafana version (12.2.1)
   - Doesn't break existing dashboard functionality

## 10. Open Questions

**To be resolved during implementation:**

1. **Exact field names:** What are the actual field names that the route layer
   should reference?
   - Likely: `"Value #E"`, `"Value #F"`
   - Or: `"latitude_history"`, `"longitude_history"` (from legendFormat)
   - **Action:** Inspect query results in Grafana's Transform tab to determine
     exact names

1. **Route layer support:** Does Grafana 12.2.1 fully support the "route" layer
   type?
   - **Action:** Test by adding route layer configuration and checking if it
     renders
   - **Fallback:** If not supported, use alternative layer type or visualization
     method

1. **Transformation requirements:** Does the route layer need data in a specific
   format?
   - **Action:** Test if route renders with current transformation (joinByField
     only)
   - If not, add organize/filter transformations to prepare data correctly

1. **Performance at scale:** How does performance degrade with long time ranges
   (7+ days)?
   - **Action:** Test with 7-day and 15-day time ranges
   - If slow, implement dynamic interval or document limitation

1. **Color choice:** What color provides best visibility on the default
   OpenStreetMap basemap?
   - Suggested: blue (contrasts with green marker)
   - **Action:** Test blue, dark-blue, purple and choose best option

## 11. Grafana Reference: Route Layer Configuration

Based on Grafana documentation and community examples, Route layer configuration
structure:

```json
{
  "type": "route",
  "name": "Layer Name",
  "config": {
    "style": {
      "color": {
        "field": "fieldname", // for dynamic coloring
        "fixed": "colorname" // for static color (use this)
      },
      "opacity": 0.8, // 0.0 to 1.0
      "lineWidth": 3, // pixels
      "lineCap": "round", // optional
      "lineJoin": "round" // optional
    },
    "showLegend": true // show in layer legend
  },
  "location": {
    "mode": "coords", // use lat/lon coordinates
    "latitude": "lat_field", // field name for latitude
    "longitude": "lon_field" // field name for longitude
  },
  "tooltip": true // enable/disable tooltips
}
```

**Key points:**

- `color.fixed` for single static color
- `color.field` for dynamic coloring based on data (future enhancement)
- `location.mode` must be `"coords"` for lat/lon data
- `latitude` and `longitude` must reference actual field names from
  query/transformation results

---

**Document Version:** 1.0 **Created:** 2025-10-28 **Status:** Ready for
Implementation **Implementation Method:** Pure JSON/YAML configuration (no UI)
**Target File:**
`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` **Related
PRD:** PRD-0007 (Position & Movement dashboard, may be deprecated)
