# Grafana Dashboard Refactor Plan

## Context
- Existing dashboards (`overview`, `network-metrics`, `position-movement`, `fullscreen-overview`) repeat several identical panels and datasource settings.
- Manual duplication raises the risk of configuration drift when thresholds, queries, or layout details need tweaks.

## Proposed Refactors
1. **Reusable network visualizations**  
   Convert the latency, packet-loss, throughput, outage, and obstruction panels that appear on multiple dashboards into library panels (or manage them via Jsonnet/Grafonnet) so threshold updates only happen once.
2. **Template-driven repeated stats**  
   Replace the “Current Speed / Heading / Altitude” stat trio with a single panel that repeats over a template variable listing metric + unit pairs. This keeps formatting and thresholds aligned while shrinking JSON.
3. **Dynamic timezone clocks**  
   Introduce a `timezones` variable and repeat a single clock panel over its values. This removes the need to edit multiple panels when adding or adjusting a location.
4. **Dashboard-level datasource defaults**  
   Define the Prometheus datasource once at the dashboard level (or via a variable) and reference it from panels implicitly. This simplifies environment changes and reduces copy/paste.

## Next Steps
- Stand up library panels in Grafana, attach them to each dashboard, and retest layout.
- Evaluate Grafana-as-code tooling (Jsonnet/Grizzly) for longer-term maintainability.
- After refactors, export refreshed dashboard JSON and update the repository.
