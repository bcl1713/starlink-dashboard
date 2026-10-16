# Monitoring Stack Configuration

Prometheus collects and stores backend telemetry. Mission Planner renders the
Overview, including network history queried through the backend. Grafana is not
bundled or required.

## Configuration

- `monitoring/prometheus/prometheus.yml` defines scraping and evaluation.
- `monitoring/prometheus/rules/` contains recording and alert rules.
- `PROMETHEUS_RETENTION` controls stored history (example default: one year).
- Overview history lookback and frontend polling cadence are separate from
  retention; see
  [environment settings](../docs/setup/configuration/environment-variables.md).
- Local host port 9090 can be overridden with `PROMETHEUS_PORT`.

## Access and Verification

- Prometheus: <http://localhost:9090>
- Mission Planner: <http://localhost:5173>

```bash
docker compose ps
curl --fail http://localhost:9090/-/ready
curl --fail http://localhost:5173/api/status
```

See [Services Overview](./docs/services-overview.md) and
[Overview features](../docs/features/overview.md).

[Back to project root](../README.md)
