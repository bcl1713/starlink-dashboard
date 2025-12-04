# Grafana Configuration and Troubleshooting

Configuration, security, and troubleshooting guide for Grafana dashboards.

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

### Map Panel Not Displaying

**Problem:** Geomap shows gray background without map tiles

**Solutions:**

1. Verify internet connectivity (tiles load from OpenStreetMap)
2. Try zooming in/out or panning
3. Refresh the page (Ctrl+R or Cmd+R)
4. Check browser console for CORS errors
5. Verify route endpoint available: `curl <http://localhost:8000/route.geojson`>

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
