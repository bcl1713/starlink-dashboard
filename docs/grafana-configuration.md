# Grafana Configuration and Troubleshooting

Configuration, security, and troubleshooting guide for Grafana dashboards.

## React overview and Grafana dual-run

`/overview` is the canonical React operator view for day-to-day operations.
Grafana remains deployed and supported at <http://localhost:3000> as the
dual-run fallback for existing dashboards and functions not explicitly verified
as equivalent in React. Use the overview first for its operational map,
telemetry, monitoring history, clocks, and controls; use Grafana for its
existing dashboard-specific workflows or as the immediate fallback when the
overview is interrupted. There is no Grafana retirement date in this change.

For a React monitoring, radar, or CSP issue, preserve the safe HTTP status and
timestamp, then follow the
[operations overview troubleshooting](./operations-overview.md#troubleshooting-and-escalation).
For Grafana-specific datasource or dashboard diagnosis, retain the procedures
below. During rollback, keep Grafana and Prometheus volumes intact and direct
operators to Grafana while the overview change is reverted.

## Configuration

### Environment Variables

Set in `.env` file:

```bash
GRAFANA_ADMIN_PASSWORD=secure_password  # Change default admin password
TIMEZONE_TAKEOFF=America/Los_Angeles    # Timezone for takeoff location
TIMEZONE_LANDING=Europe/London           # Timezone for landing location
```

### Time Range Configuration

All dashboards support customizable time ranges:

- Default: Last 5 minutes
- Auto-refresh: 5-second interval
- Configurable via dashboard settings

### Data Source Configuration

Prometheus datasource configuration:

- **URL:** `<http://prometheus:9090`>
- **Scrape Interval:** 10 seconds
- **Retention:** 15 days (configurable via `PROMETHEUS_RETENTION`)
- **Auto-configured:** Via provisioning

---

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

---

## API Endpoints

The backend provides these endpoints for integration:

### Metrics Export

- **GET** `/metrics` - Prometheus-format metrics
- **GET** `/health` - Service health check
- **GET** `/route.geojson` - Route data in GeoJSON format

### Control Endpoints

- **GET** `/api/config` - Current configuration
- **POST** `/api/sim/start` - Start simulation
- **POST** `/api/sim/stop` - Stop simulation
- **POST** `/api/sim/reset` - Reset simulation state

---

## Troubleshooting

### Dashboards Not Loading

**Problem:** Dashboards appear empty or show "No data"

**Solutions:**

1. Verify Prometheus connection: Settings → Data Sources → Prometheus → Test
2. Check backend metrics are being generated:
   `curl <http://localhost:8000/metrics`>
3. Verify Prometheus is scraping: `<http://localhost:9090/targets`>
4. Restart Grafana: `docker compose restart grafana`

### Metrics Not Updating

**Problem:** Dashboard panels show old data or frozen values

**Solutions:**

1. Check auto-refresh is enabled (not paused)
2. Verify 5-second auto-refresh interval is set
3. Check backend service is running: `docker compose ps`
4. Review backend logs: `docker compose logs starlink-location`

### Fullscreen Overview Map or Aircraft Marker

**Basemap:** Fullscreen Overview uses the keyless ArcGIS World Imagery
MapServer/XYZ basemap. The panel includes Esri attribution and does not depend
on CARTO or an API key. A gray map can therefore indicate failed external tile
loading, but it is separate from whether the aircraft marker is present.

**Current Position verification:** The Current Position panel needs a current,
reported latitude, longitude, and heading. Grafana joins those values into one
current frame and renders one plane marker; its rotation comes from the joined
heading value. Confirm that all three telemetry series return current values
before treating a missing marker as a map-tile issue:

```bash
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=starlink_dish_latitude_degrees'
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=starlink_dish_longitude_degrees'
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=starlink_dish_heading_degrees'
```

**When the position changes but no marker appears:** Treat this as a visual or
dashboard-configuration investigation, not as a reason to alter simulation
telemetry. Work through the following checks:

1. In Fullscreen Overview, inspect the **Current Position** panel and its marker
   layer. It must use the joined current frame for latitude, longitude,
   altitude, and heading, rather than a raw latitude-only frame.
2. Confirm Grafana provisioning loaded
   `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`, then
   reload the provisioned dashboard or restart Grafana if the deployed version
   is stale.
3. Open the browser developer console and network panel. Resolve JavaScript,
   panel, tile, and CORS errors before changing backend or simulator behavior.
4. Pan or zoom the map and refresh the page to distinguish a tile-load problem
   from a marker-layer problem.

**Weather layer scope:** Weather Radar (RainViewer) is a separate,
deployment-safe layer. It was not changed as part of the ArcGIS basemap and
Current Position marker update.

### High Latency or Slow Responsiveness

**Problem:** Dashboards are sluggish or panels take time to load

**Solutions:**

1. Reduce time range (select shorter time window)
2. Increase auto-refresh interval (5s → 10s)
3. Close other dashboards not in use
4. Check system resources: `docker stats`
5. Verify Prometheus isn't under heavy load

---

## Support and Issue Reporting

For issues, errors, or feature requests:

1. Check the troubleshooting section above
2. Review service logs: `docker compose logs`
3. Report issues on GitHub with:
   - Dashboard UID and panel name
   - Time range and error message
   - Environment details (SIMULATION_MODE, etc.)
   - Steps to reproduce

---

## Related Documentation

- **Design Document:** `docs/design-document.md`
- **Development Plan:** `docs/development-plan.md`
- **Main README:** `README.md`
- **Prometheus:** <http://localhost:9090>
- **Grafana Docs:** <https://grafana.com/docs/>

---

**Version:** 1.0 **Last Updated:** October 2025 **Status:** Production Ready
