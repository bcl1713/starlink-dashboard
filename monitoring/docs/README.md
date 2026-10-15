# Monitoring Stack Configuration

Prometheus collects and stores backend telemetry. Mission Planner renders the
Overview, including network history queried through the backend.

## Configuration

- `monitoring/prometheus/prometheus.yml` defines scraping and evaluation.
- `monitoring/prometheus/rules/` contains recording and alert rules.
- `PROMETHEUS_RETENTION` controls stored history (default: one year).

## Access and Verification

- Prometheus: <http://localhost:9090>
- Mission Planner: <http://localhost:5173>

```bash
docker compose ps
curl --fail http://localhost:9090/-/ready
curl --fail http://localhost:5173/api/status
```

See [Services Overview](./services-overview.md) and
[Overview features](../../docs/features/overview.md).

[Back to project root](../../README.md)
