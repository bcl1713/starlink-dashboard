# Aviation weather GFS foundation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkboxes for tracking.

**Goal:** Deliver optional production GFS pressure-level U/V/T acquisition,
bounded scientific decoding and immutable same-origin grid delivery.

**Architecture:** One optional worker container acquires and publishes selected
model products. FastAPI exchanges small revisioned demand records through a
shared local mailbox and serves validated immutable artifacts. The worker owns
retention; response leases protect open downloads from deletion.

**Tech Stack:** Python 3.11, Pydantic/FastAPI/httpx, ecCodes/NumPy, Linux file
locks, Docker Compose, pytest, existing TypeScript/Zod compatibility parsers.

**Spec:** [Approved Phase 2](../specs/2026-10-06-aviation-weather-phase-two.md).
The [presentation plan](2026-10-06-aviation-weather-gfs-presentation.md)
consumes this PR's contracts. This PR alone does not complete Phase 2.

## Global constraints

| Owner/selection | Required limits and meaning                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Boundary        | No production acceptance imports or scientific parsing in API/browser; lazy worker-only scientific imports                                  |
| Settings        | Default-off winds/temperature; 85000/50000/30000/25000/20000 Pa, default 50000 Pa                                                           |
| Time            | Horizons/leads 0/3/6/9/12/18/24/36/48 hours; nearest available instant, earlier tie; no mixed runs/interpolation/outside-range substitution |
| Decoder         | One CPU/decoder, 1 GiB RAM, queue 16; 120-second deadline, ten-second termination grace                                                     |
| HTTP            | Two exchanges, 20 attempts/minute, 30-second deadline; 32 MiB object, 256 MiB expanded, persistent 5 GiB/day                                |
| Disk            | 4 GiB including staging 1 GiB/published 2.5 GiB/reserve 0.5 GiB; two runs, admitted selections only                                         |
| Freshness       | Stale run+9h, unavailable run+18h or outside validity; failures never renew age                                                             |
| Grid            | 720×361; longitude -180/+0.5, latitude +90/-0.5; Int16-LE scale 0.01 offsets 0/0/273.15; Uint8 mask 0–3                                     |
| Browser         | Shared 16/32/16 MiB encoded/decoded/GPU, four operations, 45 seconds; total 128/64 MiB includes radar 96/48 MiB                             |
| Checks          | Explicit wall limits/cleanup; exact-SHA production evidence and required CI before review/merge into dev                                    |

## Review focus

1. Settings changes during publication cannot expose an old-selection product.
2. Source replacement between index and range reads cannot create a mixed grid.
3. Partial downloads and API/worker crashes cannot leak reservations or leases.
4. Restart/clock rollback cannot reset acquisition budgets or renew weather age.
5. A missing worker must leave Phase 1 settings/catalog and core health usable.

## File and protocol map

Create backend app/models/aviation_grid.py and production package
app/services/aviation_weather/gfs/. Tasks below own each named module; backend
paths are relative to backend/starlink-location.

Mailbox and artifact paths come only from deployment configuration. Mailbox
contains persistent `.control.lock`, `demand.json`, `ack.json`, `budget.json`
and `leases/`; artifact storage contains `staging/`, `products/`, `current.json`
and persistent publication locks. Use UID 1000 in both containers. API mounts
artifacts read-only and mailbox read-write; worker mounts both read-write and
settings read-only. File names are fixed or validated hashes, never user paths.

| IPC condition           | Required protocol                                                                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Locks                   | Persistent flock inodes; acquire control before settings-store lock, never reverse; worker holds worker.lock through owned child lifetimes                                                       |
| Save/publication        | Commit settings, invalidate old demand and advance revision under control lock; worker rechecks settings/revision under that lock before pointer swap                                            |
| Disable acknowledgement | Release control lock before waiting; worker acknowledges only after obsolete HTTP/decoder work stops and is reaped; API immediately denies obsolete payloads                                     |
| Missing acknowledgement | Wait at most 15 seconds, then sanitized 503; committed disabled state stays disabled. A successful nonblocking worker.lock acquisition proves absent ownership; missing heartbeat alone does not |
| Demand                  | Current revision only; catalog reads renew 120-second lease; monotonic deadline locally plus UTC expiry; backwards clock jump invalidates demand                                                 |
| Process identity        | API/worker startup UUIDs prevent stale shutdown revoking replacement ownership; five-second heartbeat, stale over fifteen seconds denies admission                                               |
| Reader recovery         | API shutdown withdraws its own demand; crashes expire. Response lock release, rather than PID alone, permits retention deletion                                                                  |

## Task 1: Production contracts and compatible settings

**Files:** Create `app/models/aviation_grid.py`; modify
`app/services/aviation_weather/settings.py` and
`frontend/mission-planner/src/services/aviation-weather.ts`; tests
`tests/unit/test_gfs_contracts.py`, `tests/unit/test_gfs_settings.py` and
existing `src/services/aviation-weather.test.ts`. Backend paths are relative to
`backend/starlink-location` unless explicitly prefixed.

**Interfaces:** Frozen source records and candidate:

```text
GfsSelection(pressure_pa: int, horizon_hours: int)
SourceRef(key: str, etag: str, size: int)
RangeRef(source: SourceRef, start: int, end: int, quantity: str, pressure_pa: int | None)
SourceBundle(run_at_ms: int, lead_seconds: int, ranges: tuple[RangeRef, ...], paths: tuple[Path, ...], hashes: tuple[str, ...], retrieved_at_ms: int)
GridCandidate(descriptor: GridDescriptor, directory: Path)
```

GridDescriptor contains schema/representation, product/instance hashes, version,
grid/vertical/run/lead/valid identity and u/v/t/mask buffer records declaring
confined path/hash/length/dtype and matching quantity/unit/scale/offset.
Envelope identities are distinct; hard-linked immutable buffers share disk
storage.

- [ ] Test old boolean migration: winds/temperature=false, pressure=50000,
      horizon=0; partial updates and no-op revision work; empty/null/unsupported
      updates fail. Assert buffer lengths 519840/519840/519840/259920; reject
      external paths, inconsistent identity/time/units and false allocations.
- [ ] Run; expect missing contracts/fields to fail:

  ```sh
  timeout --kill-after=10s 5m uv run --with-requirements requirements-dev.txt pytest tests/unit/test_gfs_contracts.py tests/unit/test_gfs_settings.py -q
  ```

- [ ] Add settings keys `winds`, `temperature`, `gfs_selection` and strict
      frontend compatibility parsing/defaults; keep `AviationLayer` as the
      existing bulletin union. Keep model descriptors inside the JSON payload
      contract rather than adding unrecognized keys to old envelope shapes.
- [ ] Run those tests and focused `aviation-weather.test.ts`; expect PASS.
- [ ] Commit `feat: define production GFS grid and selection contracts`.

## Task 2: Bounded inventories, version-pinned ranges and persistent quotas

**Files:** Create `gfs/inventory.py`, `gfs/transport.py`, `gfs/quota.py`; tests
`tests/unit/test_gfs_inventory.py`, `tests/unit/test_gfs_transport.py`,
`tests/unit/test_gfs_quota.py`.

**Interfaces:** `discover_runs(body: bytes) -> tuple[int, ...]`,

```text
select_ranges(index: bytes, source: SourceRef, run_at_ms: int, lead_seconds: int, pressures_pa: tuple[int, ...]) -> tuple[RangeRef, ...]
select_time(run_at_ms: int, leads: tuple[int, ...], target_ms: int) -> int | None
```

`GfsTransport.acquire(selection: GfsSelection, stage: Path) -> SourceBundle` and
`aclose() -> None` are async. `GfsQuota.reserve(bytes_: int) -> str`,
`charge(token: str, received_bytes: int) -> None`, `release(token: str) -> None`
persist atomic accounting; outstanding transfer concurrency/attempts are
bounded.

- [ ] Reject duplicate/unordered offsets, missing U/V/T/surface pressure,
      oversized/paginated listings, unsupported horizons and future runs;
      earlier instant wins ties. Range=200, ETag change, wrong bounds,
      truncation and timeout publish nothing. Attempt 21/60s and >5 GiB/day fail
      after restart; clock rollback never resets the ledger.
- [ ] Run the three new test files with the Task 1 bounded uv command; expect
      missing source acquisition/accounting to fail.
- [ ] Implement allowlisted HTTPS with inherited TLS/proxy and User-Agent. Bound
      XML/index to 1 MiB, discovery to two days/eight cycles and bounded
      pagination. HEAD before/after index; require identical strong ETag/size.
      If-Match every range and verify final validator. Range ends use next
      offset or object size. Atomic hashed stages retain private lineage; charge
      failed bytes too. Every exit deletes partials and releases reservations.
- [ ] Run tests to PASS; verify cancellation closes HTTP streams and frees owned
      slots without cancelling another admitted exchange.
- [ ] Commit `feat: acquire bounded version-pinned GFS selections`.

## Task 3: Scientific normalization and atomic retained artifacts

**Files:** Create `gfs/decode.py`, `gfs/grid.py`, `gfs/store.py` and
`backend/starlink-location/requirements-gfs.txt`; tests
`tests/unit/test_gfs_decode.py`, `tests/unit/test_gfs_grid.py`,
`tests/unit/test_gfs_store.py`. Reuse algorithms, not imports, from
`tools/acceptance/aviation_weather_proof/gfs.py` and `grid.py`.

**Interfaces:** `decode_bundle(bundle: SourceBundle) -> DecodedFields` returns
run/lead identity, Float64 coordinate axes, pressure-keyed Float32 U/V/T and
Bool validity arrays, plus Float32 surface-pressure/Bool validity arrays. Define
that frozen DecodedFields record here.

```text
normalize_grid(fields: DecodedFields, selection: GfsSelection, destination: Path) -> GridCandidate
```

`GfsProductStore.publish(candidate: GridCandidate, revision: int) -> None`,

```text
read_current(selection: GfsSelection, now_ms: int) -> tuple[GridDescriptor, ...]
```

`lease(instance: str) -> contextlib.AbstractContextManager[GridDescriptor]`,
`prune(now_ms: int) -> None`. Response locks live in mailbox `leases/`.

- [ ] Reject inconsistent metadata, duplicate/trailing GRIB, unsupported
      grid/units/basis and quantization overflow. Check seam/pole/orientation
      and zero/missing. Below-terrain pressure is mask 1, missing surface
      pressure mask 2; all contributors valid. Hash source/run/lead/vertical
      into identity. Crash before pointer swap and quota failure preserve
      current; held response leases prevent pruning.
- [ ] Pin minimal worker requirements from the proof's Python-3.11-compatible
      ecCodes/NumPy pins, excluding satellite packages. Run the new files with
      Task 1's bounded uv command plus the worker requirements; expect missing
      implementation to fail. Decoder tests generate actual GRIB fixtures.
- [ ] Implement lazy ecCodes/global coordinate verification and conservative
      resampling with below-terrain masks before regridding. Quantize once, cap
      expansion at 256 MiB and retain private lineage. Fsync
      candidates/pointers, check revision under control lock, and acquire
      response locks before opening files. Recover abandoned stages/reservations
      under ownership locks; retain two runs and release response locks on
      disconnect/finally.
- [ ] Run tests to PASS and compare dated real-source replay with the
      independent proof oracle at ten seam/pole/ordinary coordinates within 0.01
      physical units after quantization. Record decode CPU/wall/peak RSS.
- [ ] Commit `feat: normalize and retain immutable GFS grids`.

## Task 4: Cross-process demand and optional worker packaging

**Files:** Create `gfs/ipc.py`, `gfs/worker.py`,
`backend/starlink-location/Dockerfile.gfs`, `docker-compose.gfs.yml` using Task
3's worker requirements; modify backend Dockerfile only to create UID-1000
mailbox/artifact mount points; tests `tests/unit/test_gfs_ipc.py`,
`tests/unit/test_gfs_worker.py`, `tools/tests/test_gfs_compose.py`.

**Interfaces:**
`GfsMailbox.renew(owner: str, settings: AviationSettings, now_ms: int) -> None`,
`withdraw(owner: str) -> None`, `invalidate(revision: int) -> None`,
`acknowledged(revision: int) -> bool`; async `GfsWorker.run() -> None`,
`aclose() -> None` own all exchanges and the one disposable decoder child. Poll
demand at most once/second and heartbeat every five seconds; reject admission
from a missing/stale heartbeat over fifteen seconds.

- [ ] Write actual two-process tests for disable during decode/publication,
      stale revision after replacement, reader expiry at 120 seconds, API
      restart and worker death. Assert no obsolete pointer/accessible payload,
      siblings survive one reader disconnect, queue <=16, acknowledged
      cancellation has no owned child and signal/timeout cleanup leaves no
      staged reservations.
- [ ] Run those tests with bounded commands; expect missing IPC/worker to fail.
- [ ] Implement the protocol, deduplicated scheduling and owned child groups.
      Parent-death/exit/signal cleanup sends TERM, waits ten seconds, kills only
      verified survivors and reaps. Package Task 3 dependencies in optional
      Compose profile gfs: one CPU/1 GiB, no worker port, private
      product/control volumes, settings read-only. Keep scientific packages out
      of API image; preserve Docker/proxy/CA/credentials and never bake secret
      trust into images.
- [ ] Run tests and inspect the bounded worker/mount configuration:

  ```sh
  docker compose -f docker-compose.yml -f docker-compose.gfs.yml --profile gfs config
  ```

- [ ] Commit `feat: run GFS ingestion in an isolated optional worker`.

## Task 5: Nonblocking API projection and revision-safe payload responses

**Files:** Create `gfs/bridge.py`; modify `app/api/aviation_weather.py`,
`main.py` runtime initialization/shutdown and settings-save orchestration; tests
`tests/unit/test_gfs_api.py`, existing
`tests/unit/test_main_aviation_weather.py`. Update
`docs/api/aviation-weather.md`.

**Interfaces:** Async
`GfsBridge.settings_changed(settings: AviationSettings) -> None`,
`products(settings: AviationSettings, now_ms: int) -> list[WeatherProduct]`,

```text
response(instance: str, filename: str, settings: AviationSettings, now_ms: int) -> Response | None
```

`aclose() -> None`. Setting persistence and invalidation use Task 4's common
lock.

- [ ] Worker absence leaves model unavailable and radar/bulletins/settings/
      health usable; catalog does not await ingest. Old compatible run stays
      labeled; stale at 9h, unavailable at 18h; failures never renew expiry.
      Direct payload rejects disabled/expired/obsolete/traversal; verify hashes,
      ETags/type/length, disconnect lock release and two-process save/publish
      race.
- [ ] Run new/existing API tests with bounded uv command; expect failure.
- [ ] Attach optional bridge to lifespan and append model envelopes without
      duplicating AWC/radar work. Serve only current compatible grid.json and
      u/v/t/mask.bin, with response lease. Disable denies immediately and awaits
      worker acknowledgement; catalog never awaits decoding. Keep wire schemas
      compatible with Task 1 parsers.
- [ ] Run targeted backend/API and frontend parser regression tests to PASS.
- [ ] Commit `feat: serve revision-safe GFS model products`.

## Task 6: Foundation acceptance and PR handoff

**Files:** Create tools/acceptance/gfs-weather/{run.sh,compose.yml,
source_fixture.py,check_foundation.py,README.md}; test
tools/tests/test_gfs_acceptance_runner.py. Modify tools/verify's scientific test
requirements; keep API packaging separate. Add dated docs/reports evidence.

- [ ] Test dirty/wrong SHA, absent provisioned browser, stale acknowledgement,
      killed decoder, missing measurements and missing cleanup all prevent PASS.
- [ ] Implement the runner below using production images/Nginx and acceptance
      platform helpers. Own project starlink-290-gfs-foundation, ports
      15292/18292 and private volumes before allocation. Fixture only source
      transport with pinned GRIB/index bytes; use real
      worker/IPC/normalizers/API and existing Phase 1/radar browser regression
      journeys.

  ```sh
  timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh <SHA> <browser> foundation
  ```

- [ ] Run bounded backend verification (20 minutes) and focused frontend
      parsers; require static checks and CI on committed head. Foundation
      acceptance must verify Nginx U/V/T/masks, cancellation/denial,
      source-version mismatch and core health under saturation/failure, with
      unchanged Phase 1/radar controls.
- [ ] Preserve exact SHA/images/source hashes, samples, CPU/RSS, disk/network,
      screenshots and fixture/software-rendering labels. Check recorded host
      processes/listeners and Compose containers/networks/volumes absent after
      success and failure. Commit report; verify the final candidate after
      changes.
- [ ] Push foundation PR against dev; require independent whole-branch review
      and required CI. Phase 2 stays incomplete pending presentation. Stop
      runtime resources immediately; retain open-PR worktree. After verified
      merge, clean only owned worktree/branches/temporary paths per AGENTS.md.
