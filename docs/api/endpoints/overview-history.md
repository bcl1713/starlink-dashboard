# Overview History API

[Back to API endpoints](./README.md)

## GET `/api/overview-history`

Returns one bounded Prometheus history bundle for the saved Overview window. The
same response supplies the aircraft trail and all five metric graphs; the
browser makes one request per five-second poll, not one per graph. The current
metrics card is independently sourced from `/api/status`.

```json
{
  "window_seconds": 1800,
  "start_timestamp_seconds": 1781998200,
  "end_timestamp_seconds": 1782000000,
  "step_seconds": 1,
  "series": {
    "starlink_network_latency_ms_current": [[1781999999, 42.5]]
  },
  "rolling_5m": {
    "starlink_network_latency_ms_current": {
      "state": "available",
      "min": [[1781999999, 38.0]],
      "avg": [[1781999999, 41.2]],
      "max": [[1781999999, 47.0]]
    }
  }
}
```

Each sample is `[Unix timestamp in seconds, finite numeric value]`. `series`
contains raw observed metrics including aircraft location, speed, heading,
network latency, downlink and uplink throughput, packet loss, dish obstruction,
and signal quality. Missing metrics are absent rather than filled with zeros.
The five graph metrics (latency, downlink, uplink, packet loss, and obstruction)
are keys in `rolling_5m`. Each has `state: "available"` and three timestamped
traces (`min`, `avg`, `max`), or `state: "unavailable"` and empty aggregate
arrays when any of its aggregate queries fails or returns an invalid result. An
available aggregate may itself have empty sample arrays when no source data
exists. Older cached responses may omit `rolling_5m`; clients should mark
aggregates unavailable while retaining usable raw history. Failed aggregate
queries do not erase the raw `series` or aircraft trail. A raw Prometheus fetch
failure returns `503 Service Unavailable`; clients may show explicitly marked
last-good history, but must not extend its traces to the present.

The server selects the persisted positive `window_seconds` from
`/api/overview-history/settings`, ending at the current whole second. It plans
`step_seconds = max(1, ceil(window_seconds / 1800))`, at most 1,801 samples per
trace, and clips samples to the returned start/end boundaries. All raw and
aggregate traces use the same boundaries and step. No ad-hoc window or step
query parameters are accepted by this GET. Duplicate in-flight reads for the
same selected window and ending second share one bundle operation.

## GET and PUT `/api/overview-history/settings`

`GET` returns `{ "window_seconds": 1800 }` (30-minute default). `PUT` with
`{ "window_seconds": 900 }` replaces the saved positive integer window; invalid
values return `422`. The Overview legend currently offers 5, 15, 30, and 60
minutes and retains a previously persisted custom value. Store access failures
return `503`. Graphs and aircraft trail use this same selected window.
