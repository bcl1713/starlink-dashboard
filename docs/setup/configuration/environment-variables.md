# Environment Variables

[Back to Configuration Guide](./README.md)

---

## Complete Reference

All configuration is done via the `.env` file in the project root.

| Variable                          | Default         | Description              | Mode       |
| --------------------------------- | --------------- | ------------------------ | ---------- |
| `STARLINK_MODE`                   | `simulation`    | `simulation` or `live`   | Both       |
| `STARLINK_DISH_HOST`              | `192.168.100.1` | Dish IP address          | Live       |
| `STARLINK_DISH_PORT`              | `9200`          | Dish gRPC port           | Live       |
| `PROMETHEUS_RETENTION`            | `1y`            | Data retention period    | Both       |
| `STARLINK_LOCATION_PORT`          | `8000`          | Backend port             | Both       |
| `PROMETHEUS_PORT`                 | `9090`          | Prometheus port          | Both       |
| `LOG_LEVEL`                       | `INFO`          | Backend log level        | Both       |
| `JSON_LOGS`                       | `true`          | JSON log format          | Both       |
| `STARLINK_GROUND_ENTRY_LATITUDE`  | none            | Simulation GEP Latitude  | Simulation |
| `STARLINK_GROUND_ENTRY_LONGITUDE` | none            | Simulation GEP Longitude | Simulation |

---

## Operating Mode

### STARLINK_MODE

Controls whether the system connects to real hardware or uses simulation.

**Values:**

- `simulation` - Generate realistic test data (default)
- `live` - Connect to real Starlink terminal

**Example:**

```bash
# Development/testing
STARLINK_MODE=simulation

# Production monitoring
STARLINK_MODE=live
```

---

## Connection Settings

### STARLINK_DISH_HOST

IP address of the Starlink terminal (live mode only).

**Default:** `192.168.100.1`

**Example:**

```bash
# Standard Starlink IP
STARLINK_DISH_HOST=192.168.100.1

# Custom network configuration
STARLINK_DISH_HOST=192.168.1.100
```

### STARLINK_DISH_PORT

gRPC port for Starlink terminal communication (live mode only).

**Default:** `9200`

**Example:**

```bash
STARLINK_DISH_PORT=9200
```

---

## Service Ports

### STARLINK_LOCATION_PORT

Port for the backend API service.

**Default:** `8000`

**Access:** `http://localhost:8000`

### PROMETHEUS_PORT

Port for Prometheus metrics collector.

**Default:** `9090`

**Access:** `http://localhost:9090`

**Example:**

```bash
# Change ports to avoid conflicts
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091
```

---

## Storage Settings

### PROMETHEUS_RETENTION

How long Prometheus retains metrics data.

**Default:** `1y` (one year, ~2.4 GB)

**Common values:**

- `1y` - One year (~2.4 GB)
- `90d` - 90 days (~600 MB)
- `30d` - 30 days (~200 MB)
- `15d` - 15 days (~100 MB)
- `7d` - 7 days (~50 MB)

**Example:**

```bash
# Development: minimal storage
PROMETHEUS_RETENTION=7d

# Production: long-term analysis
PROMETHEUS_RETENTION=1y
```

---

## Operational Clock Settings

Configure operational clocks in Mission Planner's Configuration page. The
backend persists them in its application settings data. Mission activation may
supply departure and arrival clock locations; these settings do not use
`TIMEZONE_TAKEOFF` or `TIMEZONE_LANDING` environment variables.

See [Overview features](../../features/overview.md) for clock behavior.

---

## Logging Settings

### LOG_LEVEL

Controls verbosity of backend logs.

**Default:** `INFO`

**Values:**

- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages (recommended)
- `WARNING` - Warning messages only
- `ERROR` - Error messages only
- `CRITICAL` - Critical errors only

**Example:**

```bash
# Development: verbose logging
LOG_LEVEL=DEBUG

# Production: standard logging
LOG_LEVEL=INFO

# Quiet: errors only
LOG_LEVEL=ERROR
```

### JSON_LOGS

Whether to format logs as JSON (machine-readable) or plain text
(human-readable).

**Default:** `true`

**Example:**

```bash
# Machine-readable (production)
JSON_LOGS=true

# Human-readable (development)
JSON_LOGS=false
```

### STARLINK_GROUND_ENTRY_LATITUDE and STARLINK_GROUND_ENTRY_LONGITUDE

Provide a fixed local GEP only for simulation/offline use. Must be provided
together. Simulation will not perform public-IP/GEP discovery.

When either value is absent or invalid, no GEP is configured: `/api/status`
returns `ground_entry_point: null` and the Overview shows `GEP unavailable`.

These coordinates are a configured ground-entry location proxy. They are not
live terminal, aircraft, or satellite telemetry.

**Backend default:** unset (no GEP). The repository `.env.example` provides
sample simulation coordinates; replace or remove both values together as needed.

**Example:**

```bash
STARLINK_GROUND_ENTRY_LATITUDE="41.2565"
STARLINK_GROUND_ENTRY_LONGITUDE="-95.9345"
```

---

## Applying Changes

After editing `.env`:

```bash
# Restart services
docker compose down
docker compose up -d

# Verify changes took effect
curl http://localhost:8000/health
docker compose logs | rg -i "config\|environment"
```

---

[Back to Configuration Guide](./README.md)
