# Getting Started with Starlink Location Backend

[Back to Backend README](../README.md)

---

## Quick Start

### Using Docker Compose

```bash
# Build and start all services
docker compose up -d

# Verify services are running
docker compose ps

# Check backend health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics | head -20

# Get status
curl http://localhost:8000/api/status | jq .

# Access Prometheus
open http://localhost:9090

# Access Grafana
open http://localhost:3000  # admin/admin
```

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Core Endpoints

### `/health` - Health Check

Returns service status, uptime, and mode information.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "uptime_seconds": 123.45,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2024-10-23T16:30:00.000000"
}
```

---

### `/metrics` - Prometheus Metrics

Returns metrics in Prometheus format. Compatible with Prometheus scraping.

```bash
curl http://localhost:8000/metrics
```

Available metrics categories:

- **Position**: latitude, longitude, altitude, speed, heading
- **Network**: latency, throughput (down/up), packet loss
- **Status**: obstruction, signal quality, uptime
- **Counters**: simulation updates, errors

**See:** [API Reference](./API-reference.md) for complete list

---

### `/api/status` - Current Status (JSON)

Returns current telemetry with human-readable fields.

```bash
curl http://localhost:8000/api/status
```

**See:** [API Reference](./API-reference.md#apistatus) for response schema

---

## Configuration

Configuration can be provided via:

1. Environment variables (`STARLINK_*` prefix)
2. `config.yaml` file (default configuration)
3. Configuration API (`/api/config`)

### Essential Environment Variables

```bash
# Operating mode
STARLINK_MODE=simulation          # simulation or live

# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
JSON_LOGS=true                    # Use JSON format for logs
```

**Complete configuration guide:** See
[Configuration Documentation](./CONFIGURATION.md)

---

## Docker

### Build

```bash
docker build -t starlink-location:0.2.0 .
```

### Run

```bash
docker run -p 8000:8000 -e STARLINK_MODE=simulation starlink-location:0.2.0
```

### Health Check

Built-in health check pings `/health` endpoint every 30 seconds.

---

[Back to Backend README](../README.md)
