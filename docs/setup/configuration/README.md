# Configuration Guide

[Back to Setup Guide](../README.md) | [Back to main docs](../../INDEX.md)

---

## Overview

All configuration is done via the `.env` file in the project root. This guide
covers all configuration options for the Starlink Dashboard.

---

## Configuration Topics

- **[Environment Variables](./environment-variables.md)** - Complete .env
  reference
- **[Simulation Mode](./simulation-mode.md)** - Development and testing without
  hardware
- **[Live Mode](./live-mode.md)** - Connect to real Starlink terminal
- **[Performance Tuning](./performance-tuning.md)** - Memory, storage, and
  network optimization
- **[Network Configuration](./network-configuration.md)** - Ports and firewall
  settings
- **[Storage Configuration](./storage-configuration.md)** - Data retention and
  volumes
- **[Logging Configuration](./logging-configuration.md)** - Log levels and
  formats

---

## Quick Start

### Basic Configuration

1. **Copy example environment file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit configuration:**

   ```bash
   nano .env
   ```

3. **Set operating mode:**

   ```bash
   # For development/testing (no hardware)
   STARLINK_MODE=simulation

   # For live monitoring
   STARLINK_MODE=live
   STARLINK_DISH_HOST=192.168.100.1
   ```

4. **Apply changes:**

   ```bash
   docker compose down
   docker compose up -d
   ```

---

## Configuration Examples

### Development Setup

Optimized for local development:

```bash
# .env
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=7d
LOG_LEVEL=DEBUG
JSON_LOGS=false
```

### Production Setup

Optimized for production monitoring:

```bash
# .env
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
PROMETHEUS_RETENTION=1y
GRAFANA_ADMIN_PASSWORD=<strong-password>
LOG_LEVEL=INFO
JSON_LOGS=true
```

### Testing Setup

Minimal resource usage:

```bash
# .env
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=1d
LOG_LEVEL=WARNING
```

---

## Applying Configuration Changes

### Environment Variable Changes

```bash
# 1. Edit .env
nano .env

# 2. Restart affected services
docker compose down
docker compose up -d

# 3. Verify changes
curl http://localhost:8000/health
```

### Configuration File Changes

**For backend config.yaml changes:**

```bash
# Backend Python code changes require full rebuild
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d
```

**For Prometheus config changes:**

```bash
# Edit monitoring/prometheus/prometheus.yml
nano monitoring/prometheus/prometheus.yml

# Restart Prometheus
docker compose restart prometheus

# Verify
curl http://localhost:9090/-/healthy
```

---

## Verification

After configuration changes, verify:

```bash
# 1. Services running
docker compose ps

# 2. Health checks
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health

# 3. Logs for errors
docker compose logs | rg -i error
```

---

## Next Steps

Configuration complete! Proceed to:

- **[API Reference](../../api/README.md)** - Explore endpoints
- **[Route Management](../../../CLAUDE.md#route-management)** - Upload routes
- **[Troubleshooting](../../troubleshooting/README.md)** - Common issues

---

[Back to Setup Guide](../README.md) | [Back to main docs](../../INDEX.md)
