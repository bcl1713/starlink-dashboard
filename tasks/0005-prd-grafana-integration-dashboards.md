# PRD: Grafana Integration and Dashboards (Phase 5)

**Document Version:** 1.0 **Date:** 2025-10-23 **Status:** Draft

---

## 1. Introduction/Overview

Phase 5 delivers the complete visualization layer for the Starlink monitoring
system. This phase builds upon the working Prometheus metrics infrastructure
(Phase 3) and KML/POI system (Phase 4) to create a comprehensive, user-friendly
web dashboard using Grafana.

The dashboard must provide real-time situational awareness of the Starlink
terminal's position, movement, network performance, and proximity to points of
interest. The system must work identically in both simulation and live modes,
requiring no manual configuration changes.

**Problem Statement:** Developers and operators need a visual interface to
monitor Starlink terminal telemetry, track movement along planned routes,
analyze network performance trends, and estimate arrival times at waypoints.

**Goal:** Deliver a production-ready, auto-provisioned Grafana dashboard system
that visualizes all telemetry data, supports large high-resolution displays
(3000x2000), and provides near real-time updates with intuitive navigation
across overview and detailed metric views.

---

## 2. Goals

1. **Auto-provision Grafana** with pre-configured datasources and dashboards
   requiring zero manual setup
1. **Create three dashboards:**
   - Overview: Map + key metrics summary
   - Network Metrics: Detailed network performance analysis
   - Position & Movement: Detailed position, speed, altitude, and route tracking
1. **Implement real-time map visualization** showing current position, 48-hour
   historical track, planned route overlay, and POI markers
1. **Display all Prometheus metrics** with appropriate visualizations, units,
   and threshold warnings
1. **Support flexible time range selection** (5 min to 48 hours) with
   auto-updating windows
1. **Optimize for large displays** (3000x2000 resolution) with fullscreen mode
   support
1. **Provide clear simulation mode indication** with dismissible banner
1. **Include world clock display** showing Zulu, Washington DC, and two
   configurable timezone clocks
1. **Ensure dashboard portability** via JSON export for version control and
   sharing

---

## 3. User Stories

1. **As a developer**, I want Grafana to start fully configured so I can
   immediately view simulated data without manual setup.

1. **As an operator**, I want to see the terminal's current position and planned
   route on a map so I can verify it's following the correct path.

1. **As a flight crew member**, I want to see ETAs to upcoming waypoints so I
   can coordinate arrivals and activities.

1. **As a network engineer**, I want to analyze latency and throughput trends
   over time to identify performance patterns and issues.

1. **As a demo presenter**, I want a clear indicator when simulation mode is
   active so viewers understand they're seeing generated data.

1. **As a multi-timezone operator**, I want to see world clocks for key
   locations so I can coordinate across time zones without mental math.

1. **As a troubleshooter**, I want to see threshold warnings (e.g., high
   latency) highlighted visually so issues are immediately apparent.

1. **As a power user**, I want to pause auto-refresh and zoom into specific time
   windows to analyze historical data in detail.

---

## 4. Functional Requirements

### 4.1 Grafana Infrastructure

1. **REQ-GI-001:** Grafana container must be included in `docker-compose.yml`
   with persistent volume for configuration and dashboards.

1. **REQ-GI-002:** Prometheus datasource must be auto-provisioned via
   configuration files in `monitoring/grafana/provisioning/datasources/`.

1. **REQ-GI-003:** Admin credentials must be configurable via environment
   variable `GRAFANA_ADMIN_PASSWORD` (default: `admin`).

1. **REQ-GI-004:** Grafana must be accessible at `<http://localhost:3000`> after
   `docker compose up`.

1. **REQ-GI-005:** All required plugins must be installed during container build
   (see REQ-MAP-001).

### 4.2 Map Panel Requirements

1. **REQ-MAP-001:** The system must install the `pr0ps-trackmap-panel` Grafana
   plugin (or `grafana-worldmap-panel` if trackmap is unavailable/unsuitable
   based on implementation testing).

1. **REQ-MAP-002:** The map panel must display the current terminal position
   using `starlink_dish_latitude_degrees` and `starlink_dish_longitude_degrees`
   metrics.

1. **REQ-MAP-003:** The map panel must render a historical track/trail showing
   the last 48 hours of movement.

1. **REQ-MAP-004:** The map panel must overlay the planned route loaded from the
   `/route.geojson` endpoint.

1. **REQ-MAP-005:** The map panel must display POI markers with labels showing
   POI names.

1. **REQ-MAP-006:** The map must use OpenStreetMap as the base layer (per design
   document section 5).

1. **REQ-MAP-007:** The map panel must auto-center on the current position
   unless the user has manually panned the view.

### 4.3 Dashboard Structure

1. **REQ-DASH-001:** The system must provide three dashboards:
   - **Overview Dashboard:** Map + summary metrics
   - **Network Metrics Dashboard:** Detailed network performance
   - **Position & Movement Dashboard:** Detailed position, speed, altitude, and
     heading

1. **REQ-DASH-002:** Dashboards must be auto-provisioned from JSON files in
   `monitoring/grafana/provisioning/dashboards/`.

1. **REQ-DASH-003:** The Overview dashboard must be set as the default home
   dashboard.

1. **REQ-DASH-004:** Dashboards must support fullscreen mode and render properly
   at 3000x2000 resolution.

1. **REQ-DASH-005:** Dashboard navigation links must be provided for easy
   switching between dashboards.

### 4.4 Overview Dashboard Layout

1. **REQ-OV-001:** The Overview dashboard must include these panels:
   - Large map panel (upper left, ~60% width, 50% height)
   - POI/ETA table (upper right, ~40% width, 50% height)
   - Network performance summary (lower section, full width, multiple panels)

2. **REQ-OV-002:** The Overview dashboard must include the following metric
   panels:
   - Latency (time series graph)
   - Download/Upload throughput (combined time series)
   - Obstruction percentage (gauge or time series)
   - Current speed and heading (stat panels)
   - Current altitude (stat panel)
   - Connection status/uptime indicator

3. **REQ-OV-003:** Panels must be arranged in a visually balanced grid layout
   optimized for 3000x2000 displays.

### 4.5 Network Metrics Dashboard

1. **REQ-NET-001:** The Network Metrics dashboard must include detailed panels
   for:
   - Latency trends (time series with min/max/avg)
   - Download throughput (time series)
   - Upload throughput (time series)
   - Combined download/upload comparison (time series on same axes)
   - Packet loss/error rate (if available in metrics)
   - Obstruction statistics (time series and statistics)
   - Outage events (time series or event log if available)

1. **REQ-NET-002:** Network panels must use appropriate units (ms for latency,
   Mbps for throughput, % for obstructions).

### 4.6 Position & Movement Dashboard

1. **REQ-POS-001:** The Position & Movement dashboard must include:
   - Large map panel with track and route (top, 100% width, 60% height)
   - Current coordinates (stat panels: latitude, longitude, altitude)
   - Speed and heading (gauge or stat panels)
   - Altitude graph over time (time series)
   - Speed graph over time (time series)
   - Heading/bearing graph over time (time series)

2. **REQ-POS-002:** Position metrics must use appropriate units and precision:
   - Coordinates: decimal degrees (6 decimal places)
   - Altitude: meters or feet
   - Speed: knots or km/h
   - Heading: degrees (0-360)

### 4.7 POI/ETA Table

1. **REQ-POI-001:** The POI/ETA table must display all defined POIs with columns
   for:
   - POI name
   - Distance (in nautical miles or kilometers)
   - ETA (in time format: HH:MM or HH:MM:SS)

1. **REQ-POI-002:** The table must be sorted with upcoming POIs first (by
   soonest ETA), followed by passed POIs (most recently passed first).

1. **REQ-POI-003:** The table must use data from the Prometheus metrics:
   - `starlink_distance_to_poi_meters{name="..."}`
   - `starlink_eta_poi_seconds{name="..."}`

1. **REQ-POI-004:** Distance and ETA values must refresh at the same interval as
   other dashboard metrics.

### 4.8 Time Range and Refresh

1. **REQ-TIME-001:** Dashboards must support selectable time ranges:
   - 5 minutes (default)
   - 10 minutes
   - 15 minutes
   - 30 minutes
   - 1 hour
   - 2 hours
   - 4 hours
   - 8 hours
   - 24 hours
   - 48 hours

2. **REQ-TIME-002:** Time ranges must auto-update (e.g., "Last 5 minutes"
   continuously shifts forward as new data arrives).

3. **REQ-REFRESH-001:** Dashboard auto-refresh interval must be configurable and
   set to the slower of:
   - 1 second
   - 2× the fastest backend service metric update interval

4. **REQ-REFRESH-002:** Example: If the backend updates metrics every 3 seconds,
   refresh should be max(1, 2×3) = 6 seconds.

5. **REQ-REFRESH-003:** Users must be able to pause and resume auto-refresh via
   Grafana's built-in controls.

### 4.9 Threshold Warnings and Alerts

1. **REQ-THRESH-001:** Panels must use color thresholds to indicate warning
   conditions:
   - Latency: Green <80ms, Yellow 80-120ms, Red >120ms
   - Download throughput: Red <50 Mbps, Yellow 50-100 Mbps, Green >100 Mbps
   - Upload throughput: Red <10 Mbps, Yellow 10-20 Mbps, Green >20 Mbps
   - Obstruction: Green <5%, Yellow 5-15%, Red >15%

1. **REQ-THRESH-002:** Stat panels showing current values must change background
   or text color based on threshold ranges.

1. **REQ-THRESH-003:** Time series graphs must include threshold reference lines
   at critical values.

### 4.10 Simulation Mode Indicator

1. **REQ-SIM-001:** When `SIMULATION_MODE=true`, a dismissible banner must
   appear at the top of all dashboards stating "Simulation Mode Active" or
   similar.

1. **REQ-SIM-002:** The banner must be implemented using Grafana's text panel or
   annotation feature.

1. **REQ-SIM-003:** The banner must be visually distinct (e.g., yellow/orange
   background, prominent text).

1. **REQ-SIM-004:** The banner must be dismissible for the current session (user
   can close it, but it reappears on page reload).

1. **REQ-SIM-005:** In live mode (`SIMULATION_MODE=false`), the banner must not
   be visible.

### 4.11 World Clocks

1. **REQ-CLOCK-001:** Dashboards must include a world clock panel showing the
   current time in:
   - Zulu (UTC)
   - Washington DC (America/New_York)
   - Two additional configurable time zones (configured via environment
     variables or Grafana variables)

1. **REQ-CLOCK-002:** World clock display should use a clock or stat panel
   showing timezone abbreviation and time in HH:MM:SS format.

1. **REQ-CLOCK-003:** If configurable timezones for takeoff/landing locations
   are not set, the panel should default to placeholder values (e.g.,
   "Europe/London" and "Asia/Tokyo").

1. **REQ-CLOCK-004:** Clock panels must update in real-time (1-second
   intervals).

### 4.12 Visual Design and Polish

1. **REQ-DESIGN-001:** Dashboards must use a consistent, professional Grafana
   theme (default dark theme recommended).

1. **REQ-DESIGN-002:** Panel titles must be clear, concise, and descriptive.

1. **REQ-DESIGN-003:** Graphs must include axis labels, units, and legends where
   applicable.

1. **REQ-DESIGN-004:** The layout must be responsive and visually balanced,
   avoiding excessive whitespace or cramped panels.

1. **REQ-DESIGN-005:** Color schemes must be consistent across dashboards (e.g.,
   download always blue, upload always green).

### 4.13 Provisioning and Portability

1. **REQ-PROV-001:** All dashboards must be version-controlled as JSON files in
   `monitoring/grafana/provisioning/dashboards/`.

1. **REQ-PROV-002:** Dashboard JSON files must be automatically loaded on
   Grafana startup via provisioning configuration.

1. **REQ-PROV-003:** Users must be able to customize dashboards through the
   Grafana UI, with changes persisted in Grafana's database volume.

1. **REQ-PROV-004:** The datasource provisioning file must configure Prometheus
   with the correct internal Docker network URL (e.g.,
   `<http://prometheus:9090>`).

1. **REQ-PROV-005:** Grafana configuration must set the timezone to UTC (Zulu)
   by default.

---

## 5. Non-Goals (Out of Scope for Phase 5)

1. **Custom Grafana plugin development** — Only use existing community plugins.

2. **User authentication and role-based access control** — Use Grafana's default
   admin account. Multi-user authentication deferred to future phases.

3. **Alerting rules and notifications** — Alert configuration (email, Slack,
   etc.) is deferred to Phase 6 or later.

4. **Mobile-responsive design** — Dashboards optimized for large displays
   (3000x2000); mobile/tablet optimization is out of scope.

5. **Historical data export** — Exporting raw or aggregated data from Grafana is
   not required in this phase.

6. **Weather overlay integration** — Mentioned in design doc section 5, but
   deferred to Phase 9 (Optional Enhancements).

7. **Custom Grafana branding** — Use default Grafana UI; custom logos and
   branding deferred.

8. **WebSocket-based real-time updates** — Use Grafana's polling-based refresh
   (Phase 9 enhancement).

9. **Multi-terminal support** — Single Starlink terminal only; multi-unit
   dashboards deferred to future phases.

---

## 6. Design Considerations

### 6.1 Plugin Selection

- **Primary choice:** `pr0ps-trackmap-panel` for map visualization
- **Fallback:** `grafana-worldmap-panel` or core Grafana Geomap panel if
  trackmap is incompatible
- Test both options during implementation to determine which best supports the
  requirements (current position, track trail, route overlay, POI markers)

### 6.2 Layout Approach

- Use Grafana's grid system with rows and panels
- Panels sized in grid units (1 unit = smallest increment, typically 1/24 of
  width)
- Recommended grid for Overview dashboard:
  - Map: 14 units wide (58%), 12 units tall
  - POI Table: 10 units wide (42%), 12 units tall
  - Metrics row: Full width (24 units), divided into 4-6 panels

### 6.3 Dashboard JSON Structure

- Each dashboard JSON must include:
  - `title`, `uid`, `version` fields
  - `templating` section for variables (time range, refresh interval)
  - `panels` array with all visualization configurations
  - `time` settings (default range, refresh intervals)

### 6.4 Metric Queries

All panels must query Prometheus using PromQL. Example queries:

- **Current position:** `starlink_dish_latitude_degrees`,
  `starlink_dish_longitude_degrees`
- **Throughput:** `starlink_network_throughput_down_mbps`,
  `starlink_network_throughput_up_mbps`
- **ETA to POI:** `starlink_eta_poi_seconds{name="Waypoint A"}`

### 6.5 Simulation Banner Implementation

Two options:

1. **Text panel** at top of dashboard with conditional visibility based on a
   Grafana variable
1. **Dashboard annotation** triggered by a query detecting simulation mode
   metric

Recommend approach: Use a text panel with Markdown content and custom CSS for
styling.

---

## 7. Technical Considerations

### 7.1 Dependencies

- **Grafana Docker image:** `grafana/grafana:latest` or specific stable version
  (e.g., `10.x`)
- **Required plugins:** Installed via `GF_INSTALL_PLUGINS` environment variable
  in docker-compose.yml
- **Prometheus datasource:** Must be reachable at `<http://prometheus:9090`> on
  the Docker network

### 7.2 Provisioning File Structure

```text
monitoring/grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml       # Auto-configure Prometheus datasource
│   └── dashboards/
│       ├── dashboards.yml       # Dashboard provisioning config
│       ├── overview.json        # Overview dashboard JSON
│       ├── network-metrics.json # Network dashboard JSON
│       └── position-movement.json # Position dashboard JSON
└── grafana.ini (optional)       # Custom Grafana settings
```

### 7.3 Docker Compose Configuration

Grafana service must include:

- Environment variables:
  - `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}`
  - `GF_INSTALL_PLUGINS=pr0ps-trackmap-panel` (or selected map plugin)
  - `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` (path to overview.json UID)
- Volumes:
  - Provisioning directories
  - Persistent volume for Grafana database (`/var/lib/grafana`)
- Network: Shared Docker network with Prometheus

### 7.4 Refresh Rate Calculation

Backend services (from Phase 2/3):

- Simulation engine updates: every 3-5 seconds
- Prometheus scrape interval: likely 5-15 seconds (configured in Phase 3)

Recommended Grafana refresh: 5 seconds (slower than 1 second due to backend
constraints, faster than 10 seconds for near real-time feel)

**Action item:** Verify Prometheus scrape interval from Phase 3 configuration
and set dashboard refresh to `2 × scrape_interval` or 5 seconds, whichever is
greater.

### 7.5 World Clock Implementation

Grafana does not have native world clock panels. Options:

1. **Clock panel plugin:** Install `grafana-clock-panel` plugin
2. **Stat panels with time variables:** Use Grafana variables and
   transformations to display time in different zones
3. **Text panel with custom HTML/JS:** Embed simple JavaScript clock (may have
   CSP restrictions)

Recommended: Install `grafana-clock-panel` plugin and add multiple clock panels
configured with different timezones.

---

## 8. Success Metrics

1. **Zero-configuration startup:** User runs `docker compose up -d` and can
   access working dashboards at `<http://localhost:3000`> within 30 seconds
   (excluding image pull time).

1. **Real-time data visibility:** All metrics update visibly within 10 seconds
   of container startup when simulation mode is active.

1. **Map functionality:** Map panel displays:
   - Current position marker
   - 48-hour track trail (after sufficient runtime)
   - Route overlay from `/route.geojson`
   - POI markers with labels

1. **Threshold visualization:** At least one panel (e.g., latency) demonstrates
   color changes when values cross defined thresholds.

1. **Dashboard navigation:** User can navigate between all three dashboards
   using dashboard links or Grafana's navigation menu.

1. **Simulation mode indicator:** Banner is visible on all dashboards when
   `SIMULATION_MODE=true` and dismissible by the user.

1. **Portability:** Dashboard JSON files can be exported, shared, and imported
   into a clean Grafana instance without errors.

1. **Time range flexibility:** User can select any of the specified time ranges
   (5 min to 48 hours) and see data update accordingly.

1. **Fullscreen optimization:** Dashboard appears visually balanced and readable
   when viewed fullscreen on a 3000x2000 resolution display.

1. **World clock display:** Zulu and Washington DC times are visible and update
   every second.

---

## 9. Open Questions

1. **Q1:** Should the simulation mode banner also indicate the current
   simulation route name (if loaded from a KML file)?

1. **Q2:** Should POIs passed more than 24 or 48 hours ago be hidden from the
   POI/ETA table to reduce clutter on long journeys?

1. **Q3:** Should the map panel include zoom controls and a scale bar?

1. **Q4:** For the configurable world clocks, should timezone selection be:
   - Environment variables in `.env` (e.g.,
     `TAKEOFF_TIMEZONE=America/Los_Angeles`)
   - Grafana dashboard variables (user-selectable dropdown)

1. **Q5:** Should the Overview dashboard include a "last updated" timestamp
   showing when metrics were last refreshed?

1. **Q6:** Are there any specific color palettes or corporate branding
   requirements for the dashboards?

1. **Q7:** Should the dashboards include a link or button to access Prometheus'
   native UI for advanced querying?

1. **Q8:** For the 48-hour track trail on the map, should the trail gradually
   fade or change color based on age (e.g., recent positions bright, older
   positions dimmed)?

1. **Q9:** Should users be able to toggle the route overlay and POI markers
   on/off via dashboard variables?

1. **Q10:** Should the position dashboard include a compass rose or heading
   indicator visualization?

---

## 10. Acceptance Criteria

### 10.1 Infrastructure

- [ ] Grafana container starts successfully via `docker compose up -d`
- [ ] Grafana accessible at `<http://localhost:3000`>
- [ ] Admin login works with configured password
- [ ] Prometheus datasource auto-provisioned and working (test connection
      succeeds)
- [ ] Required plugins (map panel, clock panel) installed and available

### 10.2 Dashboards

- [ ] Three dashboards auto-loaded: Overview, Network Metrics, Position &
      Movement
- [ ] Overview dashboard set as default home dashboard
- [ ] All panels load without errors
- [ ] Dashboard navigation links work correctly

### 10.3 Map Visualization

- [ ] Map panel displays OpenStreetMap base layer
- [ ] Current position marker visible and updating
- [ ] 48-hour track trail visible (after running simulation for sufficient time)
- [ ] Route overlay from `/route.geojson` displayed correctly
- [ ] POI markers displayed on map with labels

### 10.4 Metrics Display

- [ ] All required metrics visible and updating:
  - Latency
  - Download/upload throughput
  - Obstruction percentage
  - Speed, heading, altitude
  - Connection status
- [ ] Metrics display correct units
- [ ] Threshold colors applied correctly (test by forcing metric values)

### 10.5 POI/ETA Table

- [ ] Table displays all POIs with name, distance, ETA
- [ ] POIs sorted correctly (upcoming first, passed second)
- [ ] Values update at refresh interval

### 10.6 Time and Refresh

- [ ] Time range selector includes all specified options (5min to 48hr)
- [ ] Default time range is 5 minutes
- [ ] Time window auto-updates (shifts forward with new data)
- [ ] Auto-refresh works at configured interval
- [ ] Pause/resume refresh controls work

### 10.7 Simulation Mode Indicator

- [ ] Banner visible when `SIMULATION_MODE=true`
- [ ] Banner dismissible by user
- [ ] Banner reappears after page reload (when still in simulation mode)
- [ ] Banner not visible when `SIMULATION_MODE=false`

### 10.8 World Clocks

- [ ] World clock panel displays Zulu time
- [ ] World clock panel displays Washington DC time
- [ ] Configurable timezones display correctly (or default placeholders)
- [ ] Clocks update every second

### 10.9 Design and UX

- [ ] Dashboards render properly at 3000x2000 resolution in fullscreen mode
- [ ] Panel layout is visually balanced and professional
- [ ] Color schemes consistent across dashboards
- [ ] All panels have clear titles and legends

### 10.10 Portability

- [ ] Dashboard JSON files committed to version control
- [ ] Dashboards can be exported via Grafana UI
- [ ] Exported JSON can be imported into a fresh Grafana instance

---

## 11. Implementation Notes

### 11.1 Recommended Implementation Order

1. Set up Grafana container in docker-compose.yml with plugins
2. Create Prometheus datasource provisioning configuration
3. Build the Overview dashboard incrementally:
   - Start with basic layout (text panels as placeholders)
   - Add map panel and verify position data
   - Add POI/ETA table
   - Add metric panels one by one
4. Test refresh rates and time ranges
5. Implement simulation mode banner
6. Add world clocks
7. Apply threshold colors and styling
8. Build Network Metrics dashboard (duplicate Overview patterns)
9. Build Position & Movement dashboard
10. Test end-to-end in fresh environment
11. Export and commit dashboard JSONs

### 11.2 Testing Strategy

- **Unit testing:** Not applicable for Grafana dashboards
- **Manual testing:**
  - Verify each panel displays correct data from Prometheus
  - Test all time ranges and refresh rates
  - Simulate threshold crossings (modify backend to force high latency, etc.)
  - Test on target display resolution (3000x2000)
- **Integration testing:**
  - Clean Docker environment test
    (`docker compose down -v && docker compose up`)
  - Verify auto-provisioning works without manual intervention
  - Test with different `.env` configurations (SIMULATION_MODE true/false)

### 11.3 Documentation

Update project README.md to include:

- Grafana access URL and default credentials
- Dashboard overview (what each dashboard shows)
- How to customize dashboards
- How to export/import dashboards
- Troubleshooting common Grafana issues (plugin installation, datasource
  connection)

---

## Appendix A: Prometheus Metrics Reference

| Metric Name                                   | Type  | Description                       | Unit    |
| --------------------------------------------- | ----- | --------------------------------- | ------- |
| `starlink_dish_latitude_degrees`              | Gauge | Current latitude                  | degrees |
| `starlink_dish_longitude_degrees`             | Gauge | Current longitude                 | degrees |
| `starlink_dish_altitude_meters`               | Gauge | Current altitude                  | meters  |
| `starlink_dish_speed_knots`                   | Gauge | Current speed                     | knots   |
| `starlink_dish_heading_degrees`               | Gauge | Current heading/bearing           | degrees |
| `starlink_network_latency_ms`                 | Gauge | Network latency                   | ms      |
| `starlink_network_throughput_down_mbps`       | Gauge | Download throughput               | Mbps    |
| `starlink_network_throughput_up_mbps`         | Gauge | Upload throughput                 | Mbps    |
| `starlink_dish_obstruction_percent`           | Gauge | Obstruction percentage            | %       |
| `starlink_eta_poi_seconds{name="..."}`        | Gauge | ETA to POI                        | seconds |
| `starlink_distance_to_poi_meters{name="..."}` | Gauge | Distance to POI                   | meters  |
| Additional metrics from Phase 3               | —     | (Connection status, uptime, etc.) | varies  |

(Note: Refer to Phase 3 PRD for complete metrics list.)

---

## Appendix B: Example PromQL Queries

### Current Position

```promql
starlink_dish_latitude_degrees
starlink_dish_longitude_degrees
```

### Latency with Average Over Time

```promql
avg_over_time(starlink_network_latency_ms[5m])
```

### Combined Throughput

```promql
starlink_network_throughput_down_mbps
starlink_network_throughput_up_mbps
```

### ETA to Specific POI

```promql
starlink_eta_poi_seconds{name="Waypoint Alpha"}
```

### Distance to All POIs

```promql
starlink_distance_to_poi_meters
```

---

## Appendix C: Grafana Provisioning File Examples

### Datasource Provisioning (`prometheus.yml`)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: <http://prometheus:9090>
    isDefault: true
    editable: false
```

### Dashboard Provisioning (`dashboards.yml`)

```yaml
apiVersion: 1

providers:
  - name: "Starlink Dashboards"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

---

**End of PRD**
