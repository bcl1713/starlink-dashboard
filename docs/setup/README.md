# Setup

**Purpose**: Help users install, configure, and initially deploy the system
**Audience**: Users, operators, first-time installers

[Back to main docs](../index.md)

---

## Documentation in This Category

### Getting Started

- **[Quick Start](./quick-start.md)**: 3-minute setup for experienced users
  - fastest way to get the system running
- **[Prerequisites](prerequisites-verification.md)**: Hardware and software
  prerequisites for running Starlink Dashboard
- **[Installation](./installation.md)**: Comprehensive step-by-step
  installation guide
- **[Configuration](./configuration.md)**: Environment variables, operating
  modes, and system configuration

### Installation Guides (Detailed)

- **[Installation Steps](./installation-steps.md)**: Detailed installation
  walkthrough with explanations
- **[Installation - First Time](./installation-first-time.md)**: First-time
  user installation guide with extra detail
- **[Installation - Quick Start](./installation-quick-start.md)**: Fast-track
  installation for experienced users
- **[Installation Verification](./installation-verification.md)**: Verify
  successful installation and service health
- **[Installation Troubleshooting](./installation-troubleshooting.md)**:
  Common installation issues and solutions

### Prerequisites Verification

- **[Prerequisites Verification](./prerequisites-verification.md)**: Verify
  system meets all requirements before installation

---

## Overview

This guide walks you through setting up the Starlink Dashboard system on your
local machine or server. The system uses Docker Compose for easy deployment and
includes:

- **Backend Service** - FastAPI-based telemetry collection and API
- **Prometheus** - Time-series metrics database
- **Grafana** - Visualization dashboards

---

## Setup Process

### 1. Check Prerequisites

Ensure your system meets the minimum requirements:

- Docker 20.10+
- Docker Compose 2.0+
- 5 GB disk space
- 4 GB RAM

**[View Prerequisites →](prerequisites-verification.md)**

### 2. Install

Follow the installation steps to get the system running:

1. Clone repository
2. Create environment file
3. Build Docker images
4. Start services

**[View Installation Steps →](./installation.md)**

### 3. Configure

Set up the system for your use case:

- Choose simulation or live mode
- Configure environment variables
- Set up route management
- Adjust performance settings

**[View Configuration Guide →](./configuration.md)**

---

## Quick Start

For those who want to jump right in:

```bash
# Clone repository
git clone <https://github.com/your-repo/starlink-dashboard.git>
cd starlink-dashboard

# Copy environment file
cp .env.example .env

# Start services
docker compose up -d

# Verify
curl <http://localhost:8000/health>
```

**Access points:**

- Grafana: <<http://localhost:3000>> (admin/admin)
- Prometheus: <<http://localhost:9090>>
- Backend API: <<http://localhost:8000/docs>>

---

## Operating Modes

The system supports two operating modes:

### Simulation Mode (Default)

Perfect for development and testing without hardware:

- Generates realistic telemetry data
- Follows KML routes if provided
- No Starlink terminal required
- Configurable behavior patterns

**[Learn more →](./configuration.md#simulation-mode)**

### Live Mode

Connects to a real Starlink terminal:

- Real-time telemetry from dish
- Actual network metrics
- Requires terminal on local network
- Auto-reconnects if connection lost

**[Learn more →](./configuration.md#live-mode)**

---

## Verification

After setup, verify everything works:

```bash
# 1. Check services
docker compose ps

# 2. Check backend health
curl <http://localhost:8000/health>

# 3. Check Prometheus targets
curl <http://localhost:9090/api/v1/targets>

# 4. Access Grafana
open <http://localhost:3000>
```

All services should show "Up" or "healthy" status.

---

## Next Steps

After successful setup:

1. **Explore the API** - Interactive docs at <<http://localhost:8000/docs>>
2. **View Dashboards** - Grafana at <<http://localhost:3000>>
3. **Upload Routes** - Use route management UI
4. **Create POIs** - Add points of interest for tracking

**Useful links:**

- [API Reference](../api/README.md)
- [Route Management](../../CLAUDE.md#route-management)
- [Troubleshooting](../troubleshooting/README.md)

---

## Getting Help

**Common issues:**

- Port conflicts → [Troubleshooting](../troubleshooting/README.md)
- Services won't start → [Installation](./installation.md)
- Configuration problems → [Configuration](./configuration.md)

**Resources:**

- [Design Document](../architecture/design-document.md) - Architecture overview
- [CLAUDE.md](../../CLAUDE.md) - Development guide
- [Troubleshooting Guide](../troubleshooting/README.md) - Common problems

---

**Ready to begin?** Start with [Prerequisites →](prerequisites-verification.md)
