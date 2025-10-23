# Starlink Dashboard

A Docker-based monitoring system for Starlink terminals with real-time metrics visualization through Prometheus and Grafana. Supports both live monitoring of physical Starlink hardware and simulation mode for offline development.

## Quick Start

### Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 1.29 or higher)
- Git

### Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd starlink-dashboard
   ```

2. Copy the example environment configuration:
   ```bash
   cp .env.example .env
   ```

3. Start all services:
   ```bash
   docker compose up -d
   ```

## Access Points

Once services are running, access them at:

- **Grafana Dashboard:** http://localhost:3000 (default credentials: admin/admin)
- **Prometheus Metrics:** http://localhost:9090
- **Backend Health:** http://localhost:8000/health
- **Backend Metrics:** http://localhost:8000/metrics

## Configuration

The `.env` file controls all service configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMULATION_MODE` | Enable simulation mode for offline development | `true` |
| `PROMETHEUS_RETENTION` | Metrics retention period (e.g., 15d, 7d) | `15d` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `admin` |
| `STARLINK_LOCATION_PORT` | Backend service port | `8000` |
| `PROMETHEUS_PORT` | Prometheus scraper port | `9090` |
| `GRAFANA_PORT` | Grafana UI port | `3000` |

## Development Workflow

Common Docker Compose commands:

```bash
# Start all services in background
docker compose up -d

# Stop all services
docker compose down

# View live logs from all services
docker compose logs -f

# View logs from specific service
docker compose logs -f <service-name>

# Restart services
docker compose restart

# Rebuild Docker images
docker compose build
docker compose build --no-cache

# Rebuild and restart
docker compose up -d --build
```

## Architecture

For detailed system architecture, design decisions, and component descriptions, see [docs/design-document.md](docs/design-document.md).

The system consists of three main components:

- **Backend (starlink-location):** FastAPI service that exposes Starlink telemetry via Prometheus metrics
- **Prometheus:** Time-series database for metrics collection and storage
- **Grafana:** Dashboard UI for visualizing metrics

## Testing

Validate the infrastructure with the automated test script:

```bash
./test-phase1.sh
```

This script performs smoke tests including:
- Container health status
- Service HTTP endpoints
- Prometheus metrics collection
- Grafana dashboard availability
