# Installation

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)

---

## Overview

Complete installation guide for Starlink Dashboard. This documentation has been
split into focused sections for easier navigation.

---

## Installation Guides

### [Quick Installation](./installation-quick-start.md)

For experienced users - get running in 3 minutes.

**Contents:**

- Quick start commands
- Expected results
- Default configuration
- Next steps

**When to use:** You're familiar with Docker and just need the commands.

---

### [Installation Steps](./installation-steps.md)

Detailed step-by-step installation guide.

**Contents:**

- Clone repository
- Create environment file
- Build Docker images
- Start services
- Verify services
- Access points

**When to use:** First-time setup or need detailed instructions.

---

### [Installation Verification](./installation-verification.md)

Verify that all services are running correctly.

**Contents:**

- Service health checks
- Data flow verification
- Quick diagnostics
- Troubleshooting next steps

**When to use:** After installation to confirm everything works.

---

### [First-Time Configuration](./installation-first-time.md)

Optional configuration steps after installation.

**Contents:**

- Upload sample routes
- Create POIs
- View dashboards
- Next steps

**When to use:** To enhance your setup with sample data and configuration.

---

### [Installation Troubleshooting](./installation-troubleshooting.md)

Common installation issues and solutions.

**Contents:**

- Services won't start
- Container exits immediately
- Can't access services
- Port conflicts
- Prometheus not scraping
- Grafana shows no data
- Build failures

**When to use:** When encountering installation problems.

---

## Quick Reference

**Prerequisites:** [System Requirements](./system-requirements.md)

**Quick Start:**

```bash
git clone https://github.com/your-repo/starlink-dashboard.git
cd starlink-dashboard
cp .env.example .env
docker compose build
docker compose up -d
curl http://localhost:8000/health
```

**Access Points:**

- Grafana: <http://localhost:3000> (admin/admin)
- Prometheus: <http://localhost:9090>
- Backend API: <http://localhost:8000/docs>

---

## Navigation

- [Back to Setup Guide](./README.md)
- [System Requirements](./system-requirements.md)
- [Configuration](./configuration.md)
- [Back to main docs](../index.md)

---

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)
