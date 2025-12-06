# Testing & Tuning Simulation

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
