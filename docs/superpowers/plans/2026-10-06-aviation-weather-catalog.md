# Aviation weather catalog implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this
> plan task by task in the current session.

**Goal:** Deliver the provider-neutral aviation catalog and radar compatibility
boundary as part of the owner-confirmed Phase 1 of issue 290. The
[Phase 1 plan](2026-10-06-aviation-weather-phase-one.md) owns final integration
and delivery for this foundation.

**Architecture:** Strict Pydantic and Zod contracts surround an additive FastAPI
catalog. The radar adapter reads the existing service and shares its acquisition
ownership, preserving all existing routes and rendering.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, TypeScript, Zod, pytest, Vitest.

**Spec:** [Catalog foundation](../specs/2026-10-06-aviation-weather-catalog.md).

## Global constraints

- UTC timestamps are integer epoch milliseconds; future skew at most 60 seconds.
- Encoded/decoded/GPU limits: 16/32/16 MiB for normalized single-file products.
- Grids at most 720 by 361 nodes; mask codes 0/1/2/3.
- Radar stale at 20 minutes; removed at 60 minutes or coverage expiry.
- Default-off creates no provider work; use existing ASGI disconnect ownership.
- Keep source URLs and scientific formats behind the normalization boundary.
- Isolated worktree, bounded commands and verified runtime cleanup.

## Review focus

1. Forged same-origin paths must not escape the API namespace.
2. Refresh must not extend an observation's freshness or coverage expiry.
3. Concurrent catalog and radar readers must share acquisitions.
4. Model analysis must never be labeled observed weather.
5. Failed optional weather runtime must preserve core health.

### Task 1: Strict normalized contracts

**Files:** Create `app/models/aviation_weather.py` under the backend and
`src/services/aviation-weather.ts` under the frontend, with adjacent unit tests.

**Interfaces:** Produce `AviationCatalog`, `WeatherProduct`, representation and
vertical contracts, and `parseAviationCatalog(data: unknown)`.

- [ ] Write tests for valid radar and normalized products plus malformed time,
      vertical, grid, mask, path and allocation identities.
- [ ] Run the tests and confirm the new contracts are missing.
- [ ] Implement strict Python and Zod validators with the specified limits.
- [ ] Run tests and confirm malformed inputs are rejected consistently.

### Task 2: Production catalog and radar compatibility

**Files:** Create backend `app/services/aviation_weather/catalog.py`,
`app/api/aviation_weather.py`; register the router in `main.py`; create
`tests/unit/test_aviation_weather_catalog.py`.

**Interfaces:** Consume Task 1 and existing `WeatherService.read_frame()`;
produce `radar_catalog(manifest, now_ms)` and the additive catalog route.

- [ ] Write real-service tests for off, fresh, stale, expired, provider error,
      disable, concurrent readers, capability/instance change and missing
      runtime.
- [ ] Confirm failures show the missing route/adapter.
- [ ] Implement wrapping with existing request disconnect handling.
- [ ] Verify new contracts and existing radar lifecycle tests.

### Task 3: Acceptance and handoff

**Files:** Add API documentation and a report with commands and evidence.

- [ ] Run frontend suite/build, backend contracts/lifecycle and lint.
- [ ] Review the complete diff against the spec and five review risks.
- [ ] Commit, run isolated exact-SHA Nginx/browser acceptance and record
      evidence.
- [ ] Verify task runtime teardown, push feature branch and open PR against dev.
