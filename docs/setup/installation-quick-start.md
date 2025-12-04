# Quick Installation

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Overview

For experienced users, here's the fast track to get Starlink Dashboard running
in under 3 minutes.

For detailed step-by-step instructions, see
[Installation Steps](./installation-steps.md).

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/your-repo/starlink-dashboard.git
cd starlink-dashboard

# Set up environment
cp .env.example .env

# Build and start
docker compose build
docker compose up -d

# Verify
curl http://localhost:8000/health
```

**Access:** Grafana at <http://localhost:3000> (admin/admin)

---

## Expected Results

### Services Running

```text
NAME                STATUS              PORTS
starlink-location   Up 10 seconds       0.0.0.0:8000->8000/tcp
prometheus          Up 12 seconds       0.0.0.0:9090->9090/tcp
grafana             Up 11 seconds       0.0.0.0:3000->3000/tcp
```

### Health Check Response

```json
{
  "status": "ok",
  "uptime_seconds": 15.3,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2025-10-31T10:30:00.000000",
  "message": "Service is healthy",
  "dish_connected": false
}
```

---

## Default Configuration

The `.env` file contains all configuration settings:

```bash
# Operating mode
STARLINK_MODE=simulation

# Service ports
STARLINK_LOCATION_PORT=8000
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Data retention
PROMETHEUS_RETENTION=1y

# Grafana credentials
GRAFANA_ADMIN_PASSWORD=admin
```

**For now, the defaults are fine.** You can customize later in
[Configuration](./configuration.md).

---

## Next Steps

- [Installation Steps](./installation-steps.md) - Detailed step-by-step guide
- [Verification](./installation-verification.md) - Verify your installation
- [Configuration](./configuration.md) - Customize for your use case

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
