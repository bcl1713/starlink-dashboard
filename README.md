# Starlink Dashboard

A Docker-based monitoring system for Starlink terminals with real-time metrics
visualization through Prometheus and Grafana. Supports both live monitoring of
physical Starlink hardware and simulation mode for offline development.

**Status:** Phase 0 Complete (Foundation) + ETA Route Timing Feature Complete
**Version:** 0.3.0 **Last Updated:** 2025-11-04

---

## Quick Navigation

**For Users:**

- [Quick Start](./docs/setup/quick-start.md) - Get up and running in 3 minutes
- [Setup Guide](./docs/setup/README.md) - Detailed installation instructions
- [Features Overview](./docs/features/overview.md) - Complete feature list
- [Troubleshooting](./docs/troubleshooting/quick-diagnostics.md) - Common
  issues and solutions

**For Developers:**

- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [API Reference](./docs/api-reference-index.md) - Complete API documentation
- [Development Workflow](./docs/development/workflow.md) - Development practices
- [Architecture](./docs/architecture/design-document.md) - System design and architecture

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
docker compose up -d

# 4. Verify and access
curl http://localhost:8000/health        # Backend health
open http://localhost:3000                # Grafana (admin/admin)
```

**Detailed setup:** See [Quick Start Guide](./docs/setup/quick-start.md)

---

## Access Points

Once services are running:

| Service          | URL                             | Purpose                  |
| ---------------- | ------------------------------- | ------------------------ |
| **Grafana**      | <http://localhost:3000>         | Dashboards (admin/admin) |
| **Prometheus**   | <http://localhost:9090>         | Metrics database         |
| **Backend API**  | <http://localhost:8000/docs>    | Interactive API docs     |
| **Health Check** | <http://localhost:8000/health>  | Service status           |
| **Metrics**      | <http://localhost:8000/metrics> | Raw Prometheus metrics   |

---

## Documentation

Comprehensive documentation is organized by topic:

### For Getting Started

- [Quick Start](./docs/setup/quick-start.md) - 3-minute setup
- [Setup Guide](./docs/setup/installation.md) - Installation and configuration

### For Using the System

- [Features Overview](./docs/features/overview.md) - Complete feature list
- [Grafana Setup](./docs/setup/grafana-setup.md) - Dashboard usage
- [API Reference](./docs/api-reference-index.md) - REST API endpoints
- [Troubleshooting](./docs/troubleshooting/quick-diagnostics.md) - Common issues

### For Development

- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [CLAUDE.md](./CLAUDE.md) - Development configuration
- [Design Document](./docs/architecture/design-document.md) - Architecture
- [Development Status](./dev/STATUS.md) - Current progress

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

- See [Contributing Guide](./CONTRIBUTING.md)
- Check [Development Status](./dev/STATUS.md)

**Specific Issues:**

- See [Troubleshooting Guide](./docs/troubleshooting/quick-diagnostics.md)
- Run diagnostic commands in [Quick Start](./docs/setup/quick-start.md)

---

## Contributing

Want to help improve Starlink Dashboard?

- Read [Contributing Guide](./CONTRIBUTING.md)
- Check [Development Status](./dev/STATUS.md) for current tasks
- Review [Architecture](./docs/architecture/design-document.md) before starting

---

## License

Part of the Starlink Dashboard project.

---

## Related Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

---

**Quick Links:** [Quick Start](./docs/setup/quick-start.md) |
[Features](./docs/features/overview.md) |
[API Docs](./docs/api-reference-index.md) | [Contributing](./CONTRIBUTING.md)
