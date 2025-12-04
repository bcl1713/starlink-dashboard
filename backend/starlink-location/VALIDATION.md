# Starlink Location Backend - Validation Guide

This document provides instructions for validating the Starlink Location Backend
implementation.

## Prerequisites

- Docker and Docker Compose installed
- Access to the project root directory
- curl or similar HTTP client for testing endpoints

## Quick Start Validation

### 1. Build Docker Image

```bash
docker compose build --no-cache starlink-location
```

Expected output:

- Successfully built Docker image
- Image tagged and ready to run

### 2. Start All Services

```bash
docker compose up -d
```

Expected output:

- starlink-location service starts (port 8000)
- prometheus service starts (port 9090)
- grafana service starts (port 3000)

### 3. Verify Services Are Running

```bash
docker compose ps
```

Expected output:

```text
NAME                STATUS
starlink-location   Up (healthy)
prometheus          Up
grafana             Up
```

## API Endpoint Validation

### Root Endpoint

```bash
curl <http://localhost:8000/>
```

Expected response:

```json
{
  "message": "Starlink Location Backend",
  "version": "0.2.0",
  "docs": "/docs",
  "endpoints": {
    "health": "/health",
    "metrics": "/metrics",
    "status": "/api/status",
    "config": "/api/config"
  }
}
```

### Health Endpoint

```bash
curl <http://localhost:8000/health>
```

Expected response:

```json
{
  "status": "ok",
  "uptime_seconds": 10.5,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2024-10-23T16:30:00.000000"
}
```

### Metrics Endpoint

```bash
curl <http://localhost:8000/metrics> | head -50
```

Expected output:

- Prometheus-format metrics
- Contains `starlink_dish_latitude_degrees`
- Contains `starlink_network_latency_ms`
- Contains `starlink_dish_obstruction_percent`
- Contains `simulation_updates_total`

### Status Endpoint

```bash
curl <http://localhost:8000/api/status> | jq .
```

Expected response:

```json
{
  "timestamp": "2024-10-23T16:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "speed": 25.5,
    "heading": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 10.5,
    "temperature_celsius": null
  }
}
```

### Configuration Endpoint - GET

```bash
curl <http://localhost:8000/api/config> | jq .
```

Expected output:

- Complete SimulationConfig JSON
- All sections present (route, network, obstruction, position)

### Configuration Endpoint - POST

```bash
curl -X POST <http://localhost:8000/api/config> \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "simulation",
    "update_interval_seconds": 1.0,
    "route": {"pattern": "circular", "latitude_start": 40.7128, "longitude_start": -74.0060, "radius_km": 100.0, "distance_km": 500.0},
    "network": {"latency_min_ms": 20.0, "latency_typical_ms": 50.0, "latency_max_ms": 80.0, "latency_spike_max_ms": 200.0, "spike_probability": 0.05, "throughput_down_min_mbps": 50.0, "throughput_down_max_mbps": 200.0, "throughput_up_min_mbps": 10.0, "throughput_up_max_mbps": 40.0, "packet_loss_min_percent": 0.0, "packet_loss_max_percent": 5.0},
    "obstruction": {"min_percent": 0.0, "max_percent": 30.0, "variation_rate": 0.5},
    "position": {"speed_min_knots": 0.0, "speed_max_knots": 100.0, "altitude_min_meters": 100.0, "altitude_max_meters": 10000.0, "heading_variation_rate": 5.0}
  }'
```

Expected response: 200 OK with updated configuration

## Prometheus Validation

1. Access Prometheus UI: <http://localhost:9090>

2. Check targets:
   - Navigate to Status > Targets
   - Should show `starlink-location:8000` as UP
   - Scrape interval should be 1s

3. Query metrics:
   - In the query interface, enter: `starlink_dish_latitude_degrees`
   - Should return current values that update every second

4. View target health:
   - Navigate to Status > Targets
   - `starlink-location` should show successful scrapes

## Monitoring Logs

### Backend logs

```bash
docker compose logs -f starlink-location
```

Expected log entries:

- "Initializing Starlink Location Backend..."
- "Configuration loaded: mode=simulation"
- "Simulation coordinator initialized"
- "Background update loop started"
- Periodic status updates every 60 seconds

### Prometheus logs

```bash
docker compose logs -f prometheus
```

Expected log entries:

- Successful scrapes from starlink-location:8000
- Metrics ingestion messages

## Extended Testing (10-minute run)

Run the following to verify stability over time:

```bash
for i in {1..600}; do
  echo "=== Request $i ($(date)) ==="
  curl -s <http://localhost:8000/api/status> | jq '.position.latitude, .network.latency_ms'
  sleep 1
done
```

Expected behavior:

- All requests succeed (HTTP 200)
- Latitude values change smoothly over time (circular route)
- Latency values vary within configured range (20-80ms typical, spikes to 200ms)
- No errors or dropped connections

## Verification Checklist

- [ ] Docker image builds successfully
- [ ] All services start and reach healthy state
- [ ] Root endpoint returns expected response
- [ ] Health endpoint shows "ok" status
- [ ] Metrics endpoint returns valid Prometheus format
- [ ] Status endpoint returns complete telemetry
- [ ] Configuration can be retrieved (GET)
- [ ] Configuration can be updated (POST)
- [ ] Prometheus scrapes metrics successfully (1s interval)
- [ ] Prometheus UI shows target as UP
- [ ] Logs show expected initialization messages
- [ ] Background updates running (visible in logs every 60s)
- [ ] Extended 10-minute test completes without errors
- [ ] Metrics values update over time

## Performance Metrics

Expected baseline performance:

- Health check response: < 10ms
- Status endpoint response: < 50ms
- Metrics endpoint response: < 100ms
- Config endpoint response: < 50ms
- Background update loop: ~0.1s per cycle (10 Hz)
- Memory usage: ~100-150 MB per container
- CPU usage: < 5% idle

## Cleanup

Stop all services:

```bash
docker compose down
```

Remove volumes (data):

```bash
docker compose down -v
```

Remove images:

```bash
docker compose down -v --rmi all
```

---

For troubleshooting common issues, see
[VALIDATION-TROUBLESHOOTING.md](VALIDATION-TROUBLESHOOTING.md).
