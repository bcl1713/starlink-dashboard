# Monitoring Stack Configuration

This directory contains Prometheus and Grafana configuration for the Starlink monitoring system.

## Directory Structure

```
monitoring/
├── prometheus/          # Prometheus configuration
│   ├── prometheus.yml   # Main Prometheus config
│   └── rules/           # Alert rules (if any)
├── grafana/             # Grafana provisioning
│   └── provisioning/    # Dashboard and datasource provisioning
└── README.md            # This file
```

## Services

### Prometheus

Prometheus scrapes metrics from the backend service on a configurable interval (default: 1 second).

**Configuration:** `prometheus/prometheus.yml`

**Access:** http://localhost:9090

**Key Features:**
- 1-second scrape interval for real-time data
- Configurable retention period (default: 1 year, ~2.4 GB)
- Alert rules support for mission-critical windows

### Grafana

Grafana visualizes Prometheus metrics with interactive dashboards.

**Configuration:** `grafana/provisioning/`

**Access:** http://localhost:3000 (default: admin/admin)

**Key Features:**
- Pre-configured Prometheus datasource
- Fullscreen Overview dashboard with real-time tracking
- Mission communication planning visualization

---

## Mission Communication Planning Features

### Satellite Coverage Overlay (Ka/HCX)

The mission communication planning feature adds satellite coverage overlays to Grafana dashboards.

#### Backend Setup

**What it does:**
- Converts HCX KMZ (Ka satellite coverage) to GeoJSON on startup
- Serves coverage data via HTTP static files endpoint
- Enables Grafana to fetch coverage polygons across Docker containers

**File location:** `/data/sat_coverage/hcx.geojson`

**Endpoint:** `http://localhost:8000/data/sat_coverage/hcx.geojson`

**Backend code:** `backend/starlink-location/main.py`
- StaticFiles mount: Exposes `/data/sat_coverage/` directory
- HCX initialization: Converts HCX.kmz → GeoJSON during startup
- See logs: "HCX coverage loaded: 4 regions"

#### Grafana Dashboard Configuration

**Dashboard:** Fullscreen Overview (`monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`)

**Layer: Satellite Coverage Overlay**

1. **Panel Type:** Geomap
2. **Data Source:** URL endpoint
3. **URL:** `http://localhost:8000/data/sat_coverage/hcx.geojson`
4. **Layer Type:** GeoJSON overlay
5. **Styling:**
   - Fill opacity: 20-30% (semi-transparent)
   - Colors by Ka region:
     - AOR (Atlantic Ocean Region): Light green
     - POR (Pacific Ocean Region): Light blue
     - IOR (Indian Ocean Region): Light orange
6. **Display Name:** "Ka Satellite Coverage (HCX)"

**Alternative: If using Grafana plugin for KMZ/polygon visualization**
- Install: `grafana-geomap-panel` (usually pre-installed)
- Configure polygon styling in layer panel options
- Test by activating a mission and viewing map

#### Verification Steps

**1. Backend endpoint is accessible:**
```bash
curl http://localhost:8000/data/sat_coverage/hcx.geojson | jq '.type'
# Expected output: "FeatureCollection"
```

**2. GeoJSON has valid coverage data:**
```bash
curl http://localhost:8000/data/sat_coverage/hcx.geojson | jq '.features | length'
# Expected output: 4 (four Ka regions)
```

**3. Grafana can render the overlay:**
- Navigate to Fullscreen Overview dashboard
- Verify map panel displays coverage polygons
- Polygons should not overlap waypoint markers
- Opacity should be ~20-30% (semi-transparent)

#### Common Issues & Troubleshooting

**Issue: Coverage polygons not visible on map**
- ✓ Verify backend endpoint returns 200 OK: `curl -I http://localhost:8000/data/sat_coverage/hcx.geojson`
- ✓ Check Grafana panel data source URL is exactly: `http://localhost:8000/data/sat_coverage/hcx.geojson`
- ✓ Verify panel layer type is "GeoJSON overlay" (not "Points" or other)
- ✓ Check browser console for CORS errors (should be none - CORS enabled by default)
- ✓ Reload Grafana dashboard (Ctrl+R or Cmd+R)

**Issue: Polygons are too opaque or too transparent**
- Adjust opacity in Geomap panel settings
- Recommended: 20-30% opacity for visibility without obscuring map

**Issue: Endpoint returns 404 "Not Found"**
- ✓ Verify Docker container is running: `docker compose ps`
- ✓ Check backend startup logs: `docker compose logs starlink-location | grep -i hcx`
- ✓ Verify HCX.kmz file exists: `docker exec starlink-location ls app/satellites/assets/HCX.kmz`
- ✓ Check file was converted: `docker exec starlink-location ls -lah /app/data/sat_coverage/`

**Issue: "HCX coverage loaded: 0 regions" in logs**
- KMZ conversion failed; check for errors in logs
- Try rebuilding: `docker compose down && docker compose build --no-cache && docker compose up -d`

---

## Mission Timeline Panel Setup

### Overview

The mission timeline panel displays a comprehensive timeline of communication status across the mission's flight duration, showing nominal, degraded, and critical windows for each satellite transport (X-Band, Ka, Ku).

### Panel Configuration

**Panel Type:** State Timeline (or Table, depending on Grafana version)

**Data Source:** Prometheus

**Key Metrics Used:**
- `mission_timeline_segment_status` - Status of each timeline segment (nominal/degraded/critical)
- `mission_timeline_segment_duration_seconds` - Duration of each segment
- `mission_next_conflict_seconds` - Time until next degradation event
- `mission_critical_seconds` - Total critical window duration

### Adding the Mission Timeline Panel to Fullscreen Overview

1. **Navigate to dashboard edit mode:**
   - Open Grafana: http://localhost:3000
   - Go to Fullscreen Overview dashboard
   - Click "Edit" (pencil icon)

2. **Add new panel:**
   - Click "Add panel"
   - Select "State Timeline" visualization
   - Assign a unique panel ID (avoid conflicts with existing panels)

3. **Configure data source:**
   - Data source: Prometheus
   - Query:
     ```promql
     mission_timeline_segment_status{mission_id="$active_mission"}
     ```

4. **Panel options:**
   - **Title:** "Mission Timeline - Communication Status"
   - **Time range:** Custom (mission duration)
   - **Legend:** Show transport names (X-Band, Ka, Ku)
   - **Thresholds:**
     - 0 = Nominal (green)
     - 1 = Degraded (yellow)
     - 2 = Critical (red)

5. **Save dashboard:**
   - Click "Save" → "Save dashboard"
   - Export JSON to: `grafana/provisioning/dashboards/fullscreen-overview.json`

### Interpreting Timeline Colors

- **Green:** Nominal communication (all transports available)
- **Yellow:** Degraded communication (one transport unavailable or limited)
- **Red:** Critical communication (two or more transports unavailable simultaneously)

---

## Prometheus Alert Rules

Alert rules are configured in `prometheus/rules/` (if present).

### Mission Communication Alerts

**Rules configured:**
- `MissionDegradedWindowApproaching` - Fires when degraded window <15 min away
- `MissionCriticalWindowApproaching` - Fires when critical window <15 min away

**Validation:**
```bash
docker compose exec prometheus promtool check rules /etc/prometheus/rules/mission-alerts.yml
```

**Alert Configuration File:** `prometheus/rules/mission-alerts.yml`

**How to Test Alerts:**
1. Create a test mission with known degraded/critical windows
2. Activate the mission
3. Monitor Prometheus Alerts page: http://localhost:9090/alerts
4. Verify alerts appear as window approaches (<15 min)

---

## Dashboard Layer Management

### Overview

The Fullscreen Overview dashboard contains multiple visualization layers for mission communication planning. Each layer displays different aspects of the mission and satellite status.

### Layer Types

#### 1. Position & Heading (Geomap)

**What it shows:**
- Current position (green plane icon)
- Heading direction (arrow orientation)
- Position history (blue trail)

**Configuration:**
- Data source: Prometheus
- Queries:
  - `starlink_dish_latitude_degrees` (Y-axis)
  - `starlink_dish_longitude_degrees` (X-axis)
  - `starlink_dish_heading_degrees` (rotation)

#### 2. Satellite Coverage Overlay (Geomap)

**What it shows:**
- Ka satellite coverage regions (AOR, POR, IOR)
- Semi-transparent polygons at 20-30% opacity
- Color-coded by region for easy identification

**Configuration:**
- Data source: URL endpoint
- URL: `http://localhost:8000/data/sat_coverage/hcx.geojson`
- Layer type: GeoJSON overlay
- Styling: Region-based colors with opacity

**Managing Layer Visibility:**
1. In Grafana, click the layer menu (icon in top right of map panel)
2. Toggle individual layers on/off
3. Reorder layers using drag-and-drop
4. Adjust opacity using layer options

#### 3. Mission POIs & Markers (Geomap)

**What it shows:**
- AAR (Autonomous Arrival Recovery) window locations
- X-Band transition points
- Ka coverage boundary crossing points

**Configuration:**
- Data source: Prometheus via `/api/pois?mission_id=<active_mission_id>&category=mission-event`
- Marker types: Flag (AAR), Transition icon (X-Band), Boundary marker (Ka)

**Managing Markers:**
1. Click marker to see details (time, status, transport)
2. Hover for tooltip information
3. Filter by category using dashboard variables

#### 4. Network Metrics Panel

**What it shows:**
- Real-time latency (ms)
- Throughput down/up (Mbps)
- Obstructions (%)

**Configuration:**
- Data source: Prometheus
- Update interval: Real-time (1 second)

### Customizing Layers

**To modify layer order:**
1. Edit dashboard (pencil icon)
2. In Geomap panel, use "Layer" dropdown menu
3. Drag layers to reorder
4. Save dashboard

**To adjust layer opacity:**
1. Edit dashboard
2. Click on layer in Geomap options
3. Adjust "Fill opacity" slider (0-100%)
4. Save dashboard

**To add new layers:**
1. Edit dashboard
2. In Geomap panel → Add new layer
3. Configure data source and styling
4. Test visibility and overlap
5. Save dashboard

**To hide/show layers dynamically:**
- Use Grafana dashboard variables (e.g., `$show_coverage`)
- Configure variable to filter data or toggle layer visibility
- Add variable picker to dashboard top bar

### Exporting Dashboard Configuration

**After making changes:**
```bash
# Navigate to dashboard settings (gear icon)
# Click "Edit JSON"
# Copy entire JSON
# Paste into: monitoring/grafana/provisioning/dashboards/fullscreen-overview.json
# Commit changes
```

---

## Dashboard Management

### Fullscreen Overview

**File:** `grafana/provisioning/dashboards/fullscreen-overview.json`

**Panels:**
- Position & heading (Geomap)
- Network metrics (latency, throughput)
- Obstructions (bar chart)
- POI table with ETAs
- **NEW: Satellite coverage overlay (Geomap)**
- **NEW: Mission timeline (State Timeline)**
- **NEW: AAR/transition markers (Geomap)**

### Adding New Panels

1. Open Grafana dashboard in edit mode
2. Click "Add panel" → select visualization type
3. Configure data source (Prometheus or URL endpoint)
4. Save dashboard
5. Export dashboard JSON to `grafana/provisioning/dashboards/`
6. Commit with descriptive message

---

## Performance Tuning

### Prometheus

- **Scrape interval:** Currently 1 second (very detailed)
- **Retention:** Set by `PROMETHEUS_RETENTION` in `.env`
- **Storage:** ~2.4 GB for 1 year retention

To reduce data volume:
```bash
# In .env
PROMETHEUS_RETENTION=30d  # Instead of 1y
```

### Grafana

- **Update interval:** Configurable per panel
- **Plugin performance:** Geomap plugin is lightweight
- **Query optimization:** Use variable filters to reduce dataset size

---

## Troubleshooting Common Display Issues

### Mission Timeline Panel Not Showing Data

**Symptoms:**
- Mission Timeline panel is empty or shows "No data"
- Timeline exists but segments not visible

**Diagnosis:**
1. Verify mission is activated: `curl http://localhost:8000/api/missions/active`
2. Check Prometheus metrics available:
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=mission_timeline_segment_status'
   ```
3. Verify metric has correct labels (mission_id, transport)

**Solutions:**
- Ensure mission was activated (not just saved): Status should show "Active"
- Recompute timeline if recent changes: Deactivate → Activate mission
- Check backend logs: `docker compose logs starlink-location | grep -i timeline`
- Verify test data exists: Create new test mission with explicit transitions

### Satellite Coverage Not Rendering

**Symptoms:**
- Coverage overlay not visible despite being enabled
- GeoJSON loads but polygons don't appear

**Diagnosis:**
1. Check endpoint: `curl -I http://localhost:8000/data/sat_coverage/hcx.geojson`
2. Verify GeoJSON validity: `curl http://localhost:8000/data/sat_coverage/hcx.geojson | jq '.type'`
3. Check panel configuration in Grafana

**Solutions:**
- If endpoint returns 404: Rebuild Docker container
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```
- If GeoJSON is invalid: Check HCX.kmz conversion logs
  ```bash
  docker compose logs starlink-location | grep -i "hcx\|coverage"
  ```
- Verify panel type is "Geomap" with GeoJSON layer
- Check fill opacity is not set to 0%

### Alerts Not Firing

**Symptoms:**
- Mission has degraded/critical window but no alerts appear
- Alert rules show as inactive in Prometheus

**Diagnosis:**
1. Verify rules are loaded:
   ```bash
   docker compose exec prometheus promtool check rules /etc/prometheus/rules/mission-alerts.yml
   ```
2. Check if metrics are being scraped:
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=mission_next_conflict_seconds'
   ```
3. Monitor Prometheus: http://localhost:9090/alerts

**Solutions:**
- Ensure metrics are being exported by backend
  - Verify mission activation creates metrics
  - Check backend endpoint: `curl http://localhost:8000/metrics | grep mission_`
- If rules syntax invalid, fix `prometheus/rules/mission-alerts.yml`
- Reload Prometheus rules:
  ```bash
  docker compose restart prometheus
  ```
- Test with manual query:
  ```
  mission_next_conflict_seconds{status="degraded"} < 900
  ```

### Dashboard Panels Overlapping or Misaligned

**Symptoms:**
- Multiple layers obscure each other
- Map markers not visible due to overlap
- Coverage polygons hide POI markers

**Solutions:**
1. **Adjust layer order:**
   - Edit dashboard (pencil icon)
   - Click Geomap panel
   - In "Layers" section, drag to reorder
   - Place coverage overlays behind POI markers

2. **Adjust opacity:**
   - Coverage overlay: 20-30% opacity (semi-transparent)
   - POI markers: 100% opacity (opaque)
   - Network metrics: 80% opacity (slightly transparent)

3. **Use layer filtering:**
   - Create dashboard variable: `$visible_layers`
   - Filter which layers display based on time of day or mission phase
   - Hide non-essential layers during critical operations

### Performance Issues (Slow Dashboard Load)

**Symptoms:**
- Grafana dashboard takes >5 seconds to load
- Maps lag when panning/zooming
- Metrics slow to update

**Diagnosis:**
1. Check Prometheus query performance:
   - Grafana → Preferences → Query history
   - Note slow queries (>1s response time)
2. Monitor backend throughput:
   ```bash
   docker compose logs starlink-location | grep "request duration"
   ```

**Solutions:**
- Reduce time range for dashboard (e.g., last 24 hours instead of 1 year)
- Optimize Prometheus queries (use metric_relabel_configs to drop unused metrics)
- Reduce scrape interval if safe: `prometheus.yml` → `scrape_interval: 2s` (instead of 1s)
- Disable unused panels (hide via dashboard settings)
- Increase Prometheus memory limit: Edit `docker-compose.yml`

### Mission Data Not Syncing with Prometheus

**Symptoms:**
- Mission activated but metrics not updating in Prometheus
- Dashboard shows stale data
- Metrics scraping appears to stop mid-mission

**Diagnosis:**
1. Check scrape status:
   ```bash
   curl 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[0]'
   ```
2. Verify backend is exporting metrics:
   ```bash
   curl http://localhost:8000/metrics | grep mission_
   ```

**Solutions:**
- Restart Prometheus scraper:
  ```bash
  docker compose restart prometheus
  ```
- Verify backend metrics endpoint:
  ```bash
  curl http://localhost:8000/health
  ```
- Check for DNS/network issues (Docker container connectivity)
- Rebuild if metrics not present after backend changes:
  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```

---

## Documentation References

- **Mission Planning Guide:** `docs/MISSION-PLANNING-GUIDE.md`
- **Mission Communication SOP:** `docs/MISSION-COMM-SOP.md`
- **Metrics Reference:** `docs/METRICS.md`
- **Design Document:** `docs/design-document.md`
- **CLAUDE.md:** Project conventions and Docker rebuild workflow
