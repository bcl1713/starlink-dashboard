# Starlink Dashboard

A Docker-based monitoring system for Starlink terminals with real-time metrics
visualization through Prometheus and Mission Planner. Supports both live
monitoring of physical Starlink hardware and simulation mode for offline
development.

**Status:** Phase 0 Complete (Foundation) + ETA Route Timing Feature Complete
**Version:** 0.2.0 **Last Updated:** 2026-02-28

---

## Quick Navigation

**For Users:**

- [Quick Start](./docs/setup/quick-start.md) - Get up and running in 3 minutes
- [Setup Guide](./docs/setup/README.md) - Detailed installation instructions
- [Features Overview](./docs/features/overview.md) - Complete feature list
- [Troubleshooting](./docs/troubleshooting/quick-diagnostics.md) - Common issues
  and solutions

**For Developers:**

- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [API Reference](./docs/api-reference-index.md) - Complete API documentation
- [Development Workflow](./docs/development/workflow.md) - Development practices
- [Architecture](./docs/architecture/design-document.md) - System design and
  architecture

---

## Quick Start

### Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- Git

### 3-Minute Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/your-repo/starlink-dashboard.git
cd starlink-dashboard

# 2. Set up configuration
cp .env.example .env

# 3. Start services
./scripts/compose.sh up -d --build

# 4. Verify and access
curl http://localhost:8000/health        # Backend health
open http://localhost:5173                # Mission Planner
```

**Detailed setup:** See [Quick Start Guide](./docs/setup/quick-start.md)

After `git pull`, use `./scripts/compose.sh up -d --build --remove-orphans`
again. This removes the retired Grafana container from an existing local stack.
Its old data volume is retained; remove it separately only if its data is no
longer needed. Ordinary wrapper commands include the NOAA GFS worker, so
`./scripts/compose.sh build` followed by `./scripts/compose.sh up -d` also
starts model weather support. Winds and temperature remain disabled until
enabled in Configuration. Local Compose overrides and custom file selection
continue to work normally. The wrapper passes the full checked-out HEAD SHA
to all three image builds. A dirty worktree is not an exact acceptance
candidate; use a clean commit for acceptance.

---

## Access Points

Once services are running:

| Service             | URL                             | Purpose                        |
| ------------------- | ------------------------------- | ------------------------------ |
| **Mission Planner** | <http://localhost:5173>         | Dashboard and mission planning |
| **Prometheus**      | <http://localhost:9090>         | Metrics database               |
| **Backend API**     | <http://localhost:8000/docs>    | Interactive API docs           |
| **Health Check**    | <http://localhost:8000/health>  | Service status                 |
| **Metrics**         | <http://localhost:8000/metrics> | Raw Prometheus metrics         |

---

## Documentation

Comprehensive documentation is organized by topic:

### For Getting Started

- [Quick Start](./docs/setup/quick-start.md) - 3-minute setup
- [Setup Guide](./docs/setup/installation.md) - Installation and configuration

### For Using the System

- [Features Overview](./docs/features/overview.md) - Complete feature list
- [API Reference](./docs/api-reference-index.md) - REST API endpoints
- [Troubleshooting](./docs/troubleshooting/quick-diagnostics.md) - Common issues

### For Development

- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [Design Document](./docs/architecture/design-document.md) - Architecture

### For Reference

- [Backend README](./backend/starlink-location/README.md) - Service details

---

## Getting Help

**Setup Issues:**

- See [Quick Start](./docs/setup/quick-start.md)
- Check [Troubleshooting Guide](./docs/troubleshooting/quick-diagnostics.md)

**API Questions:**

- See [API Reference](./docs/api-reference-index.md)
- Visit <http://localhost:8000/docs> (interactive documentation)

**Development Questions:**

- See [Contributing Guide](./CONTRIBUTING.md) **Specific Issues:**

- See [Troubleshooting Guide](./docs/troubleshooting/quick-diagnostics.md)
- Run diagnostic commands in [Quick Start](./docs/setup/quick-start.md)

---

## Contributing

Want to help improve Starlink Dashboard?

- Read [Contributing Guide](./CONTRIBUTING.md)
- Review [Architecture](./docs/architecture/design-document.md) before starting

---

## License

Part of the Starlink Dashboard project.

---

## Related Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

---

**Quick Links:** [Quick Start](./docs/setup/quick-start.md) |
[Features](./docs/features/overview.md) |
[API Docs](./docs/api-reference-index.md) | [Contributing](./CONTRIBUTING.md)
