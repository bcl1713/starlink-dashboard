# Monitoring API Reference

[Back to API Reference](./README.md) |
[Operations Overview Runbook](../operations-overview.md)

## Scope and access boundary

These endpoints support the React Operations Overview. Browser callers use
origin-relative, same-origin `/api/...` requests through the Mission Planner
origin. The backend owns the Prometheus connection and allow-listed queries;
clients do not receive a Prometheus URL, arbitrary query interface, upstream
credentials, or Grafana session. Do not put internal service endpoints or
ground-entry-point details in browser configuration or support captures.

## `GET /api/monitoring/history`

Returns a server-owned UTC monitoring window for the fixed allow-listed series:
`latitude_degrees`, `longitude_degrees`, `latency_ms`, `throughput_down_mbps`,
`throughput_up_mbps`, and `packet_loss_percent`, in that order. It is not a
general Prometheus proxy. Successful responses include
`Cache-Control: no-store`.

### Query parameters

| Parameter       | Default | Allowed values                         | Meaning                   |
| --------------- | ------: | -------------------------------------- | ------------------------- |
| `range_seconds` |  `1800` | integer `60` through `3600`, inclusive | UTC history window length |
| `step_seconds`  |     `1` | integer `1` through `60`, inclusive    | Prometheus query step     |

Values outside those bounds receive FastAPI validation response `422` and do not
start a history query. Unknown query parameters do not broaden the fixed
allow-list or grant upstream access.

### Request

```bash
curl 'http://localhost:8000/api/monitoring/history?range_seconds=60&step_seconds=10'
```

### Successful response semantics

`generated_at` is the backend response-generation time; `window_start` and
`window_end` define the requested UTC window. Each sample's `timestamp` is its
Prometheus observation time. `value` is a finite number or `null` when a sample
is unavailable/non-finite. The response always contains all six series in the
listed order; a series may have an empty `samples` array.

```json
{
  "generated_at": "2026-08-29T12:00:00Z",
  "window_start": "2026-08-29T11:59:00Z",
  "window_end": "2026-08-29T12:00:00Z",
  "range_seconds": 60,
  "step_seconds": 10,
  "series": [
    { "metric": "latitude_degrees", "samples": [] },
    { "metric": "longitude_degrees", "samples": [] },
    { "metric": "latency_ms", "samples": [] },
    { "metric": "throughput_down_mbps", "samples": [] },
    { "metric": "throughput_up_mbps", "samples": [] },
    { "metric": "packet_loss_percent", "samples": [] }
  ]
}
```

The example illustrates response shape only; timestamps and samples are not live
operational data.

### Safe error contracts

The endpoint returns only the safe code in `detail`; it does not expose an
upstream URL or error body.

| HTTP status | Response body                                           | Required handling                                                               |
| ----------- | ------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `429`       | `{"detail":{"code":"monitoring_rate_limited"}}`         | Honor the integer `Retry-After` response header before retrying.                |
| `502`       | `{"detail":{"code":"monitoring_upstream_error"}}`       | Treat as an upstream service signal; do not inspect or expose upstream details. |
| `503`       | `{"detail":{"code":"monitoring_capacity_unavailable"}}` | Treat as temporary monitoring capacity unavailability.                          |
| `504`       | `{"detail":{"code":"monitoring_upstream_timeout"}}`     | Treat as an upstream timeout.                                                   |

For operator response and Grafana dual-run fallback, see the
[operations overview troubleshooting runbook](../operations-overview.md#troubleshooting-and-escalation).

## `GET /api/monitoring/ground-entry-point`

Returns the cached ground-entry-point display/location state without triggering
discovery. It always responds `200`; `available: false` means no cached value is
available, not that a client should attempt a browser-side lookup.

| Field                                                           | Meaning                                                         |
| --------------------------------------------------------------- | --------------------------------------------------------------- |
| `available`                                                     | Whether a cached entry point is available.                      |
| `observed_at`                                                   | UTC time of the cached observation, or `null` when unavailable. |
| `generated_at`                                                  | UTC time the response was generated.                            |
| `display`, `city`, `region`, `country`, `latitude`, `longitude` | Cached display/location fields, or `null` when unavailable.     |

```bash
curl http://localhost:8000/api/monitoring/ground-entry-point
```

Unavailable response:

```json
{
  "available": false,
  "observed_at": null,
  "generated_at": "2026-08-29T12:00:00Z",
  "display": null,
  "city": null,
  "region": null,
  "country": null,
  "latitude": null,
  "longitude": null
}
```

No public IP field is returned. The API does not document or expose entry-point
provenance beyond this cached display/location contract. The timestamp is
illustrative rather than a live observation.

## Operational transition

`/overview` is the canonical React operator view. Grafana remains deployed and
supported as the dual-run fallback for existing dashboard-specific workflows;
there is no approved retirement date. If the overview monitoring API is
unavailable, use Grafana for the supported fallback rather than adding direct
browser access to Prometheus.
