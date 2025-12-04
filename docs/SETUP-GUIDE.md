# Starlink Dashboard Setup Guide

**This document has been reorganized into multiple focused files.**

Please see: **[Setup Documentation](./setup/README.md)**

---

## Quick Links

- **[Setup Index](./setup/README.md)** - Complete setup guide
- **[Prerequisites](./setup/prerequisites-verification.md)** - System
  requirements
- **[Installation](./setup/installation.md)** - Installation steps
- **[Configuration](./setup/configuration/README.md)** - Configuration options
- **[Verification](./setup/README.md#verification)** - Verify installation

---

## Quick Setup

### 1. Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 5 GB disk space
- 4 GB RAM

### 2. Install

```bash
# Clone repository
git clone <repository-url>
cd starlink-dashboard-dev

# Copy environment file
cp .env.example .env

# Start services
docker compose up -d
```

### 3. Verify

```bash
# Check all services running
docker compose ps

# Test backend
curl http://localhost:8000/health

# Open Grafana
open http://localhost:3000  # Login: admin/admin
```

---

## Configuration

### Simulation Mode (Default)

```bash
# In .env
STARLINK_MODE=simulation
```

No hardware required! Perfect for development and testing.

### Live Mode

```bash
# In .env
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
```

Connects to real Starlink terminal.

---

## Next Steps

1. **[Configuration Guide](./setup/configuration/README.md)** - Customize
   settings
2. **[API Reference](./api/README.md)** - Explore endpoints
3. **[Troubleshooting](./troubleshooting/README.md)** - Common issues

---

[Go to Full Setup Guide →](./setup/README.md)

[Back to main docs](./INDEX.md)
