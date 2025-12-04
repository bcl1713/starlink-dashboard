# Simulation Mode Setup

[Back to Configuration Guide](../README.md)

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
