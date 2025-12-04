# Starlink Location Backend

A FastAPI-based Prometheus metrics exporter and telemetry API for simulating
Starlink dish positioning, network performance, and environmental conditions.
Includes realistic physics-based simulators for position tracking, network
metrics, and obstruction detection.

---

## Features

- **Simulation Mode**: Generates realistic Starlink telemetry data
- **Prometheus Metrics**: Exports metrics in Prometheus format (1-second scrape
  interval)
- **REST API**: JSON telemetry endpoints and configuration management
- **Structured Logging**: JSON-formatted logs for monitoring and debugging
- **Health Checks**: Built-in health monitoring and uptime tracking
- **Configuration Management**: Runtime configuration updates via API or
  environment variables
- **Graceful Degradation**: Returns last known good values on errors
- **Background Updates**: Continuous telemetry generation at 10 Hz

---

## Quick Links

- [Getting Started](./docs/GETTING-STARTED.md) - Installation and setup
- [Architecture](./docs/ARCHITECTURE.md) - Project structure and design
- [Testing Guide](./docs/TESTING.md) - Running tests
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues
- [API Reference](./docs/API-REFERENCE.md) - Complete endpoint documentation
- [Configuration Guide](./docs/CONFIGURATION.md) - Environment variables and
  config files
- [Main Project Documentation](../../docs/) - Overall project docs

---

## Quick Start

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
```

**Detailed instructions:** See
[Getting Started Guide](./docs/GETTING-STARTED.md)

---

## Documentation Structure

### For Getting Started

- [Getting Started](./docs/GETTING-STARTED.md) - Setup and basic usage
- Quick start commands
- Core endpoints overview
- Configuration basics

### For Understanding the System

- [Architecture](./docs/ARCHITECTURE.md) - Project structure and metrics
- Simulation behavior details
- Performance characteristics
- Logging configuration

### For Development

- [Testing Guide](./docs/TESTING.md) - Running and writing tests
- [API Reference](./docs/API-REFERENCE.md) - Complete endpoint documentation
- [Configuration Guide](./docs/CONFIGURATION.md) - All configuration options

### For Troubleshooting

- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues and solutions

---

## Key Features

### Simulation Mode

- Generates realistic position, network, and obstruction metrics
- Configurable via environment variables or config files
- Supports circular and straight route patterns
- Realistic network latency spikes and packet loss

### Prometheus Integration

- Exports metrics in Prometheus format
- 1-second scrape interval support
- Comprehensive metric coverage
- Compatible with Grafana dashboards

### REST API

- Health check endpoint
- JSON status endpoint
- Configuration management API
- Real-time metric queries

---

## Contributing

When making changes:

1. Update tests in `tests/`
2. Ensure all tests pass: `pytest tests/`
3. Run with coverage: `pytest tests/ --cov=app`
4. Update documentation if adding features

See [Testing Guide](./docs/TESTING.md) for more details.

---

## License

Part of the Starlink Dashboard project.

---

## Related Resources

- [Main Project Documentation](../../docs/design-document.md) - Architecture and
  design
- [Grafana Setup](../../docs/grafana-setup.md) - Dashboard configuration
- [Setup Guide](../../docs/SETUP-GUIDE.md) - Complete system setup

---

[Back to Main Project](../../README.md)
