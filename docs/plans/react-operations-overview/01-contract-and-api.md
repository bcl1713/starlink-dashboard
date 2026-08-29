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
    observed_at: datetime
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
- A server timeout, response-size/point ceiling of
  `6 * (range_seconds / step_seconds + 1)`, cancellation propagation, and no
  query text, hostname, URL, headers, or credentials accepted from a request.
- `NaN`, `+Inf`, and `-Inf` normalized to `null`; timestamps normalized to UTC;
  series always returned in the literal order above, including empty samples.
- `502` with a stable safe detail code for malformed/upstream error and `504`
  for timeout; never include internal URL or response bodies.

Create `GET /api/monitoring/ground-entry-point` returning
`GroundEntryPointResponse`. It reads `get_cached_ground_entry_point()` only and
returns HTTP 200 with `available=false` and null details when no cached value
exists; it must not trigger internet discovery on request.

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

## Exact file map

### Backend

- Create: `backend/starlink-location/app/models/monitoring.py`
- Create: `backend/starlink-location/app/services/prometheus_client.py`
- Create: `backend/starlink-location/app/api/monitoring.py`
- Modify: `backend/starlink-location/app/api/weather.py`
- Modify: `backend/starlink-location/app/services/weather_radar.py`
- Modify: `backend/starlink-location/main.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_models.py`
- Create: `backend/starlink-location/tests/unit/test_prometheus_client.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_api.py`
- Modify: `backend/starlink-location/tests/unit/test_weather_api.py`

### Frontend

- Modify: `frontend/mission-planner/package.json`
- Modify: `frontend/mission-planner/package-lock.json`
- Create: `frontend/mission-planner/vitest.config.ts`
- Modify: `frontend/mission-planner/src/App.tsx`
- Modify: `frontend/mission-planner/src/index.css`
- Modify: `frontend/mission-planner/nginx.conf`
- Create: `frontend/mission-planner/src/types/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.test.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewGrid.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewControls.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/WorldClocks.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ClockSettings.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OperationalMap.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/LayerDisclosure.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/POIQuickReference.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricChart.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricSummary.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ObstructionGauge.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/GroundEntryPointCard.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/useOverviewData.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/preferences.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/history.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/geometry.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/formatters.ts`
- Create tests beside pure/component modules as `*.test.ts(x)`.
- Create: `frontend/mission-planner/tests/e2e/overview.spec.ts`
- Create: `frontend/mission-planner/tests/e2e/overview-continuity.spec.ts`
- Create: `frontend/mission-planner/tests/e2e/fixtures/overview.ts`
- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`

Keep production TypeScript files near or below the repository's 300-line target;
split components rather than creating a monolithic dashboard page.

## Test-first API tasks and commit boundaries

### Task 3: Add strict monitoring models and allow-listed Prometheus client

**Files:** Backend monitoring models/client and their unit tests from the
[exact file map](#exact-file-map).

**Steps:**

1. Test exact model schema, UTC serialization, forbidden extra keys, stable
   series ordering, parameter bounds, fixed query map, exact
   `/api/v1/query_range` parameters, timeout, cancellation, malformed JSON,
   upstream error, empty results, point ceiling, and non-finite normalization.
2. Explicitly test that caller PromQL, URL, hostname, and headers cannot enter
   the client API.
3. Run focused tests and observe import failures:

   ```bash
   cd backend/starlink-location
   python -m pytest tests/unit/test_monitoring_models.py \
     tests/unit/test_prometheus_client.py -q
   ```

4. Implement strict Pydantic DTOs and a small async `httpx` client with the six
   constant expressions. Run again; expected PASS.
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

1. Write TestClient tests for exact successful response heads/body fields,
   default and boundary parameters, 422 outside bounds, empty series,
   `available=false` GEP, safe available GEP, 502/504 mapping, no IP leakage,
   and router registration/OpenAPI response models.
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

1. Add tests for valid XYZ bounds, provider metadata failure, tile timeout,
   non-image/wrong content type, maximum body size, byte passthrough,
   `image/png`, bounded cache headers, and no redirect/`Location` header.
2. Add a config test asserting CSP `img-src` permits only `'self'`, `data:`,
   existing OSM, and `https://server.arcgisonline.com`; RainViewer must not be
   in CSP because FastAPI proxies it. Keep `connect-src` same-origin plus the
   existing WebSocket allowances; do not add Prometheus or Grafana.
3. Run focused tests; expected RED because endpoint returns 307.
4. Implement backend streaming/byte proxy with a fixed provider host obtained by
   the existing metadata service, strict tile validation, timeout and body cap.
   Add only ArcGIS to `img-src`.
5. Run weather/config tests; expected PASS. Manually verify with `curl -I` after
   [Task 13](03-runtime-and-browser-acceptance.md#task-13-add-browser-acceptance-and-temporal-evidence)
   that the tile response is same-origin, not a redirect, has
   `X-Content-Type-Options: nosniff`, and that `/overview` includes the intended
   CSP.
6. Commit: `fix(weather): proxy radar tiles for browser CSP`.

### Task 6: Add frontend DTO validation and monitoring services

**Files:** frontend monitoring types/service/tests.

**Steps:**

1. Test exact API paths and query encoding, zod parsing, finite coordinate
   validation, null history samples, `poi_id` mapping, cancellation, and safe
   malformed-response failures. Assert requests are origin-relative.
2. Run focused Vitest; expected RED.
3. Implement DTO schemas and service functions only; do not add UI.
4. Run focused tests, `npm run lint`, and `npm run build`; expected PASS.
5. Commit: `feat(frontend): add typed overview data services`.
