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

## Documentation References

- **Mission Planning Guide:** `docs/MISSION-PLANNING-GUIDE.md`
- **Mission Communication SOP:** `docs/MISSION-COMM-SOP.md`
- **Metrics Reference:** `docs/METRICS.md`
- **Design Document:** `docs/design-document.md`
- **CLAUDE.md:** Project conventions and Docker rebuild workflow
