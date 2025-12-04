# Simulation Mode Configuration

[Back to Configuration Guide](./README.md)

---

## Overview

**Purpose:** Development, testing, and demonstrations without hardware.

Simulation mode generates realistic Starlink telemetry without requiring a
physical terminal. Perfect for development, testing, and demonstrations.

---

## Basic Configuration

Edit `.env`:

```bash
# Set mode to simulation
STARLINK_MODE=simulation

# Optional: Adjust simulation behavior
# (advanced config in backend/starlink-location/config.yaml)
```

No other configuration required! The simulator starts automatically with default
settings.

---

## Simulated Behavior

The simulator generates realistic Starlink telemetry:

| Metric           | Simulation Behavior                      |
| ---------------- | ---------------------------------------- |
| **Position**     | Circular or route-following movement     |
| **Speed**        | 0-100 knots with realistic variation     |
| **Latency**      | 20-80ms typical, occasional 200ms spikes |
| **Throughput**   | Download 50-200 Mbps, Upload 10-40 Mbps  |
| **Obstructions** | 0-30% with smooth variation              |
| **Altitude**     | 100-10,000 meters                        |

---

## Route Configuration

### Using Default Circular Route

The simulator uses a circular pattern by default. No configuration needed.

**Behavior:**

- Circular movement around a center point
- Realistic speed variations
- Altitude changes
- Network metric variations

### Using Custom KML Route

1. **Place KML file in `/data/sim_routes/`:**

   ```bash
   cp your-route.kml data/sim_routes/my-route.kml
   ```

2. **Restart backend:**

   ```bash
   docker compose restart starlink-location
   ```

3. **Check logs:**

   ```bash
   docker compose logs starlink-location | rg -i "kml|route"
   ```

**What to expect:**

- Simulator follows waypoints in order
- Speed calculated from waypoint timing (if present)
- Position updates every second
- Smooth transitions between waypoints

---

## Testing Simulation Mode

### Verify Simulation is Running

```bash
# Check status
curl http://localhost:8000/api/status | jq '.position'
```

**Expected output:**

```json
{
  "latitude": 40.7128,
  "longitude": -74.006,
  "altitude": 5000.0,
  "heading": 180.5,
  "speed_knots": 67.3
}
```

### Monitor Position Updates

Position should change every second:

```bash
# Watch position changes
watch -n 1 'curl -s http://localhost:8000/api/status | jq .position.latitude'
```

**Expected behavior:**

- Value changes every second
- Smooth progression (no jumps)
- Follows circular or route pattern

### View Metrics

```bash
# View all Starlink metrics
curl http://localhost:8000/metrics | rg starlink_dish_latitude

# Expected output:
# starlink_dish_latitude_degrees 40.7128
```

---

## Advanced Configuration

### Simulation Parameters

For advanced tuning, edit `backend/starlink-location/config.yaml`:

```yaml
simulation:
  update_interval_seconds: 1.0 # How often to update position
  default_speed_knots: 67 # Default cruising speed
  speed_variation_knots: 5 # Random speed variation range
  position_smoothing: true # Smooth position transitions
```

**Apply changes:**

```bash
# Rebuild backend (required for config.yaml changes)
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d
```

### Custom Starting Position

To start at a specific location, modify the simulator initialization in
`backend/starlink-location/app/services/simulation_coordinator.py`.

---

## Troubleshooting

### Position Not Updating

**Symptoms:**

- Position stays the same
- Metrics show stale data

**Solutions:**

1. **Check backend is running:**

   ```bash
   docker compose ps starlink-location
   ```

2. **Check logs for errors:**

   ```bash
   docker compose logs starlink-location | rg -i "error|simulation"
   ```

3. **Restart backend:**

   ```bash
   docker compose restart starlink-location
   ```

4. **Rebuild if needed:**

   ```bash
   docker compose down
   docker compose build --no-cache starlink-location
   docker compose up -d
   ```

### Metrics Not Appearing in Prometheus

**Symptoms:**

- Prometheus shows no data
- Grafana dashboards empty

**Solutions:**

1. **Check backend metrics endpoint:**

   ```bash
   curl http://localhost:8000/metrics | rg starlink_
   ```

2. **Check Prometheus targets:**

   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'
   ```

3. **Verify Prometheus is scraping:**

   ```bash
   docker compose logs prometheus | rg -i "scrape\|target"
   ```

### Unrealistic Data

**Symptoms:**

- Speed too high/low
- Position jumps
- Metrics don't make sense

**Solutions:**

- Check if custom route has timing data
- Verify KML file format is correct
- Review simulation config.yaml parameters
- Restart with default circular route

---

## Best Practices

### Development

```bash
# .env for development
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=7d
LOG_LEVEL=DEBUG
JSON_LOGS=false
```

**Why:**

- Quick iteration
- Verbose logging for debugging
- Minimal storage footprint
- Human-readable logs

### Testing

```bash
# .env for testing
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=1d
LOG_LEVEL=INFO
```

**Why:**

- Predictable behavior
- Automated testing friendly
- Fast cleanup

### Demonstrations

```bash
# .env for demos
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=15d
LOG_LEVEL=INFO
JSON_LOGS=true
```

**Why:**

- Professional log format
- Enough retention for demo review
- Realistic simulation behavior

---

## Next Steps

- **[Live Mode Configuration](./live-mode.md)** - Connect to real hardware
- **[Performance Tuning](./performance-tuning.md)** - Optimize resource usage
- **[Troubleshooting](../../troubleshooting/README.md)** - Common issues

---

[Back to Configuration Guide](./README.md)
