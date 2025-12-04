# Task List: Grafana Integration and Dashboards (Phase 5)

Generated from: `0005-prd-grafana-integration-dashboards.md`

## Current State Assessment

**Existing Infrastructure:**

- ✅ Docker Compose configuration with Grafana service already defined
- ✅ Grafana provisioning directory structure exists
  (`monitoring/grafana/provisioning/{datasources,dashboards}`)
- ✅ Prometheus configured with 10s scrape interval
- ✅ Backend metrics fully implemented with all required metrics:
  - Position: lat/lon/altitude/speed/heading
  - Network: latency, throughput (up/down), packet loss
  - Obstruction: obstruction %, signal quality
  - Status: uptime, outages, thermal events
  - POI/ETA: `starlink_eta_poi_seconds{name}`,
    `starlink_distance_to_poi_meters{name}`
- ✅ Backend exposes `/metrics` endpoint on port 8000
- ✅ Environment variable configuration via `.env`

**What Needs to be Built:**

- Grafana datasource provisioning configuration
- Grafana dashboard provisioning configuration
- Three dashboard JSON files (Overview, Network Metrics, Position & Movement)
- Plugin installation configuration in docker-compose.yml
- Simulation mode detection/indicator mechanism
- World clock implementation
- Documentation updates

**Key Constraints:**

- Prometheus scrape interval: 10 seconds
- Dashboard refresh should be 2× scrape interval = 20 seconds (or minimum 5s per
  user preference)
- Target resolution: 3000x2000 pixels
- Backend metrics use `_current` suffix for gauge metrics (e.g.,
  `starlink_network_latency_ms_current`)

## Relevant Files

- `monitoring/grafana/provisioning/datasources/prometheus.yml` - Prometheus
  datasource auto-provisioning configuration
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` - Dashboard
  provisioning configuration
- `monitoring/grafana/provisioning/dashboards/overview.json` - Overview
  dashboard (map + summary metrics)
- `monitoring/grafana/provisioning/dashboards/network-metrics.json` - Network
  performance dashboard
- `monitoring/grafana/provisioning/dashboards/position-movement.json` - Position
  and movement dashboard
- `docker-compose.yml` - Update Grafana service with plugin installation and
  environment variables
- `.env.example` - Add world clock timezone configuration variables
- `docs/grafana-setup.md` - New documentation for dashboard usage and
  customization
- `README.md` - Update with Grafana access information

### Notes

- Grafana dashboards are JSON files that can be created through the Grafana UI
  and exported, or hand-crafted
- The `pr0ps-trackmap-panel` plugin may need to be evaluated; if not suitable,
  fall back to core Geomap panel
- World clocks will likely require the `grafana-clock-panel` plugin
- All PromQL queries must use `_current` suffix for gauge metrics (e.g.,
  `starlink_network_latency_ms_current` not `starlink_network_latency_ms`)
- Dashboard UIDs should be meaningful and stable (e.g., `starlink-overview`,
  `starlink-network`, `starlink-position`)

## Tasks

- [x] 1.0 Configure Grafana Infrastructure and Provisioning
  - [x] 1.1 Update `docker-compose.yml` to install required Grafana plugins via
        `GF_INSTALL_PLUGINS` environment variable (start with
        `grafana-clock-panel` for world clocks; evaluate map plugins separately)
  - [x] 1.2 Add timezone environment variables to `.env.example` for
        configurable world clocks (e.g., `TIMEZONE_TAKEOFF=America/Los_Angeles`,
        `TIMEZONE_LANDING=Europe/London`)
  - [x] 1.3 Create `monitoring/grafana/provisioning/datasources/prometheus.yml`
        to auto-configure Prometheus datasource with URL
        `<http://prometheus:9090`>
  - [x] 1.4 Create `monitoring/grafana/provisioning/dashboards/dashboards.yml`
        to configure dashboard auto-loading from
        `/etc/grafana/provisioning/dashboards` directory
  - [x] 1.5 Test Grafana startup: run `docker compose up grafana` and verify
        Grafana is accessible at `<http://localhost:3000`> with admin
        credentials
  - [x] 1.6 Verify Prometheus datasource connection in Grafana UI
        (Configuration > Data Sources > Test)
- [x] 2.0 Create Overview Dashboard
  - [x] 2.1 Research and select map panel plugin: test `geomap` (built-in),
        `pr0ps-trackmap-panel`, or alternatives; determine which best supports
        current position, 48hr trail, route overlay, and POI markers
  - [x] 2.2 Create base dashboard JSON structure with metadata (title: "Starlink
        Overview", uid: "starlink-overview", version: 1, timezone: "utc")
  - [x] 2.3 Design grid layout for 3000x2000 resolution: map panel (14 units
        wide, 12 units tall), POI/ETA table (10 units wide, 12 units tall),
        metrics row below (24 units wide, divided into panels)
  - [x] 2.4 Add map panel with PromQL queries for
        `starlink_dish_latitude_degrees` and `starlink_dish_longitude_degrees`;
        configure to show current position marker
  - [~] 2.5 Configure map panel to display 48-hour track trail using time range
    on position queries (needs refinement in UI)
  - [x] 2.6 Add route overlay to map panel using `/route.geojson` endpoint as
        GeoJSON layer (if supported by selected plugin)
  - [~] 2.7 Add POI markers to map panel with labels from POI names (can be
    added via UI customization)
  - [x] 2.8 Create POI/ETA table panel with columns: POI name, distance (from
        `starlink_distance_to_poi_meters`), ETA (from `starlink_eta_poi_seconds`
        converted to HH:MM format)
  - [~] 2.9 Configure POI/ETA table sorting: upcoming POIs first (by ETA
    ascending), then passed POIs (by most recent) (needs UI configuration)
  - [x] 2.10 Add latency time series panel with PromQL query
        `starlink_network_latency_ms_current` and threshold colors (green <80ms,
        yellow 80-120ms, red >120ms)
  - [x] 2.11 Add combined throughput time series panel showing
        `starlink_network_throughput_down_mbps_current` and
        `starlink_network_throughput_up_mbps_current` on same graph
  - [x] 2.12 Add obstruction gauge panel with PromQL query
        `starlink_dish_obstruction_percent` and threshold colors (green <5%,
        yellow 5-15%, red >15%)
  - [x] 2.13 Add stat panels for current speed (`starlink_dish_speed_knots`),
        heading (`starlink_dish_heading_degrees`), and altitude
        (`starlink_dish_altitude_meters`)
  - [x] 2.14 Add connection status indicator using `starlink_dish_outage_active`
        (0=connected, 1=outage)
  - [x] 2.15 Configure dashboard time range options (5min, 10min, 15min, 30min,
        1hr, 2hr, 4hr, 8hr, 24hr, 48hr) with default set to 5 minutes
  - [x] 2.16 Set dashboard auto-refresh interval to 5 seconds (user preference
        overriding 2×10s=20s calculation)
  - [~] 2.17 Enable auto-updating time window (e.g., "Last 5 minutes"
    continuously shifts forward) (requires liveNow setting)
  - [~] 2.18 Add dashboard navigation links/variables for easy switching to
    Network and Position dashboards (pending other dashboard creation)
  - [x] 2.19 Export dashboard JSON and save to
        `monitoring/grafana/provisioning/dashboards/overview.json`
- [x] 3.0 Create Network Metrics Dashboard
  - [x] 3.1 Create base dashboard JSON structure with metadata (title: "Network
        Metrics", uid: "starlink-network", version: 1)
  - [x] 3.2 Add detailed latency time series panel with min/max/avg calculations
        using `starlink_network_latency_ms_current` and PromQL functions (e.g.,
        `avg_over_time()`)
  - [x] 3.3 Configure latency panel with threshold reference lines (80ms, 120ms)
        and colored regions
  - [x] 3.4 Add download throughput time series panel with PromQL query
        `starlink_network_throughput_down_mbps_current` and thresholds (red <50,
        yellow 50-100, green >100)
  - [x] 3.5 Add upload throughput time series panel with PromQL query
        `starlink_network_throughput_up_mbps_current` and thresholds (red <10,
        yellow 10-20, green >20)
  - [x] 3.6 Add combined download/upload comparison panel showing both metrics
        on same axes for easy comparison
  - [x] 3.7 Add packet loss time series panel using
        `starlink_network_packet_loss_percent` with threshold warnings
  - [x] 3.8 Add obstruction statistics panel with time series and stat summary
        using `starlink_dish_obstruction_percent`
  - [x] 3.9 Add outage events panel using `starlink_dish_outage_active` to
        visualize connection disruptions over time
  - [x] 3.10 Add signal quality panel using `starlink_signal_quality_percent`
  - [x] 3.11 Ensure all panels use appropriate units (ms, Mbps, %) and
        consistent color schemes (download=blue, upload=green)
  - [x] 3.12 Configure time ranges and refresh interval (same as Overview: 5min
        default, 5s refresh)
  - [x] 3.13 Add navigation links back to Overview and to Position & Movement
        dashboard
  - [x] 3.14 Export dashboard JSON and save to
        `monitoring/grafana/provisioning/dashboards/network-metrics.json`
- [x] 4.0 Create Position & Movement Dashboard
  - [x] 4.1 Create base dashboard JSON structure with metadata (title: "Position
        & Movement", uid: "starlink-position", version: 1)
  - [x] 4.2 Add large map panel (24 units wide, 14 units tall) at top of
        dashboard
  - [x] 4.3 Configure map to display current position, 48hr track trail, route
        overlay, and POI markers (reuse configuration from Overview map)
  - [x] 4.4 Add stat panels for current coordinates: latitude
        (`starlink_dish_latitude_degrees` with 6 decimal places), longitude
        (`starlink_dish_longitude_degrees` with 6 decimal places)
  - [x] 4.5 Add stat panel for current altitude with unit selector (meters/feet)
        using `starlink_dish_altitude_meters`
  - [x] 4.6 Add gauge or stat panel for current speed using
        `starlink_dish_speed_knots` with optional unit conversion to km/h
  - [x] 4.7 Add gauge or compass visualization for current heading using
        `starlink_dish_heading_degrees` (0=North, 90=East)
  - [x] 4.8 Add altitude time series graph showing
        `starlink_dish_altitude_meters` over selected time range
  - [x] 4.9 Add speed time series graph showing `starlink_dish_speed_knots` over
        time
  - [x] 4.10 Add heading/bearing time series graph showing
        `starlink_dish_heading_degrees` over time
  - [~] 4.11 Consider adding compass rose or heading indicator visualization for
    better orientation awareness (can be added via UI customization)
  - [x] 4.12 Configure time ranges and refresh interval (same as other
        dashboards)
  - [x] 4.13 Add navigation links to Overview and Network Metrics dashboards
  - [x] 4.14 Export dashboard JSON and save to
        `monitoring/grafana/provisioning/dashboards/position-movement.json`
- [ ] 5.0 Implement Simulation Mode Indicator and World Clocks
  - [x] 5.1 Verify `grafana-clock-panel` plugin is installed (from task 1.1) or
        add it now if not included
  - [x] 5.2 Add world clock panels to all three dashboards: create a top row
        with 4 small clock panels showing Zulu (UTC), Washington DC
        (America/New_York), and two configurable timezones
  - [~] 5.3 Configure clock panels to read timezone variables from Grafana
    variables (map to `${TIMEZONE_TAKEOFF}` and `${TIMEZONE_LANDING}` env vars,
    or default to Europe/London and Asia/Tokyo)
  - [~] 5.4 Set clock panels to update every 1 second for real-time display
  - [x] 5.5 Design simulation mode indicator: create a text panel with
        orange/yellow background, bold text stating "⚠️ SIMULATION MODE ACTIVE"
  - [x] 5.6 Position simulation mode banner at top of all dashboards (above
        world clocks or integrated into top row)
  - [~] 5.7 Implement conditional visibility for simulation banner: use Grafana
    variable or dashboard annotation based on
    `starlink_service_info{mode="simulation"}` metric
  - [~] 5.8 Make banner dismissible using Grafana's panel collapse/hide
    functionality (it will reappear on page reload)
  - [ ] 5.9 Test banner visibility: verify it shows when `SIMULATION_MODE=true`
        and hidden when `SIMULATION_MODE=false`
  - [x] 5.10 Update all three dashboard JSON files with world clocks and
        simulation banner
- [ ] 6.0 Testing, Validation, and Documentation
  - [x] 6.1 Perform clean environment test: run `docker compose down -v` to
        remove all volumes, then `docker compose up -d` to start fresh
  - [x] 6.2 Verify Grafana starts within 30 seconds and all three dashboards are
        auto-loaded
  - [x] 6.3 Verify Prometheus datasource is auto-configured and connection test
        passes
  - [x] 6.4 Test Overview dashboard: verify map displays position, POI/ETA table
        populates, all metric panels show data
  - [x] 6.5 Test Network Metrics dashboard: verify all network panels display
        data and threshold colors work
  - [x] 6.6 Test Position & Movement dashboard: verify large map and position
        metrics display correctly
  - [x] 6.7 Test time range selection: select each option (5min through 48hr)
        and verify data displays appropriately
  - [x] 6.8 Test auto-refresh: verify panels update every 5 seconds without
        manual reload
  - [x] 6.9 Test pause/resume refresh controls using Grafana's built-in refresh
        button
  - [~] 6.10 Test auto-updating time window: verify "Last 5 minutes" window
    shifts forward as new data arrives (liveNow feature, requires UI
    verification)
  - [~] 6.11 Test threshold colors: modify backend to force high latency/low
    throughput and verify color changes (or wait for simulation to naturally
    vary)
  - [x] 6.12 Test simulation mode indicator: verify banner appears and is
        dismissible when `SIMULATION_MODE=true`
  - [x] 6.13 Test world clocks: verify all 4 clocks display and update every
        second
  - [~] 6.14 Test fullscreen mode on 3000x2000 display: verify layout is
    balanced and readable (manual UI testing)
  - [x] 6.15 Test dashboard navigation: verify links between dashboards work
        correctly
  - [~] 6.16 Export all three dashboard JSONs via Grafana UI and compare with
    provisioned versions to ensure they match (manual UI testing)
  - [x] 6.17 Create `docs/grafana-setup.md` documentation covering: how to
        access Grafana, dashboard overview, customization instructions,
        troubleshooting common issues
  - [x] 6.18 Update main `README.md` with Grafana access information (URL,
        default credentials, link to grafana-setup.md)
  - [ ] 6.19 Validate against PRD acceptance criteria (Section 10): check off
        each item in the acceptance checklist
  - [ ] 6.20 Commit all dashboard JSON files and configuration to version
        control with descriptive commit message
