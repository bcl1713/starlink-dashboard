# Starlink CSV Export Design

## Context

Prometheus scrapes telemetry metrics every 1 second and retains data for 1 year. The backend is FastAPI-based with dependency injection. The frontend is React with existing page patterns (POIManagerPage, RouteManagerPage, etc.).

## Goals / Non-Goals

**Goals:**
- Query Prometheus HTTP API for historical metric data
- Generate CSV with aligned timestamps across all metrics
- Provide simple UI for date range selection and download

**Non-Goals:**
- Real-time streaming export (batch only)
- Multiple export formats (CSV only for now)
- Scheduled/automated exports

## Decisions

### Decision 1: Query Prometheus directly from backend

The backend will query Prometheus's HTTP API (`/api/v1/query_range`) for each metric, then join results by timestamp. This keeps Prometheus as the single source of truth.

**Prometheus URL:** `http://prometheus:9090` (internal docker network)

### Decision 2: Metrics to export

Query these Prometheus metrics:
- `starlink_dish_latitude_degrees`
- `starlink_dish_longitude_degrees`
- `starlink_dish_altitude_feet`
- `starlink_dish_speed_knots`
- `starlink_dish_heading_degrees`
- `starlink_network_latency_ms_current`
- `starlink_network_throughput_down_mbps_current`
- `starlink_network_throughput_up_mbps_current`
- `starlink_network_packet_loss_percent`
- `starlink_dish_obstruction_percent`
- `starlink_signal_quality_percent`

### Decision 3: Configurable step interval

The step interval will be a configurable parameter with sensible defaults:

```
GET /api/export/starlink-csv?start={iso8601}&end={iso8601}&step={seconds}
```

**Default behavior:**
- If `step` not provided, auto-calculate based on range:
  - Range ≤ 2 hours → 1s step
  - Range ≤ 24 hours → 10s step
  - Range ≤ 7 days → 60s step
  - Range > 7 days → 300s step (5 min)

**Manual override:**
- User can specify exact step in seconds (minimum 1s)
- UI provides dropdown: "1s", "10s", "1min", "5min", "Auto"

This keeps exports manageable while allowing fine-grained data when needed.

### Decision 4: API structure

```
GET /api/export/starlink-csv?start={iso8601}&end={iso8601}&step={seconds}
Response: CSV file download (StreamingResponse)
```

### Decision 5: Frontend location

Add export UI to existing navigation. Simple page with two datetime inputs, step selector, and an export button.
