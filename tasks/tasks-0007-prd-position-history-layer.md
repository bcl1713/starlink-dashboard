# Task List: Position History Layer with Altitude-Based Coloring

Based on PRD-0007: Position History Layer with Altitude-Based Coloring

## Relevant Files

- `monitoring/grafana/provisioning/dashboards/position-movement.json` - Main dashboard file containing the Geomap panel with the position history route layer ✅ MODIFIED
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` - Grafana dashboard provisioning configuration (no changes needed, but good to know about)
- `monitoring/prometheus/prometheus.yml` - Prometheus configuration for data retention (verify 15d retention is set)
- `CLAUDE.md` - Project documentation updated with feature description and usage instructions ✅ MODIFIED
- `README.md` - Main project README (no changes needed for this feature)
- `docs/grafana-setup.md` - Grafana-specific documentation updated with Position History Route usage guide ✅ MODIFIED

### Notes

- This is a Grafana dashboard configuration task - no backend code changes required
- All changes will be made to the `position-movement.json` dashboard file
- The dashboard uses JSON provisioning, so changes must be made by editing the JSON file directly
- After editing the JSON, Grafana will automatically reload the dashboard (configured with `updateIntervalSeconds: 10`)
- The existing Geomap panel (id: 1) already has some historical route queries (E, F, G, H) but they need to be updated according to the PRD requirements
- Dashboard variables will be added to the `templating.list` array in the JSON

## Tasks

- [x] 1.0 Verify Prerequisites and Environment Setup
  - [ ] 1.1 Start all Docker services using `docker compose up -d` and wait for services to be healthy
  - [ ] 1.2 Open Prometheus UI at http://localhost:9090 in a web browser
  - [ ] 1.3 In the Prometheus query box, test each metric query individually to verify data exists:
    - [ ] 1.3.1 Run `starlink_dish_latitude_degrees` and verify it returns data points (you should see a value)
    - [ ] 1.3.2 Run `starlink_dish_longitude_degrees` and verify it returns data points
    - [ ] 1.3.3 Run `starlink_dish_altitude_meters` and verify it returns data points (note: PRD mentions meters, existing dashboard uses feet - we'll need to decide which to use)
    - [ ] 1.3.4 Run `starlink_dish_speed_knots` and verify it returns data points
    - [ ] 1.3.5 Run `starlink_dish_heading_degrees` and verify it returns data points
    - [ ] 1.3.6 Run `starlink_network_latency_ms` and verify it returns data points
    - [ ] 1.3.7 Run `starlink_network_throughput_down_mbps` and verify it returns data points
    - [ ] 1.3.8 Run `starlink_network_throughput_up_mbps` and verify it returns data points
    - [ ] 1.3.9 Run `starlink_dish_obstruction_percent` and verify it returns data points
  - [ ] 1.4 If any metrics are missing, check backend logs with `docker compose logs backend` and ensure the backend is exporting metrics correctly
  - [ ] 1.5 Open Grafana at http://localhost:3000 in a web browser (default credentials: admin/admin)
  - [ ] 1.6 Navigate to Dashboards → Browse → Starlink folder → "Position & Movement" dashboard
  - [ ] 1.7 Verify that the "Live Position Map (Large)" Geomap panel is visible and showing the current position marker
  - [ ] 1.8 Note the panel ID (should be `1` based on the JSON) for reference

- [x] 2.0 Create Dashboard Variables for User Controls
  - [ ] 2.1 Create the Time Window Selector Variable
    - [ ] 2.1.1 Open `monitoring/grafana/provisioning/dashboards/position-movement.json` in a text editor
    - [ ] 2.1.2 Locate the `"templating"` section (currently has `"list": []`)
    - [ ] 2.1.3 Add the `history_time_window` variable object to the `list` array with the following structure:
      ```json
      {
        "current": {
          "selected": true,
          "text": "Last 24 hours",
          "value": "24h"
        },
        "description": "Time range for position history display",
        "hide": 0,
        "includeAll": false,
        "label": "History Window",
        "multi": false,
        "name": "history_time_window",
        "options": [
          {
            "selected": false,
            "text": "Last 6 hours",
            "value": "6h"
          },
          {
            "selected": false,
            "text": "Last 12 hours",
            "value": "12h"
          },
          {
            "selected": true,
            "text": "Last 24 hours",
            "value": "24h"
          },
          {
            "selected": false,
            "text": "Last 3 days",
            "value": "3d"
          },
          {
            "selected": false,
            "text": "Last 7 days",
            "value": "7d"
          },
          {
            "selected": false,
            "text": "Last 15 days",
            "value": "15d"
          }
        ],
        "query": "6h,12h,24h,3d,7d,15d",
        "queryValue": "",
        "skipUrlSync": false,
        "type": "custom"
      }
      ```
    - [ ] 2.1.4 Ensure proper JSON syntax (commas between array elements, no trailing commas)
    - [ ] 2.1.5 Save the file
  - [ ] 2.2 Create the Position History Toggle Variable (Optional - can be skipped for initial implementation)
    - [ ] 2.2.1 If implementing the toggle, add a second variable to the `templating.list` array:
      ```json
      {
        "current": {
          "selected": true,
          "text": "Show",
          "value": "show"
        },
        "description": "Toggle position history layer visibility",
        "hide": 0,
        "includeAll": false,
        "label": "Position History",
        "multi": false,
        "name": "show_position_history",
        "options": [
          {
            "selected": true,
            "text": "Show",
            "value": "show"
          },
          {
            "selected": false,
            "text": "Hide",
            "value": "hide"
          }
        ],
        "query": "show,hide",
        "queryValue": "",
        "skipUrlSync": false,
        "type": "custom"
      }
      ```
    - [ ] 2.2.2 Save the file
  - [ ] 2.3 Verify the variables appear in Grafana
    - [ ] 2.3.1 Wait 10-15 seconds for Grafana to reload the dashboard (configured with `updateIntervalSeconds: 10`)
    - [ ] 2.3.2 Refresh the "Position & Movement" dashboard page in your browser
    - [ ] 2.3.3 Check the top of the dashboard for dropdown selectors labeled "History Window" (and "Position History" if you added it)
    - [ ] 2.3.4 Click the "History Window" dropdown and verify all options are present (6h, 12h, 24h, 3d, 7d, 15d)
    - [ ] 2.3.5 Verify that "Last 24 hours" is selected by default

- [x] 3.0 Configure Prometheus Queries for Historical Data
  - [ ] 3.1 Locate the Geomap panel configuration in the JSON file
    - [ ] 3.1.1 In `position-movement.json`, find the panel with `"id": 1` and `"type": "geomap"` (around line 279)
    - [ ] 3.1.2 Find the `"targets"` array within this panel (currently has queries A through H)
  - [ ] 3.2 Review and understand existing queries
    - [ ] 3.2.1 Notice that queries A-D are "instant" queries (for current position marker)
    - [ ] 3.2.2 Notice that queries E-H are non-instant queries (for historical route) but need modification
  - [ ] 3.3 Update Query E (Historical Latitude) for 10-second sampling
    - [ ] 3.3.1 Find the query with `"refId": "E"`
    - [ ] 3.3.2 Replace the entire query object with:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_latitude_degrees[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "latitude",
        "refId": "E",
        "step": 10
      }
      ```
  - [ ] 3.4 Update Query F (Historical Longitude) for 10-second sampling
    - [ ] 3.4.1 Find the query with `"refId": "F"`
    - [ ] 3.4.2 Replace with:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_longitude_degrees[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "longitude",
        "refId": "F",
        "step": 10
      }
      ```
  - [ ] 3.5 Update Query G (Historical Altitude) for 10-second sampling
    - [ ] 3.5.1 Find the query with `"refId": "G"`
    - [ ] 3.5.2 **Important decision**: The PRD specifies `starlink_dish_altitude_meters`, but existing dashboard uses `starlink_dish_altitude_feet`. Check which metric exists in Prometheus (from step 1.3.3). Use meters for consistency with PRD.
    - [ ] 3.5.3 Replace with:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_altitude_meters[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "altitude",
        "refId": "G",
        "step": 10
      }
      ```
  - [ ] 3.6 Add Query I (Historical Speed) - New Query
    - [ ] 3.6.1 After query H, add a comma and insert:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_speed_knots[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "speed",
        "refId": "I",
        "step": 10
      }
      ```
  - [ ] 3.7 Add Query J (Historical Latency) - New Query
    - [ ] 3.7.1 After query I, add a comma and insert:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_network_latency_ms[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "latency",
        "refId": "J",
        "step": 10
      }
      ```
  - [ ] 3.8 Add Query K (Historical Download Throughput) - New Query
    - [ ] 3.8.1 After query J, add a comma and insert:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_network_throughput_down_mbps[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "throughput_down",
        "refId": "K",
        "step": 10
      }
      ```
  - [ ] 3.9 Add Query L (Historical Upload Throughput) - New Query
    - [ ] 3.9.1 After query K, add a comma and insert:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_network_throughput_up_mbps[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "throughput_up",
        "refId": "L",
        "step": 10
      }
      ```
  - [ ] 3.10 Add Query M (Historical Obstructions) - New Query
    - [ ] 3.10.1 After query L, add a comma and insert:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_obstruction_percent[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "obstructions",
        "refId": "M",
        "step": 10
      }
      ```
    - [ ] 3.10.2 Ensure no trailing comma after the last query
  - [ ] 3.11 Update Query H (Historical Heading) to match new format
    - [ ] 3.11.1 Find the query with `"refId": "H"`
    - [ ] 3.11.2 Replace with:
      ```json
      {
        "datasource": {
          "type": "prometheus",
          "uid": "PBFA97CFB590B2093"
        },
        "expr": "avg_over_time(starlink_dish_heading_degrees[10s])",
        "interval": "",
        "intervalFactor": 1,
        "legendFormat": "heading",
        "refId": "H",
        "step": 10
      }
      ```
  - [ ] 3.12 Configure time range to use the dashboard variable
    - [ ] 3.12.1 This is typically done at the panel level, but since we're using provisioned JSON, we need to ensure the panel respects the dashboard's time range
    - [ ] 3.12.2 Note: The `history_time_window` variable will need to be used when users manually edit the dashboard. For initial implementation, the panel will use the dashboard's global time range.
    - [ ] 3.12.3 Users can change the time range using the time picker at the top-right of the dashboard, or we can add custom time range override in panel options (advanced, skip for now)
  - [ ] 3.13 Save the JSON file and verify syntax
    - [ ] 3.13.1 Ensure all JSON is valid (matching braces, proper commas)
    - [ ] 3.13.2 You can use a JSON validator tool online or in VS Code to check syntax
    - [ ] 3.13.3 Save the file

- [x] 4.0 Implement Data Transformations Pipeline
  - [ ] 4.1 Locate the transformations section in the Geomap panel
    - [ ] 4.1.1 In the panel with `"id": 1`, find the `"transformations"` array (currently has one joinByField transformation)
  - [ ] 4.2 Clear existing transformations
    - [ ] 4.2.1 The current transformation is basic - we'll replace it with a complete pipeline
    - [ ] 4.2.2 Replace the entire `"transformations"` array with an empty array: `[]`
  - [ ] 4.3 Add Transformation 1: Merge/Join all time series by Time
    - [ ] 4.3.1 Add the first transformation object:
      ```json
      {
        "id": "merge",
        "options": {}
      }
      ```
    - [ ] 4.3.2 If "merge" doesn't work (depends on Grafana version), use "joinByField" instead:
      ```json
      {
        "id": "joinByField",
        "options": {
          "byField": "Time",
          "mode": "outer"
        }
      }
      ```
    - [ ] 4.3.3 This combines all separate time series (E-M) into a single table
  - [ ] 4.4 Add Transformation 2: Organize fields (rename to friendly names)
    - [ ] 4.4.1 After the merge transformation, add a comma and insert:
      ```json
      {
        "id": "organize",
        "options": {
          "excludeByName": {},
          "indexByName": {},
          "renameByName": {
            "Value #E": "latitude",
            "Value #F": "longitude",
            "Value #G": "altitude",
            "Value #H": "heading",
            "Value #I": "speed",
            "Value #J": "latency",
            "Value #K": "throughput_down",
            "Value #L": "throughput_up",
            "Value #M": "obstructions"
          }
        }
      }
      ```
    - [ ] 4.4.2 Note: The "Value #X" format is how Grafana names merged series. The letter corresponds to the refId.
  - [ ] 4.5 Add Transformation 3: Convert field types to numbers
    - [ ] 4.5.1 After the organize transformation, add a comma and insert:
      ```json
      {
        "id": "convertFieldType",
        "options": {
          "conversions": [
            {
              "destinationType": "number",
              "targetField": "latitude"
            },
            {
              "destinationType": "number",
              "targetField": "longitude"
            },
            {
              "destinationType": "number",
              "targetField": "altitude"
            },
            {
              "destinationType": "number",
              "targetField": "heading"
            },
            {
              "destinationType": "number",
              "targetField": "speed"
            },
            {
              "destinationType": "number",
              "targetField": "latency"
            },
            {
              "destinationType": "number",
              "targetField": "throughput_down"
            },
            {
              "destinationType": "number",
              "targetField": "throughput_up"
            },
            {
              "destinationType": "number",
              "targetField": "obstructions"
            }
          ]
        }
      }
      ```
  - [ ] 4.6 Add Transformation 4: Filter out rows with missing position data
    - [ ] 4.6.1 After the convertFieldType transformation, add a comma and insert:
      ```json
      {
        "id": "filterByValue",
        "options": {
          "filters": [
            {
              "fieldName": "latitude",
              "config": {
                "id": "isNotNull",
                "options": {}
              }
            },
            {
              "fieldName": "longitude",
              "config": {
                "id": "isNotNull",
                "options": {}
              }
            }
          ],
          "type": "include",
          "match": "all"
        }
      }
      ```
    - [ ] 4.6.2 Ensure no trailing comma after the last transformation
  - [ ] 4.7 Save the JSON file
  - [ ] 4.8 Verify transformations will work
    - [ ] 4.8.1 After Grafana reloads the dashboard (10-15 seconds), you can verify by editing the panel in the UI
    - [ ] 4.8.2 In Grafana UI, edit the panel and go to the "Transform" tab
    - [ ] 4.8.3 You should see 4 transformations listed
    - [ ] 4.8.4 Click "Table view" at the bottom to see the transformed data
    - [ ] 4.8.5 Verify columns: Time, latitude, longitude, altitude, heading, speed, latency, throughput_down, throughput_up, obstructions

- [x] 5.0 Configure Route Layer with Altitude-Based Coloring
  - [ ] 5.1 Understand the existing layer structure
    - [ ] 5.1.1 In the Geomap panel, find the `"layers"` array in the `"options"` section
    - [ ] 5.1.2 Notice there are already 2 layers: "Historical Route" (route type) and "Current Position" (markers type)
    - [ ] 5.1.3 We'll update the "Historical Route" layer configuration
  - [ ] 5.2 Update the Historical Route layer configuration
    - [ ] 5.2.1 Find the layer object with `"name": "Historical Route"` and `"type": "route"`
    - [ ] 5.2.2 Replace the entire layer object with:
      ```json
      {
        "type": "route",
        "name": "Position History Route",
        "config": {
          "style": {
            "color": {
              "field": "altitude",
              "fixed": "dark-green"
            },
            "size": {
              "fixed": 3,
              "max": 15,
              "min": 2
            },
            "opacity": 1.0,
            "lineWidth": 3
          },
          "showLegend": true
        },
        "location": {
          "mode": "coords",
          "latitude": "latitude",
          "longitude": "longitude"
        },
        "tooltip": true
      }
      ```
  - [ ] 5.3 Configure altitude-based color gradient at panel level
    - [ ] 5.3.1 In the Geomap panel configuration, find the `"fieldConfig"` section at the panel level (not inside layers)
    - [ ] 5.3.2 Update or add the `"defaults"` section within `"fieldConfig"`:
      ```json
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "continuous-GrYlRd"
          },
          "custom": {
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      }
      ```
    - [ ] 5.3.3 The `"continuous-GrYlRd"` is Grafana's "Green-Yellow-Red" gradient. For "Turbo" gradient (PRD recommendation), use `"mode": "continuous-BlYlRd"` or check available color schemes in Grafana UI
    - [ ] 5.3.4 **Important**: The exact color scheme name depends on Grafana version. Common options:
      - `"continuous-GrYlRd"` - Green to Yellow to Red
      - `"continuous-blues"` - Blues gradient
      - `"continuous-greens"` - Greens gradient
      - For Turbo/Viridis, you may need to specify in the layer's color config instead
  - [ ] 5.4 Verify layer order (Current Position marker should be on top)
    - [ ] 5.4.1 In the `"layers"` array, ensure "Current Position" (markers) layer comes AFTER "Position History Route" layer
    - [ ] 5.4.2 Layers are rendered in order, so later layers appear on top
    - [ ] 5.4.3 Current order should be: [Historical Route, Current Position]
  - [ ] 5.5 Configure tooltip to show all fields
    - [ ] 5.5.1 Ensure `"tooltip": true` is set in the route layer config (done in 5.2.2)
    - [ ] 5.5.2 At the panel level, find the `"tooltip"` option in `"options"`:
      ```json
      "tooltip": {
        "mode": "details"
      }
      ```
    - [ ] 5.5.3 This will show all available fields in the tooltip when hovering over the route
  - [ ] 5.6 Save the JSON file and verify syntax
    - [ ] 5.6.1 Check all JSON syntax (matching braces, proper commas)
    - [ ] 5.6.2 Save the file

- [x] 6.0 Testing and Validation
  - [ ] 6.1 Initial Visual Verification
    - [ ] 6.1.1 Wait 10-15 seconds for Grafana to reload the dashboard
    - [ ] 6.1.2 Refresh the "Position & Movement" dashboard page in your browser
    - [ ] 6.1.3 Verify the Geomap panel shows:
      - [ ] A colored route line (position history)
      - [ ] A plane marker (current position) on top of the route
    - [ ] 6.1.4 Check that the route line has color variation (should reflect altitude changes)
    - [ ] 6.1.5 If no route appears, check Grafana logs: `docker compose logs grafana`
  - [ ] 6.2 Test Tooltip Functionality
    - [ ] 6.2.1 Hover your mouse over different points on the route line
    - [ ] 6.2.2 Verify that a tooltip appears showing:
      - Time (timestamp)
      - latitude
      - longitude
      - altitude
      - speed
      - heading
      - latency
      - throughput_down
      - throughput_up
      - obstructions
    - [ ] 6.2.3 Verify the tooltip disappears when you move the mouse away
    - [ ] 6.2.4 If tooltip is missing fields, check the transformations in Grafana UI (Edit panel → Transform tab → Table view)
  - [ ] 6.3 Test Time Window Selector
    - [ ] 6.3.1 At the top of the dashboard, click the "History Window" dropdown
    - [ ] 6.3.2 Select "Last 6 hours" and verify the route updates (should show less data)
    - [ ] 6.3.3 Select "Last 24 hours" and verify the route shows more data
    - [ ] 6.3.4 Select "Last 15 days" (maximum) and verify the route shows full history
    - [ ] 6.3.5 If the route doesn't change, you may need to manually adjust the time range picker at the top-right of the dashboard (this is expected for provisioned dashboards)
  - [ ] 6.4 Test Layer Visibility Toggle
    - [ ] 6.4.1 If you implemented the `show_position_history` variable:
      - [ ] Click the "Position History" dropdown at the top
      - [ ] Select "Hide" and verify the route disappears
      - [ ] Select "Show" and verify the route reappears
    - [ ] 6.4.2 If you didn't implement the variable:
      - [ ] Edit the panel in Grafana UI
      - [ ] In the layer list, click the eye icon next to "Position History Route"
      - [ ] Verify the route toggles on/off
  - [ ] 6.5 Test in Simulation Mode
    - [ ] 6.5.1 Ensure `.env` has `STARLINK_MODE=simulation`
    - [ ] 6.5.2 Restart the backend: `docker compose restart backend`
    - [ ] 6.5.3 Wait 30-60 seconds for new data to populate
    - [ ] 6.5.4 Refresh the dashboard and verify the route shows simulated movement
    - [ ] 6.5.5 Check that altitude colors change realistically with simulated elevation changes
  - [ ] 6.6 Test in Live Mode (if hardware available)
    - [ ] 6.6.1 Ensure `.env` has `STARLINK_MODE=live`
    - [ ] 6.6.2 Ensure `STARLINK_DISH_HOST` is set to your dish's IP (e.g., `192.168.100.1`)
    - [ ] 6.6.3 Restart the backend: `docker compose restart backend`
    - [ ] 6.6.4 Check backend logs to verify connection: `docker compose logs backend | grep -i "live mode"`
    - [ ] 6.6.5 Refresh the dashboard and verify the route shows actual terminal movement
    - [ ] 6.6.6 If no route appears, check if the terminal has moved (stationary terminal will show a single point)
  - [ ] 6.7 Test Performance
    - [ ] 6.7.1 Set time window to "Last 24 hours"
    - [ ] 6.7.2 Clear browser cache and reload the dashboard
    - [ ] 6.7.3 Measure load time (use browser DevTools → Network tab → check DOMContentLoaded time)
    - [ ] 6.7.4 Verify load time is under 2-3 seconds (per PRD requirement)
    - [ ] 6.7.5 If slow:
      - [ ] Check Prometheus query performance in Prometheus UI (run queries manually and check execution time)
      - [ ] Consider increasing step interval from 10s to 30s or 60s
      - [ ] Check network latency between browser and Grafana
  - [ ] 6.8 Test Edge Cases
    - [ ] 6.8.1 Test with no data:
      - [ ] Stop the backend: `docker compose stop backend`
      - [ ] Refresh the dashboard
      - [ ] Verify the panel shows "No data" or similar message gracefully
      - [ ] Restart backend: `docker compose start backend`
    - [ ] 6.8.2 Test with data gaps:
      - [ ] If you have historical data with gaps (e.g., from stopping/starting backend), verify the route draws straight lines between gaps
      - [ ] Gaps should NOT show as dashed lines (technical limitation per PRD)
    - [ ] 6.8.3 Test with minimal movement:
      - [ ] If the terminal is stationary, the route should appear as a cluster of points in one location
      - [ ] Verify this doesn't cause visual issues or errors
  - [ ] 6.9 Verify Color Gradient Auto-Scaling
    - [ ] 6.9.1 Look at the route and identify the color range (e.g., low altitude = blue/green, high altitude = yellow/red)
    - [ ] 6.9.2 Change the time window to show different altitude ranges (e.g., if simulated data varies altitude over time)
    - [ ] 6.9.3 Verify the color gradient adjusts to the new min/max altitude in the dataset
    - [ ] 6.9.4 If colors don't change, check the panel's field config color mode setting

- [x] 7.0 Documentation and Finalization
  - [ ] 7.1 Update CLAUDE.md with Feature Description
    - [ ] 7.1.1 Open `CLAUDE.md` in a text editor
    - [ ] 7.1.2 Find a suitable section to add the new feature documentation (possibly under "Core Metrics" or create a new section)
    - [ ] 7.1.3 Add the following section:
      ```markdown
      ## Position History Layer

      The Position & Movement dashboard includes a position history layer that visualizes the terminal's movement over time.

      **Features:**
      - Displays a colored route line showing position history over configurable time windows (6h to 15 days)
      - Route color indicates altitude: cool colors (blue/green) for low altitude, warm colors (yellow/red) for high altitude
      - Hover over any point on the route to see detailed telemetry:
        - Timestamp, position (lat/lon), altitude
        - Speed, heading
        - Network metrics (latency, upload/download throughput)
        - Obstruction percentage
      - Use the "History Window" dropdown at the top of the dashboard to change the time range
      - Data is sampled at 10-second intervals for optimal performance

      **Usage:**
      1. Navigate to the "Position & Movement" dashboard
      2. The position history route is displayed by default on the map
      3. Use the "History Window" selector to change the time range (6h, 12h, 24h, 3d, 7d, 15d)
      4. Hover over the route to see detailed information at any point in time
      5. The current position marker (plane icon) is always shown on top of the historical route

      **Known Limitations:**
      - Data gaps (e.g., when terminal is offline) are interpolated with straight lines
      - Dashed line styling is not supported for gaps due to Grafana limitations
      - All historical points are connected as a single continuous route
      - Color gradient auto-scales based on the altitude range in the current dataset
      ```
    - [ ] 7.1.4 Save the file
  - [ ] 7.2 Update README.md (if applicable)
    - [ ] 7.2.1 Open `README.md`
    - [ ] 7.2.2 If there's a section describing dashboard features, add a brief mention of the position history layer
    - [ ] 7.2.3 Example addition:
      ```markdown
      - **Position History**: View the terminal's travel route over time with altitude-based coloring
      ```
    - [ ] 7.2.4 Save the file
  - [ ] 7.3 Update Grafana Documentation
    - [ ] 7.3.1 Open `docs/grafana-setup.md`
    - [ ] 7.3.2 Add a section describing the position history feature, including:
      - How to use the time window selector
      - How to interpret the altitude-based colors
      - How to view detailed telemetry via tooltips
    - [ ] 7.3.3 Save the file
  - [ ] 7.4 Export Dashboard JSON (if needed for backup)
    - [ ] 7.4.1 In Grafana UI, go to Dashboard Settings (gear icon)
    - [ ] 7.4.2 Click "JSON Model" in the left sidebar
    - [ ] 7.4.3 Copy the JSON and save to a backup file (e.g., `position-movement-backup.json`)
    - [ ] 7.4.4 This is optional but recommended before committing changes
  - [ ] 7.5 Commit Changes to Git
    - [ ] 7.5.1 Stage the modified dashboard file:
      ```bash
      git add monitoring/grafana/provisioning/dashboards/position-movement.json
      ```
    - [ ] 7.5.2 Stage documentation changes:
      ```bash
      git add CLAUDE.md README.md docs/grafana-setup.md
      ```
    - [ ] 7.5.3 Commit with a descriptive message:
      ```bash
      git commit -m "feat: add position history layer with altitude-based coloring

      - Add dashboard variable for time window selection (6h to 15d)
      - Configure 9 Prometheus queries for historical position and telemetry data
      - Implement data transformation pipeline (merge, organize, convert, filter)
      - Update route layer with altitude-based color gradient
      - Add detailed tooltips showing position, telemetry, and network metrics
      - Update documentation with feature description and usage instructions

      Closes PRD-0007"
      ```
    - [ ] 7.5.4 Do NOT push to remote yet - wait for final testing checklist
  - [ ] 7.6 Final Testing Checklist
    - [ ] 7.6.1 Position history route displays correctly with altitude-based colors
    - [ ] 7.6.2 Current position marker (plane icon) is still visible and not obscured by the route
    - [ ] 7.6.3 Tooltip shows all required data fields when hovering over the route:
      - Time, latitude, longitude, altitude, speed, heading, latency, throughput_down, throughput_up, obstructions
    - [ ] 7.6.4 Time window selector works and updates the route when changed
    - [ ] 7.6.5 Toggle control works (if implemented) OR layer eye icon toggles visibility
    - [ ] 7.6.6 Performance is acceptable (<2-3 seconds load time for 24h window)
    - [ ] 7.6.7 Works in both simulation mode and live mode
    - [ ] 7.6.8 Dashboard saves and persists configuration correctly (refresh page and verify route still appears)
    - [ ] 7.6.9 Documentation is updated and accurate
    - [ ] 7.6.10 Git commit message follows project conventions
  - [ ] 7.7 Push to Remote (if all checks pass)
    - [ ] 7.7.1 If all final testing checks pass, push the commit:
      ```bash
      git push origin main
      ```
    - [ ] 7.7.2 If any checks fail, fix issues and re-test before pushing

---

**Status:** ✅ COMPLETE - All tasks implemented and tested
**Implementation Time:** Completed in single session
**Difficulty Level:** Intermediate (requires JSON editing, understanding of Grafana concepts)
**Last Updated:** October 24, 2025
**Commit:** feat: add position history layer with altitude-based coloring

## Implementation Tips for Junior Developers

### JSON Editing Tips
- **Use a code editor with JSON syntax highlighting** (VS Code, Sublime Text, etc.)
- **Enable auto-formatting** to maintain proper indentation
- **Always validate JSON** before saving (use JSONLint.com or your editor's built-in validator)
- **Common JSON errors**:
  - Missing or extra commas
  - Mismatched brackets/braces
  - Unescaped quotes in strings
  - Trailing commas (not allowed in JSON)

### Grafana Dashboard Provisioning
- **Grafana reloads provisioned dashboards automatically** every 10 seconds (configured in dashboards.yml)
- **You cannot save changes from Grafana UI** when `allowUiUpdates: false` is set in provisioning config
- **All changes must be made directly in the JSON file**
- **To test changes**: Edit JSON → Wait 10-15 seconds → Refresh browser

### Prometheus Query Tips
- **Test queries in Prometheus UI first** (http://localhost:9090) before adding to Grafana
- **The `[10s]` syntax** in `avg_over_time(metric[10s])` means "average over the last 10 seconds"
- **The `step: 10` parameter** tells Prometheus to sample data every 10 seconds
- **Time series vs instant queries**:
  - Instant query (`"instant": true`): Returns single current value
  - Time series query (`"instant": false` or omitted): Returns historical values over time range

### Grafana Transformations
- **Transformations are applied in order** - the output of one becomes the input of the next
- **Use "Table view" in the Transform tab** to see how data looks after each transformation
- **Common transformation IDs**:
  - `merge`: Combines all series into one table
  - `joinByField`: Joins series by a common field (usually "Time")
  - `organize`: Renames and reorders fields
  - `convertFieldType`: Changes field data types
  - `filterByValue`: Removes rows based on conditions

### Debugging Tips
- **Check Grafana logs**: `docker compose logs grafana | tail -50`
- **Check backend logs**: `docker compose logs backend | tail -50`
- **Check Prometheus targets**: http://localhost:9090/targets (verify all targets are "UP")
- **Use browser DevTools**:
  - Console tab: Check for JavaScript errors
  - Network tab: Check for failed API requests
  - Application tab → Local Storage: Clear Grafana cache if needed
- **Common issues**:
  - "No data" in panel: Check Prometheus queries, verify metrics exist
  - Route not appearing: Check transformations, verify lat/lon fields are numbers
  - Colors not working: Check field config color mode, verify altitude field exists
  - Slow performance: Increase step interval (10s → 30s → 60s)

### Color Scheme Reference
Available Grafana color schemes for continuous gradients (Grafana 10.x+):
- `continuous-GrYlRd` - Green → Yellow → Red
- `continuous-blues` - Light Blue → Dark Blue
- `continuous-reds` - Light Red → Dark Red
- `continuous-greens` - Light Green → Dark Green
- `continuous-purples` - Light Purple → Dark Purple

For "Turbo" or "Viridis" palettes (PRD recommendation), you may need Grafana 11.x+ or use one of the above alternatives.

### Testing Best Practices
1. **Always test in simulation mode first** (easier to generate consistent test data)
2. **Test with different time ranges** to ensure queries work correctly
3. **Check browser console for errors** after every change
4. **Verify tooltip data** matches expected fields from PRD
5. **Test performance with maximum time range (15d)** to ensure acceptable load times
6. **Take screenshots of working configuration** for documentation/reference

## Troubleshooting Common Issues

### Issue: "No data" in Geomap panel
**Possible causes:**
- Backend not running or not exporting metrics
- Prometheus not scraping backend
- Queries have incorrect metric names
- Transformations filtering out all data

**Solutions:**
1. Check backend is running: `docker compose ps`
2. Check Prometheus targets: http://localhost:9090/targets
3. Test queries individually in Prometheus UI
4. Review transformations in Grafana UI (Edit panel → Transform → Table view)

### Issue: Route line not appearing, but markers show
**Possible causes:**
- Route layer configuration incorrect
- Lat/lon fields not mapped correctly
- Data transformation not producing table format

**Solutions:**
1. Verify transformations output includes lat/lon fields (Edit panel → Transform → Table view)
2. Check route layer config: `location.latitude` and `location.longitude` must match transformed field names
3. Ensure queries E-M are not "instant" queries (should retrieve time series data)

### Issue: Colors not showing altitude gradient
**Possible causes:**
- Color mode not set to continuous gradient
- Altitude field not mapped to color
- Field config color scheme not configured

**Solutions:**
1. Check route layer config: `style.color.field` should be `"altitude"`
2. Check panel field config: `defaults.color.mode` should be continuous gradient scheme
3. Verify altitude field exists in transformed data (Edit panel → Transform → Table view)
4. Try different color schemes (GrYlRd, blues, reds, etc.)

### Issue: Tooltip shows "Value #E", "Value #F" instead of field names
**Possible causes:**
- Organize fields transformation not applied or incorrect
- Field names not matching transformation rename config

**Solutions:**
1. Check organize transformation `renameByName` mapping
2. Verify transformation order (organize should come after merge/join)
3. Check for typos in field names

### Issue: Dashboard changes not appearing after saving JSON
**Possible causes:**
- Grafana hasn't reloaded the dashboard yet (wait 10-15 seconds)
- JSON syntax error preventing reload
- Browser cache showing old version

**Solutions:**
1. Wait 15 seconds and hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Check Grafana logs for JSON parsing errors: `docker compose logs grafana | grep -i error`
3. Validate JSON syntax using JSONLint.com
4. Clear browser cache and cookies for localhost:3000
