# Environment Variables

[Back to Configuration Guide](./README.md)

---

## Complete Reference

All configuration is done via the `.env` file in the project root.

| Variable                 | Default               | Description            | Mode |
| ------------------------ | --------------------- | ---------------------- | ---- |
| `STARLINK_MODE`          | `simulation`          | `simulation` or `live` | Both |
| `STARLINK_DISH_HOST`     | `192.168.100.1`       | Dish IP address        | Live |
| `STARLINK_DISH_PORT`     | `9200`                | Dish gRPC port         | Live |
| `PROMETHEUS_RETENTION`   | `1y`                  | Data retention period  | Both |
| `GRAFANA_ADMIN_PASSWORD` | `admin`               | Grafana password       | Both |
| `STARLINK_LOCATION_PORT` | `8000`                | Backend port           | Both |
| `PROMETHEUS_PORT`        | `9090`                | Prometheus port        | Both |
| `GRAFANA_PORT`           | `3000`                | Grafana port           | Both |
| `TIMEZONE_TAKEOFF`       | `America/Los_Angeles` | Takeoff timezone       | Both |
| `TIMEZONE_LANDING`       | `Europe/London`       | Landing timezone       | Both |
| `LOG_LEVEL`              | `INFO`                | Backend log level      | Both |
| `JSON_LOGS`              | `true`                | JSON log format        | Both |

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

### GRAFANA_PORT

Port for Grafana dashboard interface.

**Default:** `3000`

**Access:** `http://localhost:3000`

**Example:**

```bash
# Change ports to avoid conflicts
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091
GRAFANA_PORT=3001
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

## Security Settings

### GRAFANA_ADMIN_PASSWORD

Password for Grafana admin user.

**Default:** `admin`

**Security note:** Change this in production!

**Example:**

```bash
# Development
GRAFANA_ADMIN_PASSWORD=admin

# Production
GRAFANA_ADMIN_PASSWORD=your-strong-password-here
```

---

## Timezone Settings

### TIMEZONE_TAKEOFF

Timezone for departure location (mission planning).

**Default:** `America/Los_Angeles`

**Example:**

```bash
# West Coast USA
TIMEZONE_TAKEOFF=America/Los_Angeles

# East Coast USA
TIMEZONE_TAKEOFF=America/New_York

# UK
TIMEZONE_TAKEOFF=Europe/London

# Japan
TIMEZONE_TAKEOFF=Asia/Tokyo
```

### TIMEZONE_LANDING

Timezone for arrival location (mission planning).

**Default:** `Europe/London`

**Common timezones:**

- `America/New_York` (EST/EDT)
- `America/Chicago` (CST/CDT)
- `America/Denver` (MST/MDT)
- `America/Los_Angeles` (PST/PDT)
- `Europe/London` (GMT/BST)
- `Asia/Tokyo` (JST)
- `Australia/Sydney` (AEST/AEDT)

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
