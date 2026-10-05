# Overview History API

[Back to API endpoints](./README.md)

## GET `/api/overview-history`

Returns one bounded Prometheus history bundle for the saved Overview window. The
same response supplies the aircraft trail and all five metric graphs; the
browser makes one shared request per polling interval. The released default
remains five seconds pending the #224 performance acceptance gate; a reviewed
frontend build can select one second. The current metrics card is independently
sourced from `/api/status`.

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
`/api/overview-history/settings`. It plans
`step_seconds = max(1, ceil(window_seconds / 1800))`, at most 1,801 samples per
trace. The end is rounded down to a fixed Unix epoch/step grid; the start is
exactly one selected duration earlier. Evaluations begin at the first grid point
at or after that start. This preserves custom durations without shifting the
sampling grid each second. A 60-minute window still has two-second resolution
when polled every second. All traces share this grid and are clipped to the
returned boundaries. No ad-hoc window or step parameters are accepted.

## Incremental cache and failures

One process retains one selected configuration and one completed snapshot.
Initial reads hydrate the whole window. Healthy warm reads query from ten
seconds before the prior query end through the new aligned end, replace that
entire overlap (including disappearing samples), and evict expired points.
Sequential reads in the same evaluation interval reuse the completed snapshot.
Readers arriving during any refresh share it, including across ending seconds;
they can receive its earlier query end instead of queuing another refresh.
Returned snapshots are never modified by a later refresh. Retention is capped at
1,801 points per trace (26 traces maximum), independent of uptime.

Full loads also occur after settings invalidation, a backwards wall-clock jump,
a gap longer than 30 seconds, usable source/label changes, aggregate recovery,
and every five minutes of demand. Repeated persistent ambiguity does not cause
an endless full-load loop. When a clean tail cannot resolve ambiguity in the
full window, that unsuccessful aggregate recovery is remembered until the tail
becomes unavailable, its source changes, or scheduled reconciliation runs.
Transport and malformed-response failures keep their normal recovery retries. A
metric rejected for ambiguity stays withheld until a source transition or full
reconciliation proves its window unambiguous. The ten-second overlap is a
provisional supported ingestion-lateness bound, chosen against the bundled
one-second scrape interval and timeout; it requires representative-host
validation. Arbitrary older corrections are reconciled by the next demand-driven
full load, rather than being promised immediately. There is no background
history polling without viewers. Restart clears the cache; changing the
Prometheus URL or metric allowlist requires restart.

A failed raw refresh returns 503 and does not advance the last-good snapshot.
Failures are shared; retry delays increase monotonically from one to five
seconds. Each whole refresh has a five-second deadline. Aggregate requests share
an earlier deadline so successful raw history can be published within the
refresh budget. Aggregate errors or deadline exhaustion return usable raw
history with all three traces unavailable for the affected metric; successful
recovery refills the historical aggregates before publishing them. Finite
raw-step masking applies after merging, so old aggregates cannot fill current
raw gaps. Query end, cache publication time and evaluation times are never
substituted for source acquisition time.

Durable settings updates invalidate atomically after persistence, even for an
unchanged duration. Previous-generation work cannot publish after invalidation.
Cancellation by one HTTP waiter does not cancel other readers' shared refresh.
Shutdown drains the refresh before closing the shared HTTP client. The bundled
deployment has one Uvicorn worker; this cache does not share memory across
multiple workers.

## Cadence, hidden tabs and rollback

The shared browser subscription keeps interval polling enabled in hidden tabs
and refetches on focus. Hidden charts pause compositor motion while history
ingestion continues. Errors use a five-second polling interval without additional
automatic retries. Fresh-history processing is memoized separately from clock
labels and compositor motion; timer ticks do not reproject or upload traces.

`VITE_OVERVIEW_HISTORY_POLL_SECONDS=1` selects one-second polling at frontend
build time. The default and invalid values resolve to five seconds. Compose
passes this build argument from `.env`; rebuild `mission-planner` after changing
it. For local builds, run `VITE_OVERVIEW_HISTORY_POLL_SECONDS=1 npm run build`.
Rebuild with `5` to roll back. This does not change scrape cadence, history
resolution or statistics. Do not promote the default until the
representative-host budgets in the
[implementation plan](../../superpowers/plans/2026-10-01-overview-history-efficiency.md)
pass. Fixture measurements are not a real Prometheus/browser resource soak.

## GET and PUT `/api/overview-history/settings`

`GET` returns `{ "window_seconds": 1800 }` (30-minute default). `PUT` with
`{ "window_seconds": 900 }` replaces the saved positive integer window; invalid
values return `422`. The Overview legend currently offers 5, 15, 30, and 60
minutes and retains a previously persisted custom value. Store access failures
return `503`. Graphs and aircraft trail use this same selected window.
