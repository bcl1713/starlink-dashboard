# Phase 1: React Operations Overview Contract and API

> **For Hermes:** Start after Tasks 1–2 in the
> [master plan](../2026-08-29-react-operations-overview.md). Preserve test-first
> ordering and stop at every commit/review gate.

This phase fixes the backend/browser trust boundary and shared data contracts
before dashboard rendering. Return to the
[master plan](../2026-08-29-react-operations-overview.md) for binding scope,
parity semantics, baseline SHA, and existing API ownership.

## API and DTO contracts

Create `backend/starlink-location/app/models/monitoring.py` with strict Pydantic
models (`extra="forbid"`) and UTC-aware datetimes:

```python
MonitoringMetric = Literal[
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
]

class MonitoringSample(BaseModel):
    timestamp: datetime
    value: float | None

class MonitoringSeries(BaseModel):
    metric: MonitoringMetric
    samples: list[MonitoringSample]

class MonitoringHistoryResponse(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    range_seconds: int
    step_seconds: int
    series: list[MonitoringSeries]

class GroundEntryPointResponse(BaseModel):
    available: bool
    observed_at: datetime | None
    generated_at: datetime
    display: str | None
    city: str | None
    region: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
```

Do **not** expose the GEP public IP in the browser DTO. `display` comes from
`GroundEntryPoint.label`, not caller content or raw Prometheus labels.

Create `GET /api/monitoring/history` with:

- `range_seconds: int = 1800`, `ge=60`, `le=3600`.
- `step_seconds: int = 1`, `ge=1`, `le=60`.
- Server-selected `window_end=now(UTC)`; no browser-provided absolute time.
- One fixed internal Prometheus base URL from `PROMETHEUS_URL` defaulting to
  `http://prometheus:9090`.
- Exactly six allow-listed raw metric expressions:
  `starlink_dish_latitude_degrees`, `starlink_dish_longitude_degrees`,
  `starlink_network_latency_ms_current`,
  `starlink_network_throughput_down_mbps_current`,
  `starlink_network_throughput_up_mbps_current`, and
  `starlink_network_packet_loss_percent`.
- Accept exactly zero or one Prometheus matrix result per allow-listed metric;
  reject multiple labeled series as `502` rather than selecting
  nondeterministically. Require `status="success"`, `data.resultType="matrix"`,
  exact metric identity, two-element `[timestamp, value]` points, monotonic
  timestamps, and no duplicate timestamps. Reject malformed or extra response
  shapes.
- A server timeout; an integer point ceiling of
  `6 * (range_seconds // step_seconds + 1)` across accepted/decoded points; and
  a configured upstream body-byte ceiling enforced while streaming before JSON
  parsing. Propagate client-disconnect cancellation and accept no query text,
  hostname, URL, headers, or credentials from a request.
- `NaN`, `+Inf`, and `-Inf` normalized to `null`; timestamps normalized to UTC;
  series always returned in the literal order above, including empty samples.
- `502` with a stable safe detail code for malformed/upstream error and `504`
  for timeout; never include internal URL or response bodies.

Create `GET /api/monitoring/ground-entry-point` returning
`GroundEntryPointResponse`. It reads `get_cached_ground_entry_point()` only and
returns HTTP 200 with `available=false` and null details when no cached value
exists. In that state `observed_at` is `None` while `generated_at` remains the
required response-generation time; the route must not trigger internet discovery
on request.

## Truthful freshness contract

Freshness is source-specific; client receipt time is transport telemetry, never
presented as source freshness:

- `/api/status.timestamp` is the telemetry observation time.
- POI ETA `timestamp` is calculation/generation time, not observation time.
- Add a typed active-link response in `app/models/monitoring.py` and return both
  coordinator telemetry `observed_at` and response `generated_at` from
  `app/api/active_x_link.py`; cache reads must retain the original observation.
- Wrap west/east coordinates in a typed response with `revision_at` derived from
  the active route's persisted source/version modification time and a separate
  `generated_at`; change `app/api/geojson.py` and its contract tests. Static
  route freshness changes only when that revision changes.
- History sample timestamps are Prometheus observation timestamps;
  `MonitoringHistoryResponse.generated_at` is only response generation time.
- Add `observed_at` to cached `GroundEntryPoint` state in
  `app/services/ground_entry_point.py` at successful discovery/config refresh,
  preserve it across `get_cached_ground_entry_point()` reads, and expose it plus
  request-time `generated_at`. Never stamp stale cached discovery with request
  time. Test unchanged-cache, actual refresh, invalidation, and unavailable GEP.
- RainViewer frame time comes from the selected provider frame metadata;
  metadata fetch/generation time is separate. Client freshness uses frame time.

Source stale/recovery tests must advance each applicable source clock, prove
generation alone cannot make an old observation/revision fresh, and label a
source `Unknown freshness` when its truthful source time is absent.

Define matching TypeScript DTOs in
`frontend/mission-planner/src/types/monitoring.ts`. Also define dedicated DTOs
for the existing status, coordinates, active-link, and POI ETA payloads there;
do not reuse `src/types/poi.ts`, because the operational API returns `poi_id`
where the management type requires `id`. Validate external responses with zod at
the service boundary and reject malformed finite ranges/coordinates.

## International Date Line handling

Implement pure utilities in
`frontend/mission-planner/src/pages/OverviewPage/geometry.ts` and unit-test them
before map work:

- Normalize longitude into `[-180, 180)`.
- Detect an IDL crossing when adjacent normalized longitudes differ by more than
  180 degrees.
- Interpolate the latitude at `+180/-180`, end the current segment at one edge,
  and begin a new segment at the opposite edge. Preserve timestamps and stable
  order for history.
- Split every route-like geometry: planned route, position history, and each
  active-link state. Never connect the last point of one segment to the first
  point of another.
- Handle exact `180`, duplicate points, null/invalid samples, one-point input,
  repeated crossings, east-to-west and west-to-east movement.
- The backend history endpoint returns one canonical lat/lon history; React
  aligns latitude and longitude by exact timestamp and performs the split once.
  The duplicate eastern/western PromQL targets in Grafana are implementation
  plumbing, not an API contract.

## Plan Map

The backend, frontend, browser, CI, docs, and later ownership boundaries are in
the [plan map](00-exact-file-map.md). Exact paths remain binding where already
implemented or where an owning contract explicitly requires one. For later
operational-map and responsive-composition work, use the responsibility maps
there instead of treating historical path inventory as a global exact-file
constraint.

## Test-first API tasks and commit boundaries

### Task 3: Add strict monitoring models and allow-listed Prometheus client

**Files:** Backend monitoring models/client and their unit tests from the
[plan map](#plan-map).

**Steps:**

1. Test exact model schema, UTC serialization, forbidden extra keys, stable
   series ordering, parameter bounds, fixed query map, exact
   `/api/v1/query_range` parameters, timeout/disconnect cancellation, malformed
   JSON, upstream error, empty result, exact matrix shape, rejection of multiple
   series, identity mismatch, integer point ceiling, streaming body-byte
   ceiling, and non-finite normalization.
2. Explicitly test that caller PromQL, URL, hostname, and headers cannot enter
   the client API.
3. Run focused tests and observe import failures:

   ```bash
   cd backend/starlink-location
   python -m pytest tests/unit/test_monitoring_models.py \
     tests/unit/test_prometheus_client.py -q
   ```

4. Implement strict Pydantic DTOs and a small async `httpx` client with the six
   constant expressions. Apply a documented per-client rate limit of 12 history
   requests/minute, a process-wide semaphore of 4 upstream range queries,
   cancellation on disconnect, and single-flight coalescing of identical
   `(range_seconds, step_seconds, 10-second window bucket)` requests. Waiters
   share only a live result/error; cancellation of one waiter does not cancel a
   query still used by others, and no result cache survives the bucket. Return
   `429` with `Retry-After` when the per-client limit is exceeded and `503` when
   the bounded concurrency queue is full. Run again; expected PASS.
5. Run:

   ```bash
   python -m ruff check app/models/monitoring.py \
     app/services/prometheus_client.py \
     tests/unit/test_monitoring_models.py \
     tests/unit/test_prometheus_client.py
   ```

   Also run the repository's configured mypy command if present; expected no new
   diagnostics.

6. Commit: `feat(api): add bounded monitoring history client`.

### Task 4: Expose typed monitoring routes

**Files:** `app/api/monitoring.py`, `main.py`, API tests.

**Steps:**

1. Write TestClient tests for exact successful response headers/body fields,
   default and boundary parameters, 422 outside bounds, empty series,
   `available=false` GEP, safe available GEP, 502/504 mapping, no IP leakage,
   429/503 mapping, coalescing, disconnect cancellation, and router
   registration/OpenAPI response models. Add compatibility tests for POI
   generation time, active-link observation/generation time, route revision
   time, and GEP cache observation time from the freshness contract.
2. Run focused tests; expected RED: 404/import failure.
3. Implement the router and include it in `main.py`.
4. Run focused tests; expected PASS. Then run:

   ```bash
   cd backend/starlink-location
   python -m pytest tests/unit/test_monitoring_api.py \
     tests/integration/test_health.py tests/integration/test_metrics_endpoint.py -q
   ```

5. Commit: `feat(api): expose typed monitoring endpoints`.

### Task 5: Proxy RainViewer bytes and lock CSP boundaries

**Files:** weather service/API/tests and Mission Planner Nginx config.

**Steps:**

1. Add tests requiring metadata fetches to use exactly
   `https://api.rainviewer.com/public/weather-maps.json` and provider tile URLs
   to use exactly `https://tilecache.rainviewer.com` (no suffix matching).
   Require every redirect target to remain on its respective exact HTTPS host,
   with no userinfo, custom port, IP literal, or localhost. DNS resolution must
   contain no private, loopback, link-local, multicast, unspecified, or reserved
   address. Resolve and pin the validated addresses for the connection to
   prevent DNS rebinding. Validate metadata host, path template, XYZ bounds,
   selected frame path/time, and final path after every redirect; either disable
   redirects or revalidate each hop with a small hop cap. Cover metadata
   failure, timeout, non-image content, streaming body cap (abort as bytes cross
   the limit), byte passthrough, `image/png`, bounded cache headers, and no
   downstream redirect. Malformed hosts/redirects return a stable safe upstream
   code and never expose URL, host, resolved IP, or body in response/log
   assertions.
2. Add `tools/tests/test_mission_planner_nginx.py` asserting CSP `img-src`
   permits only `'self'`, `data:`, existing OSM, and
   `https://server.arcgisonline.com`; RainViewer must not be in CSP because
   FastAPI proxies it. Keep `connect-src` same-origin plus the existing
   WebSocket allowances; do not add Prometheus or Grafana.
3. Run focused tests; expected RED because endpoint returns 307.
4. Implement the strict metadata-host/DNS/path/redirect checks and bounded
   streaming proxy above. Add only ArcGIS to `img-src`.
5. Run weather/config tests; expected PASS. Manually verify with `curl -I`
   during
   [Task 14](03-runtime-and-browser-acceptance.md#task-14-prove-an-exact-head-isolated-real-stack)
   through the built Mission Planner Nginx (not Vite or direct FastAPI) that the
   tile response is same-origin, not a redirect, has
   `X-Content-Type-Options: nosniff`, and that `/overview` includes the intended
   CSP.
6. Commit: `fix(weather): proxy radar tiles for browser CSP`.

### Task 6: Add frontend DTO validation and monitoring services

**Files:** frontend monitoring types/service/tests.

**Steps:**

1. Test exact API paths/query encoding, all six POI options including omitted
   query for All POIs, zod parsing, finite coordinates, null history samples,
   `poi_id` mapping, cancellation, and safe malformed failures. Assert requests
   are origin-relative. Parse and preserve every observation, generation,
   revision, and RainViewer frame timestamp without conflating client receipt.
2. Run focused Vitest; expected RED.
3. Implement DTO schemas and service functions only; do not add UI.
4. Run focused tests, `npm run lint`, and `npm run build`; expected PASS.
5. Commit: `feat(frontend): add typed overview data services`.
