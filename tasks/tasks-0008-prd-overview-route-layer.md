# Task List: Add Position History Route to Fullscreen Overview Dashboard

**PRD Reference:** `tasks/0008-prd-overview-route-layer.md`

**Implementation Approach:** Pure JSON/YAML configuration (no UI interaction required)

**Target:** Grafana 12.2.1, Geomap panel in `fullscreen-overview.json`

---

## Relevant Files

- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` - Main dashboard JSON file containing the Geomap panel (ID 1) that needs modification to add the route layer
- `CLAUDE.md` - Project documentation that will be updated to describe the new position history route feature
- `.env` - Environment configuration file (reference only - used for testing in simulation/live modes)

### Notes

- This is a configuration-only task - no code files are being created or modified
- All work is done by editing the JSON dashboard configuration directly
- Use `jq` command-line tool to validate JSON syntax after each edit
- Grafana automatically reloads provisioned dashboards when JSON files change
- If auto-reload doesn't work, restart Grafana with `docker compose restart grafana`

---

## Tasks

- [ ] 1.0 Setup and Preparation
  - [ ] 1.1 Navigate to project directory: `cd /path/to/starlink-dashboard-dev` (replace with your actual path)
  - [ ] 1.2 Create a backup of the dashboard JSON file with timestamp: `cp monitoring/grafana/provisioning/dashboards/fullscreen-overview.json monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup-$(date +%Y%m%d-%H%M%S)`
  - [ ] 1.3 Validate the current JSON is properly formatted: `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` (if no output, it's valid; if error, JSON is broken)
  - [ ] 1.4 Extract the Geomap panel (ID 1) to a temporary file for easier viewing: `jq '.panels[] | select(.id == 1)' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/geomap-panel.json`
  - [ ] 1.5 View the current queries in the panel: `jq '.panels[] | select(.id == 1) | .targets' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` (you should see 4 queries: A, B, C, D)
  - [ ] 1.6 View the current layers configuration: `jq '.panels[] | select(.id == 1) | .options.layers' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` (you should see 1 marker layer)
  - [ ] 1.7 Ensure Grafana is running: `docker compose ps grafana` (status should be "Up")
  - [ ] 1.8 Open Grafana in browser at `http://localhost:3000` and navigate to the Fullscreen Overview dashboard to see current state (only current position marker, no route)

- [ ] 2.0 Add Historical Data Queries to Geomap Panel
  - [ ] 2.1 Open `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` in your text editor
  - [ ] 2.2 Find the Geomap panel by searching for `"id": 1` (it's around line 195)
  - [ ] 2.3 Locate the `"targets"` array within this panel (around line 269) - this array currently has 4 queries (refId A, B, C, D)
  - [ ] 2.4 After the last query (refId D, around line 301), add a comma `,` at the end of that query object
  - [ ] 2.5 Add new query E for historical latitude on a new line after query D: `{"expr": "starlink_dish_latitude_degrees", "instant": false, "range": true, "intervalFactor": 1, "legendFormat": "latitude_history", "refId": "E", "interval": "1s"}`
  - [ ] 2.6 Add a comma `,` after query E
  - [ ] 2.7 Add new query F for historical longitude: `{"expr": "starlink_dish_longitude_degrees", "instant": false, "range": true, "intervalFactor": 1, "legendFormat": "longitude_history", "refId": "F", "interval": "1s"}`
  - [ ] 2.8 Ensure proper JSON formatting (queries should be in an array with commas between them, no trailing comma after the last one)
  - [ ] 2.9 Save the file
  - [ ] 2.10 Validate JSON syntax: `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` (fix any errors before proceeding)
  - [ ] 2.11 Wait 5-10 seconds for Grafana to auto-reload, OR manually restart: `docker compose restart grafana`
  - [ ] 2.12 In browser, hard refresh the dashboard (Ctrl+Shift+R or Cmd+Shift+R on Mac)
  - [ ] 2.13 Open the "Current Position" panel in edit mode temporarily (just to inspect, don't save): Click the panel title → Edit
  - [ ] 2.14 Click the "Query inspector" button (icon in top right that looks like a document with magnifying glass)
  - [ ] 2.15 Verify queries E and F appear in the query list and are returning time-series data (not instant values)
  - [ ] 2.16 Close the edit mode without saving (click the "X" or "Back to dashboard")

- [ ] 3.0 Add Route Layer Configuration
  - [ ] 3.1 Open `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` in your text editor again
  - [ ] 3.2 Find the `"layers"` array within the Geomap panel (around line 208)
  - [ ] 3.3 The layers array currently has ONE object (the "Current Position" marker layer starting at line 210)
  - [ ] 3.4 We need to add a NEW layer BEFORE the existing marker layer (remember: first layer = bottom, last layer = top)
  - [ ] 3.5 Add an opening `{` right after the opening `[` of the layers array
  - [ ] 3.6 Copy this route layer configuration and paste it as the FIRST object in the layers array:
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
      },
      "showLegend": false
    },
    "location": {
      "mode": "coords",
      "latitude": "Value #E",
      "longitude": "Value #F"
    },
    "tooltip": false
  }
  ```
  - [ ] 3.7 Add a comma `,` after the closing `}` of the route layer (to separate it from the marker layer)
  - [ ] 3.8 Ensure the existing marker layer (starting with `"type": "markers"`) comes AFTER the route layer in the array
  - [ ] 3.9 The final structure should be: `"layers": [ {route layer config}, {marker layer config} ]`
  - [ ] 3.10 Save the file
  - [ ] 3.11 Validate JSON: `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [ ] 3.12 If validation fails, carefully check: matching braces `{}`, matching brackets `[]`, commas between objects, NO trailing comma after last object
  - [ ] 3.13 Wait for Grafana auto-reload OR restart: `docker compose restart grafana`
  - [ ] 3.14 Hard refresh dashboard in browser (Ctrl+Shift+R)
  - [ ] 3.15 Check if a blue route line appears on the map showing historical movement

- [ ] 4.0 Test and Debug Route Rendering
  - [ ] 4.1 **If route appears:** Great! Skip to 4.8. **If route does NOT appear:** Continue to 4.2
  - [ ] 4.2 Open browser DevTools (F12 or right-click → Inspect) and check Console tab for any Grafana errors (red text)
  - [ ] 4.3 Open the panel in edit mode (just for inspection): Click panel → Edit
  - [ ] 4.4 Click on the "Transform" tab at bottom to see how data is being processed
  - [ ] 4.5 Look at the field names in the transformed data - note the EXACT names for query E and F results (might be "Value #E" and "Value #F" or might be "latitude_history" and "longitude_history")
  - [ ] 4.6 If field names are different from "Value #E" / "Value #F", go back to the JSON file and update the route layer's `"latitude"` and `"longitude"` field names to match exactly
  - [ ] 4.7 Save, validate JSON, restart Grafana, and refresh browser - check if route appears now
  - [ ] 4.8 Verify the current position marker (green plane) is visible on TOP of the route (if not, the layer order is wrong - marker should be LAST in layers array)
  - [ ] 4.9 Test with different time ranges: Click time picker in top right, try "Last 5 minutes", "Last 1 hour", "Last 6 hours" - verify route updates to show different amounts of history
  - [ ] 4.10 Test route appearance: If line is too thick/thin, edit JSON and change `"lineWidth"` value (try 2, 3, or 4)
  - [ ] 4.11 Test route color: If blue isn't visible enough, try "dark-blue", "purple", or "orange" in the `"color": {"fixed": "blue"}` field
  - [ ] 4.12 Ensure simulation mode is active: Check `.env` file has `STARLINK_MODE=simulation`, restart if needed: `docker compose restart backend`
  - [ ] 4.13 Wait 2-3 minutes for simulated movement data to accumulate, then check that route shows a path (not just a single point)
  - [ ] 4.14 Test edge case - very short time range: Set dashboard to "Last 30 seconds" - route should still display (might be very short)
  - [ ] 4.15 Test edge case - very long time range: Set to "Last 6 hours" or "Last 24 hours" - verify route loads without freezing browser
  - [ ] 4.16 Test edge case - no data: Stop backend with `docker compose stop backend`, refresh dashboard, verify it shows "No data" gracefully (not errors), then restart: `docker compose start backend`

- [ ] 5.0 Validate and Document Changes
  - [ ] 5.1 Do final JSON validation: `jq empty monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [ ] 5.2 Pretty-format the JSON (optional but recommended): `jq '.' monitoring/grafana/provisioning/dashboards/fullscreen-overview.json > /tmp/formatted.json && mv /tmp/formatted.json monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [ ] 5.3 Open `CLAUDE.md` in your text editor
  - [ ] 5.4 Find the section titled "## Dashboard Features" (around line 65)
  - [ ] 5.5 After the "Position History Layer" section (or at the end of Dashboard Features), add a new subsection:
  ```markdown
  ### Position History Route (Fullscreen Overview)

  The Fullscreen Overview dashboard's map panel displays both current position and historical route.

  **Features:**
  - Route shows position history over the selected dashboard time range
  - Uses 1-second sampling intervals matching other overview panels
  - Simple blue route line (future: metric-based coloring)
  - Current position marker (green plane) displays on top of route
  - Data gaps interpolated with straight lines

  **Implementation:**
  - Configured in `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - Uses Grafana Geomap Route layer
  - Queries Prometheus for historical lat/lon time series (queries E & F)

  **Known Limitations:**
  - No interactive tooltips in initial version (planned future enhancement)
  - Single solid color (no gradient or metric-based coloring yet)
  - All points connected as continuous route (no segment breaks)
  ```
  - [ ] 5.6 Save `CLAUDE.md`
  - [ ] 5.7 Review the complete checklist of success criteria:
    - [ ] JSON is valid (passes `jq empty` check)
    - [ ] Dashboard loads without errors in Grafana
    - [ ] Route displays correctly over dashboard time range
    - [ ] Current position marker visible on top of route
    - [ ] Route updates when changing dashboard time range
    - [ ] Works in simulation mode
    - [ ] No console errors in browser DevTools
    - [ ] Performance is acceptable (dashboard loads in <5 seconds)
  - [ ] 5.8 If all criteria pass, proceed to commit. If any fail, debug before committing
  - [ ] 5.9 Stage changes for commit: `git add monitoring/grafana/provisioning/dashboards/fullscreen-overview.json CLAUDE.md`
  - [ ] 5.10 Create commit with descriptive message: `git commit -m "Add position history route layer to fullscreen overview dashboard

- Add historical lat/lon range queries (1s interval, refId E & F)
- Configure Grafana Geomap route layer for position history
- Display route with blue line under current position marker
- Route respects dashboard time range selector
- Handle data gaps with linear interpolation"`
  - [ ] 5.11 Verify commit was created: `git log -1` (should show your commit message)
  - [ ] 5.12 Clean up backup file (optional): `rm monitoring/grafana/provisioning/dashboards/fullscreen-overview.json.backup-*`
  - [ ] 5.13 Final test: Restart entire stack to ensure changes persist: `docker compose restart`
  - [ ] 5.14 After restart, open dashboard and verify route still displays correctly

---

**Status:** Complete task list with detailed sub-tasks

**Total Tasks:** 5 parent tasks, 59 sub-tasks

**Estimated Time:** 1-3 hours (including testing and debugging)

**Key Files Modified:**
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- `CLAUDE.md`

**No Code Files Created or Modified** - This is purely a configuration task
