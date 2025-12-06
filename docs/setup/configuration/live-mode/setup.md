# Live Mode Setup

[Back to Configuration Guide](../README.md)

---

## Overview

**Purpose:** Connect to a real Starlink terminal for actual telemetry.

Live mode connects directly to your Starlink terminal to collect real metrics
and position data.

---

## Prerequisites

1. Starlink terminal on local network
2. Terminal accessible at `192.168.100.1` (default) or known IP
3. Port `9200` accessible for gRPC communication

---

## Basic Configuration

Edit `.env`:

```bash
# Set mode to live
STARLINK_MODE=live

# Configure dish connection
STARLINK_DISH_HOST=192.168.100.1  # Your terminal's IP
STARLINK_DISH_PORT=9200            # Standard gRPC port
```

---

## Network Mode Selection

Choose network mode based on your OS:

### Option A: Bridge Mode (Recommended - Cross-Platform)

Already configured by default. Works on Windows, macOS, and Linux.

**In `docker-compose.yml`:**

```yaml
extra_hosts:
  - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

No changes needed - this is the default configuration.

### Option B: Host Mode (Linux Only - Best Performance)

For Linux systems, host mode provides direct network access.

**In `docker-compose.yml`:**

Uncomment:

```yaml
network_mode: host
```

And comment out:

```yaml
# extra_hosts:
#   - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```
