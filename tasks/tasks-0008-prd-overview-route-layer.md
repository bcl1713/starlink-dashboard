# Task List: Add Position History Route to Fullscreen Overview Dashboard

**PRD Reference:** `tasks/0008-prd-overview-route-layer.md`

**Implementation Approach:** Pure JSON/YAML configuration (no UI interaction
required)

**Target:** Grafana 12.2.1, Geomap panel in `fullscreen-overview.json`

---

## Relevant Files

- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` - Main
  dashboard JSON file containing the Geomap panel (ID 1) that needs modification
  to add the route layer
- `CLAUDE.md` - Project documentation that will be updated to describe the new
  position history route feature
- `.env` - Environment configuration file (reference only - used for testing in
  simulation/live modes)

### Notes

- This is a configuration-only task - no code files are being created or
  modified
- All work is done by editing the JSON dashboard configuration directly
- Use `jq` command-line tool to validate JSON syntax after each edit
- Grafana automatically reloads provisioned dashboards when JSON files change
- If auto-reload doesn't work, restart Grafana with
  `docker compose restart grafana`

### Key Technical Approach: Dual Transformation Pipelines

**Problem:** The Geomap panel needs to display both a route (time-series data
from queries E & F) and a current position marker (instant data from queries
A-D). By default, a single transformation joins ALL queries into one dataset,
which prevents the route from rendering correctly.

**Solution:** Create TWO separate transformation pipelines:

1. **Pipeline 1 (Marker):** Filter queries A-D → Join by Time → Output instant
   position data
2. **Pipeline 2 (Route):** Filter queries E-F → Join by Time → Output
   time-series position history

Each layer then references its specific pipeline via the `filterData` field:

- Route layer: `"filterData": {"id": "byRefId", "options": "joinByField-E-F"}`
- Marker layer:
  `"filterData": {"id": "byRefId", "options": "joinByField-A-B-C-D"}`

This ensures each layer gets data in the correct format (instant vs time-series)
without interference from the other queries.

---

## Tasks

- [x] 1.0 Setup and Preparation
  - [x] 1.1 Navigate to project directory: `cd /path/to/starlink-dashboard-dev`
        (replace with your actual path)
  - [x] 1.2 Create a backup of the dashboard JSON file with timestamp:
        `cp monitoring/grafana/provisioning/dashboards/fullscreen-overview.json monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup-$(date +%Y%m%d-%H%M%S)`
  - [x] 1.3 Validate the current JSON is properly formatted:
        `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
        (if no output, it's valid; if error, JSON is broken)
  - [x] 1.4 Extract the Geomap panel (ID 1) to a temporary file for easier
        viewing:
        `jq '.panels[] | select(.id == 1)' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/geomap-panel.json`
  - [x] 1.5 View the current queries in the panel:
        `jq '.panels[] | select(.id == 1) | .targets' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
        (you should see 4 queries: A, B, C, D)
  - [x] 1.6 View the current layers configuration:
        `jq '.panels[] | select(.id == 1) | .options.layers' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
        (you should see 1 marker layer)
  - [x] 1.7 Ensure Grafana is running: `docker compose ps grafana` (status
        should be "Up")
  - [x] 1.8 Open Grafana in browser at `http://localhost:3000` and navigate to
        the Fullscreen Overview dashboard to see current state (only current
        position marker, no route)

- [x] 2.0 Add Historical Data Queries to Geomap Panel
  - [x] 2.1 Open
        `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` in
        your text editor
  - [x] 2.2 Find the Geomap panel by searching for `"id": 1` (it's around
        line 195)
  - [x] 2.3 Locate the `"targets"` array within this panel (around line 269) -
        this array currently has 4 queries (refId A, B, C, D)
  - [x] 2.4 After the last query (refId D, around line 301), add a comma `,` at
        the end of that query object
  - [x] 2.5 Add new query E for historical latitude on a new line after query D:
        `{"expr": "starlink_dish_latitude_degrees", "instant": false, "range": true, "intervalFactor": 1, "legendFormat": "latitude_history", "refId": "E", "interval": "1s"}`
  - [x] 2.6 Add a comma `,` after query E
  - [x] 2.7 Add new query F for historical longitude:
        `{"expr": "starlink_dish_longitude_degrees", "instant": false, "range": true, "intervalFactor": 1, "legendFormat": "longitude_history", "refId": "F", "interval": "1s"}`
  - [x] 2.8 Ensure proper JSON formatting (queries should be in an array with
        commas between them, no trailing comma after the last one)
  - [x] 2.9 Save the file
  - [x] 2.10 Validate JSON syntax:
        `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
        (fix any errors before proceeding)
  - [x] 2.11 Wait 5-10 seconds for Grafana to auto-reload, OR manually restart:
        `docker compose restart grafana`
  - [x] 2.12 In browser, hard refresh the dashboard (Ctrl+Shift+R or Cmd+Shift+R
        on Mac)
  - [x] 2.13 Open the "Current Position" panel in edit mode temporarily (just to
        inspect, don't save): Click the panel title → Edit
  - [x] 2.14 Click the "Query inspector" button (icon in top right that looks
        like a document with magnifying glass)
  - [x] 2.15 Verify queries E and F appear in the query list and are returning
        time-series data (not instant values)
  - [x] 2.16 Close the edit mode without saving (click the "X" or "Back to
        dashboard")

- [x] 3.0 Update Transformations to Separate Data Streams
  - [x] 3.1 Open
        `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` in
        your text editor again
  - [x] 3.2 Find the `"transformations"` array within the Geomap panel (around
        line 342)
  - [x] 3.3 The transformations array currently has ONE transformation object
        (joinByField with mode: outer)
  - [x] 3.4 **Replace the entire transformations array** with this new structure
        that creates two separate data pipelines:

  ```json
  "transformations": [
    {
      "filter": {
        "id": "byRefId",
        "options": "/^(?:A|B|C|D)$/"
      },
      "id": "joinByField",
      "options": {
        "byField": "Time",
        "mode": "inner"
      }
    },
    {
      "filter": {
        "id": "byRefId",
        "options": "/^(?:E|F)$/"
      },
      "id": "joinByField",
      "options": {
        "mode": "inner"
      }
    }
  ]
  ```

  - [x] 3.5 **Explanation:** This creates TWO separate joinByField
        transformations: - First transformation: Filters to queries A-D (instant
        values) and joins them by Time field for the marker layer - Second
        transformation: Filters to queries E-F (time-series values) and joins
        them for the route layer - The regex patterns `/^(?:A|B|C|D)$/` and
        `/^(?:E|F)$/` match the query refIds

- [x] 3.6 Add Route Layer Configuration
  - [x] 3.6.1 Find the `"layers"` array within the Geomap panel (around
        line 208)
  - [x] 3.6.2 The layers array currently has ONE object (the "Current Position"
        marker layer starting at line 210)
  - [x] 3.6.3 We need to add a NEW layer BEFORE the existing marker layer
        (remember: first layer = bottom, last layer = top)
  - [x] 3.6.4 Copy this route layer configuration and paste it as the FIRST
        object in the layers array:

  ```json
  {
    "type": "route",
    "name": "Position History",
    "config": {
      "style": {
        "color": {
          "fixed": "blue"
        },
        "opacity": 0.7,
        "lineWidth": 3
      },
      "showLegend": false
    },
    "filterByRefId": "E",
    "filterData": {
      "id": "byRefId",
      "options": "joinByField-E-F"
    },
    "location": {
      "mode": "coords",
      "latitude": "latitude_history",
      "longitude": "longitude_history"
    },
    "tooltip": false
  }
  ```

  - [x] 3.6.5 **Key fields explained:** - `"filterByRefId": "E"` - Tells the
        layer to use query E as the primary reference - `"filterData"` - Points
        to the second transformation pipeline (joinByField for E-F queries) -
        The `"options": "joinByField-E-F"` value references the transformation
        that filtered queries E & F

  - [x] 3.6.6 Add a comma `,` after the closing `}` of the route layer (to
        separate it from the marker layer)

- [x] 3.7 Update Marker Layer Configuration
  - [x] 3.7.1 Find the existing marker layer object (should come after the route
        layer in the layers array)
  - [x] 3.7.2 Add `"filterByRefId": "A"` inside the `"config"` object of the
        marker layer (not at the root level of the layer)
  - [x] 3.7.3 Add a `"filterData"` field at the root level of the marker layer
        (same level as "type", "name", "config"):

  ```json
  "filterData": {
    "id": "byRefId",
    "options": "joinByField-A-B-C-D"
  }
  ```

  - [x] 3.7.4 **Important:** The marker layer's `filterData` points to the first
        transformation (queries A-D), while the route layer's `filterData`
        points to the second transformation (queries E-F). This ensures each
        layer gets data from its own transformation pipeline.

  - [x] 3.7.5 The final marker layer should have both `filterByRefId` in config
        AND `filterData` at the root level

  - [x] 3.7.6 Save the file
  - [x] 3.7.7 Validate JSON:
        `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [x] 3.7.8 If validation fails, carefully check: matching braces `{}`,
        matching brackets `[]`, commas between objects, NO trailing comma after
        last object
  - [x] 3.7.9 Wait for Grafana auto-reload OR restart:
        `docker compose restart grafana`
  - [x] 3.7.10 Hard refresh dashboard in browser (Ctrl+Shift+R)
  - [x] 3.7.11 Check if a blue route line appears on the map showing historical
        movement

- [x] 4.0 Test and Debug Route Rendering
  - [x] 4.1 **If route appears:** Great! Skip to 4.10. **If route does NOT
        appear:** Continue to 4.2
  - [x] 4.2 Open browser DevTools (F12 or right-click → Inspect) and check
        Console tab for any Grafana errors (red text)
  - [x] 4.3 Open the panel in edit mode (just for inspection): Click panel →
        Edit
  - [x] 4.4 Click on the "Transform" tab at bottom to see how data is being
        processed
  - [x] 4.5 Verify you see TWO transformation pipelines: - First: "joinByField"
        with filter for queries A, B, C, D - Second: "joinByField" with filter
        for queries E, F
  - [x] 4.6 Switch to "Table view" at top right of the edit panel
  - [x] 4.7 You should see TWO separate data tables: - One with columns: Time,
        latitude, longitude, altitude, heading (from queries A-D, single instant
        values) - One with columns: Time, latitude_history, longitude_history
        (from queries E-F, multiple time-series rows)
  - [x] 4.8 If you only see one joined table with ALL fields, the
        transformations didn't work correctly - double-check the transformation
        JSON structure
  - [x] 4.9 If the route layer shows "No data" or errors, check that: - TWO
        separate transformations exist in the transformations array - Route
        layer has
        `filterData: {id: "byRefId", options:       "joinByField-E-F"}` - Marker
        layer has
        `filterData: {id: "byRefId", options:       "joinByField-A-B-C-D"}` -
        Field names in route layer location match: "latitude_history" and
        "longitude_history"
  - [x] 4.10 Verify the current position marker (green plane) is visible on TOP
        of the route (if not, the layer order is wrong - marker should be LAST
        in layers array)
  - [x] 4.11 Test with different time ranges: Click time picker in top right,
        try "Last 5 minutes", "Last 1 hour", "Last 6 hours" - verify route
        updates to show different amounts of history
  - [x] 4.12 Test route appearance: If line is too thick/thin, edit JSON and
        change `"lineWidth"` value (try 2, 3, or 4)
  - [x] 4.13 Test route color: If blue isn't visible enough, try "dark-blue",
        "purple", or "orange" in the `"color": {"fixed": "blue"}` field
  - [x] 4.14 Ensure simulation mode is active: Check `.env` file has
        `STARLINK_MODE=simulation`, restart if needed:
        `docker compose restart backend`
  - [x] 4.15 Wait 2-3 minutes for simulated movement data to accumulate, then
        check that route shows a path (not just a single point)
  - [x] 4.16 Test edge case - very short time range: Set dashboard to "Last 30
        seconds" - route should still display (might be very short)
  - [x] 4.17 Test edge case - very long time range: Set to "Last 6 hours" or
        "Last 24 hours" - verify route loads without freezing browser
  - [x] 4.18 Test edge case - no data: Stop backend with
        `docker compose stop backend`, refresh dashboard, verify it shows "No
        data" gracefully (not errors), then restart:
        `docker compose start backend`

- [x] 5.0 Validate and Document Changes
  - [x] 5.1 Do final JSON validation:
        `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [x] 5.2 Pretty-format the JSON (optional but recommended):
        `jq '.' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/formatted.json && mv /tmp/formatted.json monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [x] 5.3 Open `CLAUDE.md` in your text editor
  - [x] 5.4 Find the section titled "## Dashboard Features" (around line 65)
  - [x] 5.5 After the "Position History Layer" section (or at the end of
        Dashboard Features), add a new subsection:

  ```markdown
  ### Position History Route (Fullscreen Overview)

  The Fullscreen Overview dashboard's map panel displays both current position
  and historical route.

  **Features:**

  - Route shows position history over the selected dashboard time range
  - Uses 1-second sampling intervals matching other overview panels
  - Simple blue route line (future: metric-based coloring)
  - Current position marker (green plane) displays on top of route
  - Data gaps interpolated with straight lines

  **Implementation:**

  - Configured in
    `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - Uses Grafana Geomap Route layer
  - Queries Prometheus for historical lat/lon time series (queries E & F)

  **Known Limitations:**

  - No interactive tooltips in initial version (planned future enhancement)
  - Single solid color (no gradient or metric-based coloring yet)
  - All points connected as continuous route (no segment breaks)
  ```

  - [x] 5.6 Save `CLAUDE.md`
  - [x] 5.7 Review the complete checklist of success criteria:
    - [x] JSON is valid (passes `jq empty` check)
    - [x] Dashboard loads without errors in Grafana
    - [x] Route displays correctly over dashboard time range
    - [x] Current position marker visible on top of route
    - [x] Route updates when changing dashboard time range
    - [x] Works in simulation mode
    - [x] No console errors in browser DevTools
    - [x] Performance is acceptable (dashboard loads in <5 seconds)
  - [x] 5.8 If all criteria pass, proceed to commit. If any fail, debug before
        committing
  - [x] 5.9 Stage changes for commit:
        `git add monitoring/grafana/provisioning/dashboards/fullscreen-overview.json CLAUDE.md`
  - [x] 5.10 Create commit with descriptive message: `git commit -m "Add
        position history route layer to fullscreen overview dashboard

- Add historical lat/lon range queries (1s interval, refId E & F)
- Configure Grafana Geomap route layer for position history
- Display route with blue line under current position marker
- Route respects dashboard time range selector
- Handle data gaps with linear interpolation"`
  - [x] 5.11 Verify commit was created: `git log -1` (should show your commit
        message)
  - [x] 5.12 Clean up backup file (optional):
        `rm monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup-*`
  - [x] 5.13 Final test: Restart entire stack to ensure changes persist:
        `docker compose restart`
  - [x] 5.14 After restart, open dashboard and verify route still displays
        correctly

---

**Status:** Complete task list with detailed sub-tasks

**Total Tasks:** 5 parent tasks, 59 sub-tasks

**Estimated Time:** 1-3 hours (including testing and debugging)

**Key Files Modified:**

- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- `CLAUDE.md`

**No Code Files Created or Modified** - This is purely a configuration task
