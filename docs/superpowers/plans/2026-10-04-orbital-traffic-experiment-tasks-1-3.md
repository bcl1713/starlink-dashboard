# Orbital Traffic Experiment: Tasks 1–3

Read the [main plan](2026-10-04-orbital-traffic-experiment.md) and approved
spec. Its global constraints apply to every step. Backend paths below begin at
`backend/starlink-location/`; frontend paths at `frontend/mission-planner/`.

## Task 1: Confirmed orbital preference

**Files:** Modify backend `app/services/overview_link_settings.py`,
`app/api/overview_link_settings.py`,
`tests/unit/test_overview_link_settings.py`,
`tests/integration/test_overview_link_settings_api.py`; frontend
`src/services/overview-link-settings.ts` and its test, existing settings hook
tests, `src/pages/OverviewLinkSettingsCard.tsx` and its test.

**Interfaces:** Extend `OverviewLinkSettings` and the strict partial-update API
with `orbital_traffic_enabled: bool = False` (TypeScript `boolean`). GET/PUT
`/api/overview-links/settings` returns all three confirmed fields. Reuse query
key `['overview-link-settings']` and its serialized mutation scope.

- [x] Write `test_orbital_default_and_partial_merge`: an old file with both
      switches false reads orbital false; updating only orbital true leaves both
      false; then updating only X-band true leaves orbital true. Reject null,
      strings, unknown fields and empty updates; test interleaved viewer edits.
- [x] Write frontend tests `orbital_is_off_until_confirmed` and
      `late_get_cannot_restore_orbital_after_save`: malformed/missing orbital
      field is not a confirmed response; failed GET/PUT retains cached
      confirmation; canceled pre-save GET cannot overwrite a successful save.
      The switch label is exactly `Orbital traffic view`, disabled while
      unconfirmed or saving.
- [x] Run backend tests with

  ```bash
  pytest tests/unit/test_overview_link_settings.py \
  tests/integration/test_overview_link_settings_api.py -q
  ```

  from the backend, and

  ```bash
  npm run test:unit -- src/services/overview-link-settings.test.ts \
  src/hooks/api/useOverviewLinkSettings.test.ts \
  src/hooks/api/useUpdateOverviewLinkSettings.test.ts \
  src/pages/OverviewLinkSettingsCard.test.tsx
  ```

  from the frontend. Confirm the newly added assertions fail before
  implementation.

- [x] Add the field to the existing store, strict update schema, response
      validation and Configuration controls. Continue atomic partial merge; do
      not migrate saved false values using truthiness or use optimistic toggles.
- [x] Rerun the same commands; require all tests passing and the original link
      settings/API behavior intact. Commit
      `feat: persist experimental orbital view`.

## Task 2: Shared catalog and visible-viewer leases

**Files:** Create backend `app/services/orbital_catalog_models.py`,
`orbital_catalog_store.py`, `orbital_catalog_client.py`, `orbital_catalog.py`,
`orbital_viewers.py`, `app/api/orbital_catalog.py`,
`tests/unit/test_orbital_catalog.py`, `test_orbital_catalog_store.py`,
`test_orbital_viewers.py`, `tests/integration/test_orbital_catalog_api.py`, and
fixture `tests/fixtures/orbital-catalog.json`. Modify `main.py` for registration
and shutdown; create `tests/unit/test_main_orbital_catalog.py`.

**Interfaces:** `OrbitalCatalogService` owns `acquire(viewer_id: str)`,
`release(viewer_id: str)`, `get_catalog(viewer_id: str)`, `get_status()`,
`resume_provider()` and `aclose()` async methods. Inject UTC clock and
`httpx.AsyncClient` for deterministic tests. Persistent envelope contains
`generation`, `acquired_at`, `last_attempt_at`, `retry_after_at`, `suspended`,
accepted `objects`, rejected/truncated counts. IDs remain decimal strings.

Accepted object fields are `NORAD_CAT_ID` (string), `EPOCH` (UTC ISO string),
and finite numeric `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`,
`RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `BSTAR`,
`MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`. Reject missing required elements;
explicitly document any provider-approved defaults before using them. All times
in the envelope are UTC ISO strings or null. `generation` is a content hash.

HTTP contracts:

- `PUT /api/orbital/viewers/{viewer_id}` acquires/renews a 75-second lease;
  response has `expires_at`. Client renews every 30 seconds only while visible
  and enabled. Bound live leases to 128; return 429 at capacity.
- `DELETE /api/orbital/viewers/{viewer_id}` releases idempotently (204).
- `GET /api/orbital/catalog?viewer_id=...` requires a valid lease (409
  otherwise) and returns the envelope; loading/empty catalog is an empty
  `objects` array with status, so the client can retain arc fallback without
  fabricated data.
- `GET /api/orbital/status` returns diagnostics only and creates no demand.
- `POST /api/orbital/provider/resume` is explicit operator intervention; clear
  suspension but preserve cooldown/backoff and do not create viewer demand.

Additional plan decisions: store catalog at `data/orbital/catalog.json` and
provider state separately at `data/orbital/provider-state.json`; atomically
replace each under a shared file lock. Persist attempt state before network I/O.
On unreadable provider state, fail closed; explicit operator resume atomically
repairs state with a fresh attempt timestamp and a full two-hour cooldown,
preserving the last good catalog. One app-owned coordinator and cross-process
attempt lock prevent simultaneous upstream attempts. Lease expiry is maintained
only while leases exist; after the last lease, cancel the periodic refresh
timer. A bounded in-flight download may finish after demand disappears and
update the cache, but cannot reschedule.

- [x] Read CelesTrak format documentation and usage policy linked in the spec.
      Record access date and relevant limits in
      `docs/development/orbital-provider-policy.md`; do not repeatedly download
      the live GP feed or add its URL as a clickable documentation link. If
      policy conflicts with the proposed two-hour floor, adopt the longer
      allowed delay and update the plan before execution continues. Use a
      20-second timeout and a 16 MiB streamed response limit; reject oversized
      bodies without cache loss.
- [x] Write `test_catalog_validation_and_stable_subset`: validate OMM epoch,
      numeric ID, finite fields, positive mean motion, eccentricity in `[0,1)`,
      inclination in `[0,180]`, supported SGP4 elements and perigee above Earth.
      Reject duplicate IDs as ambiguous, invalid objects individually, empty/bad
      downloads as a replacement. More than 16,384 valid objects yields sorted
      numeric-ID subset; shuffled identical elements retain generation.
      Generation hashes canonical accepted elements, independently of
      acquisition time.
- [x] Write `test_attempt_clock_survives_restart_and_failure`: 20 simultaneous
      viewers make one attempt; failure still blocks until 7,200 seconds; longer
      Retry-After wins; every non-200 HTTP response persists suspension; resume
      cannot bypass cooldown. Restart after timeout, cancellation or state-file
      corruption cannot storm provider. Persist last good data despite failed
      refresh or partial disk write.
- [x] Write `test_viewer_demand_and_diagnostics`: no viewer means zero upstream
      calls/timers; status GET creates none; expired/released leases stop
      periodic work; renewed/acquired leases share cache. Epochs exactly 72
      hours old and ten minutes future are eligible; one millisecond outside is
      ineligible, even after fresh acquisition. Worker filtering will
      independently enforce expiry.
- [x] Run

  ```bash
  pytest tests/unit/test_orbital_catalog*.py \
  tests/unit/test_orbital_viewers.py \
  tests/unit/test_main_orbital_catalog.py \
  tests/integration/test_orbital_catalog_api.py -q
  ```

  confirm new tests fail.

- [x] Implement the model validator, atomic store, bounded httpx client,
      coordinator and routes, registering app-owned state at startup and closing
      clients/timers at shutdown. HTTP diagnostics include eligible/rejected
      counts, generation, attempt/retry times, suspension, truncation and
      fallback reason.
- [x] Rerun tests to green with fake provider and fake time. Verify
      registration, shutdown and cross-process lock behavior. Commit
      `feat: cache orbital catalog with demand and provider backoff`.

## Task 3: OMM propagation and worker transport

**Files:** Create frontend `src/pages/orbital/types.ts`, `coordinates.ts`,
`propagation.ts`, `worker-protocol.ts`, `orbital.worker.ts`, `worker-client.ts`,
and corresponding `coordinates.test.ts`, `propagation.test.ts`,
`worker-client.test.ts`. Create `src/services/orbital-catalog.ts` and its test.
Modify frontend `package.json` and `package-lock.json` only in this task.

**Interfaces:** Define `CatalogObject` from Task 2's validated OMM JSON,
`CatalogEnvelope`, `OrbitalEndpoints` (aircraft Earth-fixed km or null; PoP
Earth-fixed km or null), and `OrbitalSnapshot` with mount generation, catalog
generation, UTC milliseconds, ordered `ids: string[]`,
`positionsKm: Float64Array`, `valid: Uint8Array`, and Task 4's
`route: OrbitalRoute | null`. Flatten positions as `[x,y,z]` per ID. Use Float32
scene buffers for the GPU. `PropagationResult` contains `utcMs`, `ids`,
`positionsKm` and `valid` with the same meanings as snapshot fields; it does not
contain routing or mount state.

```typescript
propagateCatalog(objects: readonly CatalogObject[], utcMs: number):
PropagationResult
```

returns IDs, physical positions and validity at one UTC.
`ecefKmToScene(point: FlowPoint): FlowPoint` maps axes/scales from the main
plan. `OrbitalWorkerClient` exposes `start(catalog)`, `setEndpoints(endpoints)`,
`recycle(snapshot)`, `dispose()` and snapshot/error callbacks. Protocol messages
carry mount generation; old generations must be ignored before allocation.
Snapshot buffers are transferred, never detached while being displayed.

- [x] Verify a maintained satellite.js release supports OMM JSON via
      `json2satrec`, SGP4 propagation and GMST/Earth-fixed conversion in Vite
      module workers. Pin the verified release through npm and lockfile; record
      version/license in the provider note. Do not silently substitute TLE or an
      unverified propagator.
- [x] Write `omm_reference_coordinates`: independently sourced fixed OMM/UTC
      vector matches Earth-fixed coordinates to the reference tolerance recorded
      with the fixture; `[6378.137,0,0]` maps to `[2,0,0]`, `[0,6378.137,0]` to
      `[0,0,-2]`, `[0,0,6378.137]` to `[0,2,0]`. Preserve actual altitude, never
      a uniform shell. Reject failed/nonfinite/below-surface propagation and
      expired epochs individually; test poles, antimeridian and string IDs
      beyond 99,999.
- [x] Write `one_second_snapshots_and_backpressure`: one propagation per second,
      no frame-triggered propagation; two retained snapshots and one in flight
      at most. A slow consumer drops superseded ticks, never queues missed work.
      Reordered catalogs keep ID mapping stable; generation change resets
      buffers. Late data/error after `dispose()` cannot emit callbacks or
      allocate resources.
- [x] Run

  ```bash
  npm run test:unit -- src/pages/orbital/coordinates.test.ts \
  src/pages/orbital/propagation.test.ts \
  src/pages/orbital/worker-client.test.ts \
  src/services/orbital-catalog.test.ts
  ```

  verify red assertions first.

- [x] Implement one worker-owned one-second clock, finite filtering and
      transferable reusable buffers. Keep the UTC clock injectable for tests.
      Await buffer recycling before scheduling another update; refresh from
      current UTC after suspension, never integrate elapsed hidden-page
      intervals.
- [x] Rerun to green and run `npm run build` to verify worker bundling. Commit
      `feat: propagate orbital snapshots in a bounded worker`.
