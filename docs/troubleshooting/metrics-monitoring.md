# Metrics and history troubleshooting

Prometheus scrapes `starlink-location:8000/metrics` at 1-second intervals. The
backend queries Prometheus for Overview history; Mission Planner renders it.
Grafana is not a dependency of this deployment.

```bash
curl --fail --max-time 10 http://localhost:8000/metrics
curl --fail --max-time 10 http://localhost:9090/-/ready
curl --fail --max-time 10 http://localhost:9090/api/v1/targets
curl --fail --max-time 10 'http://localhost:9090/api/v1/query?query=up'
docker compose logs --tail=100 prometheus
```

Use the configured host ports. Inspect `health` and `lastError` for the backend
target. A failed target may indicate backend health, the bridge network, or
invalid scrape config. Use host curl or backend-container curl for diagnostics;
do not assume the Prometheus image includes curl.

The config is bind-mounted locally; restart Prometheus after changing it. Both
global and job-specific scrape intervals are set to 1 second, with a 1-second
job timeout. The rules file is mounted under `/etc/prometheus/rules/`.

If samples exist but Overview history is absent, check backend logs and
`STARLINK_PROMETHEUS_URL` (default `http://prometheus:9090`), selected history
window, and sample freshness. History lookback does not increase database
retention. A fresh database cannot provide older samples, and live connectivity
loss does not create synthetic history. During paced replay the Overview network
cards are intentionally hidden.

See [monitoring services](../../monitoring/docs/services-overview.md) and
[history configuration](../setup/configuration/environment-variables.md).
