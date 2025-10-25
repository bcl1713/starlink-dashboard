# Grafana Dashboard Setup and Usage Guide

## Overview

This document provides guidance on using the Starlink monitoring dashboards in Grafana. The system includes three complementary dashboards that provide real-time monitoring of your Starlink terminal's performance, network metrics, and positioning data.

## Accessing Grafana

### Default Access
- **URL:** http://localhost:3000
- **Default Username:** admin
- **Default Password:** admin (change in production!)

### Environment Configuration
Set the following environment variables in `.env` for customization:
```bash
GRAFANA_ADMIN_PASSWORD=secure_password  # Change default admin password
TIMEZONE_TAKEOFF=America/Los_Angeles    # Timezone for takeoff location
TIMEZONE_LANDING=Europe/London           # Timezone for landing location
```

## Dashboard Overview

### 1. **Starlink Overview** (Primary Dashboard)
**UID:** `starlink-overview`

The main dashboard providing a high-level view of terminal operations:

#### Map Panel
- **Live Position Map:** Displays current terminal position on OpenStreetMap
- Route overlay from `/route.geojson` endpoint
- Current location marker
- Click the map controls to zoom, measure, or toggle fullscreen

#### POI/ETA Table
- Shows upcoming Points of Interest (POIs)
- Displays distance to each POI in meters
- Shows estimated time of arrival (ETA) in seconds
- Updates every 5 seconds based on current speed and position

#### Key Metrics
- **Network Latency:** Gauge with color coding (green <80ms, yellow 80-120ms, red >120ms)
- **Dish Obstruction:** Percentage of dish blocked (green <5%, yellow 5-15%, red >15%)
- **Throughput:** Combined download/upload speed graph
- **Speed:** Current velocity in knots
- **Heading:** Current direction (0°=North, 90°=East, 180°=South, 270°=West)
- **Altitude:** Current elevation in meters
- **Connection Status:** Indicator showing connected/outage state

#### Navigation
- Links at the top allow quick switching to other dashboards
- Simulation mode indicator shown at the top (orange banner when active)

### 2. **Network Metrics** (Detailed Network Performance)
**UID:** `starlink-network`

Deep-dive analysis of network performance:

#### Latency Analysis
- Current, minimum, maximum, and average latency (5-minute window)
- Time series visualization with threshold lines at 80ms and 120ms
- Color coding: green (good), yellow (acceptable), red (poor)

#### Throughput Analysis
- **Combined View:** Download (blue) and upload (green) on same graph
- **Download Detailed:** Separate detailed view with thresholds (red <50, yellow 50-100, green >100 Mbps)
- **Upload Detailed:** Separate detailed view with thresholds (red <10, yellow 10-20, green >20 Mbps)

#### Reliability Metrics
- **Packet Loss:** Percentage of lost packets (threshold: 2% yellow, 5% red)
- **Obstruction:** Time series of dish obstruction percentage
- **Outage Events:** Step graph showing connection disruptions (green=connected, red=outage)
- **Signal Quality:** Percentage indicator (70% yellow, 85% green)

All panels include min/max/mean statistics in legends for quick reference.

### 3. **Position & Movement** (Detailed Positioning)
**UID:** `starlink-position`

Comprehensive position and movement tracking:

#### Large Map Display
- Full-width map panel for detailed position visualization
- Route overlay and POI markers
- Zoom controls and fullscreen capability

#### Current Position Metrics
- **Latitude:** Current latitude (6 decimal places ≈ 0.1 meter precision)
- **Longitude:** Current longitude (6 decimal places ≈ 0.1 meter precision)
- **Altitude:** Current elevation in meters
- **Speed:** Current velocity in knots

#### Position History Route
- **Historical Route with Altitude Coloring:** The "Position History Route" layer displays the terminal's complete movement path with altitude-based color coding
- Route colors indicate elevation: cool colors (green) for low altitude, warm colors (red) for high altitude
- Hover over any point on the route to see detailed telemetry data:
  - **Position:** Latitude, longitude at that point in time
  - **Altitude:** Elevation in meters
  - **Speed:** Velocity in knots at that moment
  - **Heading:** Direction (0°=North, 90°=East, 180°=South, 270°=West)
  - **Network Metrics:** Latency (ms) and upload/download throughput (Mbps) at that time
  - **Obstructions:** Percentage of dish obstruction at that point
- Use the "History Window" dropdown (top-left of dashboard) to select different time ranges:
  - 6 hours, 12 hours, 24 hours (default), 3 days, 7 days, 15 days (maximum)
- The route automatically updates when you change the time window
- Current position marker (plane icon) always appears on top of the historical route

#### Movement History
- **Altitude Over Time:** Graph showing altitude variations during flight
- **Speed Over Time:** Graph showing velocity changes
- **Heading Over Time:** Graph showing direction changes (0-360°)

All time series include min/max/mean/last statistics for analysis.

**Position History Features:**
- Data is sampled at 10-second intervals for optimal performance and to balance detail with responsiveness
- All historical points are connected as a single continuous route
- Data gaps (e.g., when terminal is offline) are interpolated with straight lines
- Color gradient auto-scales based on the altitude range in the current dataset
- For example, if your dataset has altitudes from 0-100m, the scale adjusts to show that range; if it's 500-800m, the scale adjusts accordingly

## Configuration and Customization

### Time Range Selection

All dashboards support multiple time range presets:
- **5 seconds** to **1 day** options
- **Default:** Last 5 minutes
- **Auto-Refresh:** 5-second interval (configurable via dashboard settings)

To change time range:
1. Click the time range selector (top-right corner)
2. Choose a preset or enter custom range
3. Press "Apply time range"

### Dashboard Refresh Settings

To adjust auto-refresh:
1. Click the refresh icon (circular arrow, top-right)
2. Select desired interval or toggle "Pause" to stop refreshing
3. All panels will respect the chosen interval

### Metrics Data Source

All dashboards query Prometheus at `http://prometheus:9090`:
- **Scrape Interval:** 10 seconds (optimized for Starlink metrics)
- **Retention:** 15 days (configurable via `PROMETHEUS_RETENTION`)
- **Datasource:** Auto-configured via provisioning

To verify datasource connection:
1. Click the gear icon (settings, bottom-left)
2. Select "Data Sources"
3. Click "Prometheus"
4. Click "Save & Test"

## Simulation Mode

When `SIMULATION_MODE=true` in `.env`:

### Simulated Data Behavior
- All metrics are generated with realistic patterns
- Position moves along a circular or KML-defined route
- Speed varies between 150-250 knots with smooth transitions
- Latency oscillates between 40-120ms
- Occasional outages and obstruction events injected (1-5% probability)

### Identifying Simulation Mode
- **⚠️ SIMULATION MODE ACTIVE** banner displayed at top of Overview dashboard
- Orange/yellow coloring on the banner
- All metrics behave realistically but are not from actual hardware

### Switching Modes
1. Set `SIMULATION_MODE=false` in `.env` to connect to real hardware
2. Requires network access to Starlink dish at `192.168.100.1:9200`
3. Restart services: `docker compose restart`
4. Dashboards automatically reflect real hardware metrics

## Troubleshooting

### Dashboards Not Loading
**Problem:** Dashboards appear empty or show "No data"

**Solutions:**
1. Verify Prometheus connection: Settings → Data Sources → Prometheus → Test
2. Check backend metrics are being generated: `curl http://localhost:8000/metrics`
3. Verify Prometheus is scraping: `http://localhost:9090/targets`
4. Restart Grafana: `docker compose restart grafana`

### Metrics Not Updating
**Problem:** Dashboard panels show old data or frozen values

**Solutions:**
1. Check auto-refresh is enabled (not paused)
2. Verify 5-second auto-refresh interval is set
3. Check backend service is running: `docker compose ps`
4. Review backend logs: `docker compose logs starlink-location`

### Map Panel Not Displaying
**Problem:** Geomap shows gray background without map tiles

**Solutions:**
1. Verify internet connectivity (tiles load from OpenStreetMap)
2. Try zooming in/out or panning
3. Refresh the page (Ctrl+R or Cmd+R)
4. Check browser console for CORS errors
5. Verify route endpoint available: `curl http://localhost:8000/route.geojson`

### High Latency or Slow Responsiveness
**Problem:** Dashboards are sluggish or panels take time to load

**Solutions:**
1. Reduce time range (select shorter time window)
2. Increase auto-refresh interval (5s → 10s)
3. Close other dashboards not in use
4. Check system resources: `docker stats`
5. Verify Prometheus isn't under heavy load

## Performance Metrics and Thresholds

### Network Performance
| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|-----------|------|
| **Latency** | <40ms | 40-80ms | 80-120ms | >120ms |
| **Download** | >150 Mbps | 100-150 Mbps | 50-100 Mbps | <50 Mbps |
| **Upload** | >25 Mbps | 20-25 Mbps | 10-20 Mbps | <10 Mbps |
| **Packet Loss** | 0% | <1% | 1-2% | >2% |

### Dish Health
| Metric | Good | Caution | Poor |
|--------|------|---------|------|
| **Obstruction** | <5% | 5-15% | >15% |
| **Signal Quality** | >85% | 70-85% | <70% |

## Advanced Features

### Dashboard Navigation
- Dashboard links at the top of each dashboard allow quick switching
- Navigation history preserved if "Keep Time" option selected
- Each dashboard can be bookmarked for quick access

### Fullscreen Mode
- Click fullscreen icon (top-right of any panel) for focused view
- Press 'Esc' to exit fullscreen
- Useful for large monitors or presentation mode

### Export and Sharing
- Dashboard JSON can be exported for backup or sharing
- Settings → Dashboard Settings → Export
- Import via + icon → Import → Paste JSON

### Custom Annotations
- Add manual markers to charts (e.g., "Throttling Event")
- Click and drag on time series, or use Annotations API
- Useful for correlating external events with metrics

## Security Considerations

### Default Credentials
⚠️ **IMPORTANT:** Change default admin password before deploying:
```bash
# In .env
GRAFANA_ADMIN_PASSWORD=YourSecurePasswordHere
# Then restart
docker compose restart grafana
```

### Network Access
- Restrict access to Grafana port 3000 in production
- Use reverse proxy (nginx, Caddy) for external access
- Implement authentication (OAuth, SAML, etc.) for multi-user access

### Data Retention
- Prometheus retains metrics for 15 days by default
- Adjust `PROMETHEUS_RETENTION` in `.env` for different retention:
  ```bash
  PROMETHEUS_RETENTION=30d  # 30 days
  PROMETHEUS_RETENTION=365d # 1 year
  ```

## API Endpoints

The backend provides these endpoints for integration:

### Metrics Export
- **GET** `/metrics` - Prometheus-format metrics
- **GET** `/health` - Service health check
- **GET** `/route.geojson` - Route data in GeoJSON format

### Configuration
- **GET** `/api/config` - Current configuration
- **POST** `/api/sim/start` - Start simulation
- **POST** `/api/sim/stop` - Stop simulation
- **POST** `/api/sim/reset` - Reset simulation state

## Support and Issue Reporting

For issues, errors, or feature requests:
1. Check the troubleshooting section above
2. Review service logs: `docker compose logs`
3. Report issues on GitHub with:
   - Dashboard UID and panel name
   - Time range and error message
   - Environment details (SIMULATION_MODE, etc.)
   - Steps to reproduce

## Related Documentation

- **Design Document:** `docs/design-document.md`
- **Development Plan:** `docs/phased-development-plan.md`
- **Main README:** `README.md`
- **Prometheus:** http://localhost:9090
- **Grafana Docs:** https://grafana.com/docs/

---

**Version:** 1.0
**Last Updated:** October 2025
**Status:** Production Ready
