# Backend Architecture

The backend is a FastAPI application at `main.py`. Its API modules expose
telemetry, routes/POIs, Mission V2 and planning, persisted display settings,
weather/traffic, and exports. Service modules own acquisition, caching, storage,
validation, and calculations; Pydantic models define strict API contracts.

Simulation and terminal telemetry share status/metrics consumers. Mission leg
activation selects an executable route and simulation context. Prometheus
scrapes `/metrics`; Mission Planner consumes backend APIs through Nginx in the
production frontend. NOAA GFS processing runs in a separate worker with shared
mailbox/product volumes.

See the maintained
[system architecture](../../../docs/architecture/design-document.md),
[data structures](../../../docs/data-structures/index.md), and
[API reference](../../../docs/api-reference-index.md). File layouts, metric
names, and performance figures in older reports refer to their original
candidates.

[Back to backend](../README.md)
