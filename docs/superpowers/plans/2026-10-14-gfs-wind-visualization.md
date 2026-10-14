# GFS Wind Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace GFS wind barbs with a wind-speed gradient, animated flow
trails, and a knots legend; enforce exclusive wind/temperature selection across
displays.

**Architecture:** Retain the existing GFS worker, grid admission, and controller
ownership. Enforce mode selection in the settings store and frontend parser;
extract the existing atmospheric mesh into a reusable raster owner, then attach
a bounded particle owner only to wind drawings. Drive motion through React Three
Fiber, using the existing controller lifecycle and weather budget.

**Tech Stack:** Python/FastAPI/Pydantic/filelock, TypeScript/React/Zod,
Three.js, React Three Fiber, Vitest, pytest, Playwright, and the existing Docker
acceptance runner. No new dependency or data provider.

**Spec:**
[Approved wind visualization design](../specs/2026-10-14-gfs-wind-visualization-design.md).

**Status:** Approved for native implementation by the user on 2026-10-14.
Hardware performance remains unverified until its target is identified; software
browser acceptance and hardware performance approval are separate.

## Global Constraints

- Implement in a feature worktree based on the latest `origin/dev`, with a PR
  against `dev`. Keep the primary checkout on `dev`. The inspected code base is
  `aef333d46a30c131f61a5de3bfe318c6a7618f43`; this documentation branch adds the
  approved spec. Carry the approved documents into the feature branch if their
  documentation PR has not merged. Record and review any intervening code diff.
  At feature setup, record `GFS_WIND_BASE_SHA` as the full pre-change dev SHA;
  use that same SHA for static-policy and paired baseline controls.
- Exactly three modes: both false is off; wind true implies temperature false;
  temperature true implies wind false. No particles over temperature.
- Preserve existing shared level/horizon, confirmation and five-second settings
  polling. Default-off additions, corrupt-file behavior, schema, masks, NOAA
  attribution, original freshness/expiry, and radar/bulletin behavior remain.
- Unrounded speed is `hypot(U, V) * 1.9438444924406` knots after conservative
  bilinear U/V interpolation. Do not round to barb increments or interpolate
  precomputed magnitudes. Invalid data is unknown, not zero.
- Palette: 0 `#1d4ed8`, 25 `#06b6d4`, 50 `#22c55e`, 75 `#eab308`, 100 `#f97316`,
  125 `#ef4444`, 150+ `#a855f7`; linear sRGB interpolation, opacity 0.45. Only
  displayed color saturates at 150 kt.
- At most 2,000 particles, 12 retained trail samples each at 30 Hz, staggered
  lifetimes at most six seconds, visual multiplier 12,000, integration steps at
  most 50 ms. Discard suspended time; no invented minimum wind speed.
- Shared optional-weather limits remain 16 MiB encoded, 32 MiB decoded/geometry,
  16 MiB GPU, four fetch/decode operations, and old-plus-candidate accounting.
  Keep each drawing within the existing envelope's 12 MiB decoded / 4 MiB GPU
  allocation declarations; do not silently increase them.
- Preallocate animation buffers. No particle/frame React state changes, new
  timers, forecast playback, user particle controls, or retained barb mode.
- Stop/dispose on disable, mode/selection change, hide, offline, expiry, and
  unmount. Reduced motion disables particles without a grid fetch.
- Every test/resource-owning run has an explicit wall limit and termination
  grace. Record ownership and verify scoped cleanup on success and failure.

## Review Focus

1. A legacy repair can bypass GFS demand invalidation or invert control/settings
   lock order; Task 1 tests repaired revisions with existing live demand.
2. A failed save may already have persisted a revision while worker
   acknowledgement fails; Task 2 tests confirmed UI state and subsequent
   revision reconciliation.
3. A preference change can arrive while a replacement grid is pending; Task 4
   tests that the newly admitted drawing observes the latest motion preference.
4. An entirely masked grid or extreme encoded winds can cause endless respawn or
   invalid geometry; Task 4 tests fixed work bounds and finite output.
5. The existing production proof enables both layers and rewrites the
   temperature texture to measure U/V; Task 5 measures each new native shader
   separately and fails if evidence is missing or only checks diagnostic output.

## File Map and Task Boundaries

Paths below are relative to the repository root. `F` abbreviates
`frontend/mission-planner`; `B` abbreviates `backend/starlink-location`; `A`
abbreviates `F/src/pages/aviation-weather`. Expand these in shell commands.

| Task                       | Production files                                                                                                                                                                                                                              | Tests / evidence                                                                                                                                                                                          |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1: Settings ownership      | `B/app/services/aviation_weather/settings.py`, `B/app/services/aviation_weather/gfs/bridge.py`, `B/app/api/aviation_weather.py`, `B/main.py`                                                                                                  | `B/tests/unit/test_gfs_settings.py`, `test_gfs_api.py`, `test_gfs_store.py`, `test_gfs_worker.py`, `test_gfs_ipc.py`, `test_main_aviation_weather.py`; `tools/acceptance/gfs-weather/check_foundation.py` |
| 2: Exclusive UI mode       | Create `F/src/services/gfs-mode.ts`; modify `F/src/services/aviation-weather.ts`, `A/AviationSettingsCard.tsx`, `A/gfs-controller.ts`                                                                                                         | Create `F/src/services/gfs-mode.test.ts`; extend `F/src/services/aviation-weather.test.ts`, `A/AviationSettingsCard.test.tsx`, `A/gfs-controller.test.ts`                                                 |
| 3: Raster and key          | Create `A/wind-scale.ts`, `A/grid-raster.ts`; modify `A/grid-shader.ts`, `A/grid-renderer.ts`, `A/GfsStatus.tsx`, `A/AviationWeather.css`; remove production `A/wind-barbs.ts`                                                                | Create `A/wind-scale.test.ts`; extend `A/grid-renderer.test.ts`, `A/GfsStatus.test.tsx`, `F/src/pages/OverviewMapLegend.test.tsx`; remove production `A/wind-barbs.test.ts`                               |
| 4: Particles and lifecycle | Create `A/wind-particles.ts`, `A/wind-particle-drawing.ts`; modify `A/grid-sampling.ts`, `A/grid-renderer.ts`, `A/gfs-controller.ts`, `A/GfsLayer.tsx`, `F/src/hooks/useGfsWeather.ts`                                                        | Create `A/wind-particles.test.ts`, `A/wind-particle-drawing.test.ts`, `A/GfsLayer.test.tsx`; extend `A/grid-renderer.test.ts`, `A/gfs-controller.test.ts`; create `F/src/hooks/useGfsWeather.test.tsx`    |
| 5: Production acceptance   | Extend `tools/acceptance/gfs-weather/runner.py`, `README.md`, `F/tests/e2e/gfs-weather-production.spec.ts`; create `F/tests/e2e/support/gfs-wind-probe.ts`, `F/tests/e2e/gfs-wind-performance.spec.ts`, `F/playwright.gfs-hardware.config.ts` | Extend `tools/tests/test_gfs_acceptance_runner.py`; update `docs/api/aviation-weather.md`, `docs/features/overview-weather.md`; create `docs/reports/2026-10-14-gfs-wind-visualization.md`                |

Keep the historical diagnostic renderer under
`F/tests/e2e/support/aviation-weather-proof/` and its tests intact: it documents
a previous proof, not the current production mode. Remove production barb
imports and production-specific assertions; retain signed sampling and
geographic tests.

Execute Tasks 1–5 in order. Each task has its own red/green checks and commit.

## Task 1: Exclusive Settings, Legacy Repair, and Demand Ownership

**Interfaces:** Preserve `AviationSettingsStore.get()` and
`update(changes: dict)`. `get()` returns an effective wind-precedence snapshot
without writing. Add `repair_legacy() -> tuple[AviationSettings, bool]`, where
the flag reports an atomic persisted repair. Add
`GfsBridge.read_settings() -> AviationSettings` (async) and its synchronous
`_read_settings()` helper.

- [x] Add named failing tests in `test_gfs_settings.py`:
      `test_partial_enable_disables_other_layer_in_one_revision`,
      `test_explicit_both_true_is_rejected_without_write`,
      `test_legacy_repair_is_atomic_and_idempotent`,
      `test_readonly_legacy_snapshot_never_writes`, and
      `test_concurrent_mode_saves_commit_exclusive_revisions`. Required
      assertions:

  ```python
  before = store.update({"temperature": True})
  after = store.update({"winds": True})
  assert (after.winds, after.temperature) == (True, False)
  assert after.revision == before.revision + 1
  assert store.update({"winds": True}).revision == after.revision
  ```

  Write a raw legacy JSON fixture with both true and revision 7; repair must
  persist wind-only revision 8 exactly once, preserving non-GFS fields and
  selection. A read-only store returns wind-only revision 7 with unchanged file
  bytes. Repeated concurrent saves must yield unique ordered committed revisions
  with no both-true snapshots. Empty/null/unsupported changes remain invalid.

- [x] Add route/bridge tests in `test_gfs_api.py` and startup coverage in
      `test_main_aviation_weather.py`: both-true PUT returns 422, file/demand
      stay unchanged, and GET/startup legacy repair clears old demand before
      returning the repaired revision. Test missing worker acknowledgement and
      lock contention with bounded deadlines. Use real stores/mailboxes and the
      existing child-worker fixtures; do not mock away revision invalidation.
- [x] Run from `B`, expecting the new exclusivity/repair assertions to FAIL:

  ```sh
  timeout --kill-after=10s 5m uv run --with-requirements requirements-dev.txt --with-requirements requirements-gfs.txt pytest tests/unit/test_gfs_settings.py tests/unit/test_gfs_api.py tests/unit/test_main_aviation_weather.py -q
  ```

- [x] Implement effective normalization without changing raw `_read()` data.
      `AviationSettingsUpdate.changes()` rejects explicitly both true before
      guarded runtime operations; preserve route validation status 422.
      `update()` validates first, takes the file lock, combines legacy
      normalization with the requested change, clears the counterpart on enable,
      and persists at most one revision using the existing
      tempfile/fsync/replace sequence. Repeated saves are no-ops.
- [x] Implement `repair_legacy()` under the settings lock, refusing writes for
      read-only stores. Bridge `_read_settings()` takes the mailbox control lock
      **before** the settings lock, repairs, then invalidates demand for the
      repaired revision before releasing control. `read_settings()` delegates
      through `asyncio.to_thread`; it does not wait for ingest. `_save()`
      continues to invalidate the single final update revision. Never acquire
      mailbox control from inside the settings lock.
- [x] Route settings GET and catalog settings reads through the bridge helper
      when present; fallback to the writable store's repair when there is no
      bridge. Initialize repair after bridge construction and before startup
      completes, preserving optional-weather startup failure isolation. Product
      admission and read-only worker `get()` calls only normalize; they do not
      repair or nest control locks. Preserve PUT's existing
      worker-acknowledgement behavior.
- [x] Update both-true fixtures in `test_gfs_api.py`, `test_gfs_store.py`, and
      `test_gfs_worker.py` to one admitted mode, parametrizing independent wind
      and temperature controls where necessary. In `check_foundation.py`,
      replace the combined enable with sequential modes: capture/verify wind
      descriptor and components, switch to temperature and verify its
      identity/components, confirm old wind URLs are denied, then restore wind
      for cancellation controls. Retain all original hash, mask, expiry, worker
      and core-response evidence.
- [x] Run the focused command and `pytest tests/unit/test_gfs_*.py -q` through
      the same uv environment with a 10-minute limit; require PASS, no hangs,
      and no owned workers left. Commit
      `feat: enforce exclusive GFS settings and legacy repair`.

## Task 2: Confirmed Exclusive Configuration and Frontend Admission

**Interfaces:** `gfs-mode.ts` exports
`GfsFlags = { winds: boolean; temperature: boolean }` and
`resolveGfsFlags(flags: GfsFlags): GfsFlags`, returning wind precedence if both
true. Re-export `GfsFlags` from `gfs-controller.ts` for existing imports.
`parseAviationSettings(data: unknown): ResolvedAviationSettings` retains its
signature, normalizing the flags after strict parsing.

- [x] Write `gfs-mode.test.ts` with all four boolean combinations and tests that
      normalization never mutates the input. Extend parser tests with both-true
      revision 7: expect wind-only revision 7, unchanged level/horizon and
      non-GFS fields; malformed values still fail parsing.
- [x] Extend Configuration tests using the real shared QueryClient and existing
      API boundary fixtures. `enabling wind atomically replaces temperature`
      starts in temperature mode and asserts the exact request and confirmed
      switches:

  ```typescript
  expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
    winds: true,
    temperature: false,
  });
  expect(screen.getByRole("switch", { name: "GFS winds" })).toBeChecked();
  expect(
    screen.getByRole("switch", { name: "GFS air temperature" }),
  ).not.toBeChecked();
  ```

  Add the inverse, both-off, failed save, and save rejection after persisted
  revision followed by polling reconciliation. Last confirmed cache data stays
  visible on rejection; a subsequent higher revision updates both switches.

- [x] Add `legacy mode admits only wind` in `gfs-controller.test.ts`: supply a
      both-true input and a catalog containing both entries; only wind is
      loaded, drawn, and published. Selection/horizon and incompatible-drawing
      removal are unchanged. Run these tests plus `aviation-weather.test.ts` and
      `AviationSettingsCard.test.tsx` from `F` with the command below; expect
      FAIL before implementation.

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/services/gfs-mode.test.ts src/services/aviation-weather.test.ts src/pages/aviation-weather/AviationSettingsCard.test.tsx src/pages/aviation-weather/gfs-controller.test.ts
  ```

- [x] Implement the helper/parser and atomic toggle mutations. Turning either
      switch off never enables its counterpart. Add helper copy: **Only one GFS
      layer can be displayed at a time.** Keep the shared selection, Surface
      disabled, pending-control disable, error handling, and confirmed-cache
      behavior. The controller consumes normalized settings; Overview never
      writes preferences to repair old snapshots.
- [x] Rerun the named tests to PASS and commit
      `feat: make GFS Configuration toggles mutually exclusive`.

## Rendering and Acceptance Tasks

Continue with [Tasks 3–4: rendering and lifecycle](2026-10-14-gfs-wind-visualization-rendering.md)
and [Task 5: acceptance and delivery](2026-10-14-gfs-wind-visualization-acceptance.md).
The task content is unchanged; the split keeps each document within the
repository's 300-line limit.

## Coverage and Execution Handoff

Tasks 1–2 implement configuration, legacy compatibility, and synchronized
exclusive admission. Task 3 implements the fixed-scale raster, mask semantics,
and legend. Task 4 implements physical flow direction, bounded animation,
reduced motion, and ownership. Task 5 verifies real source/CPU/GPU agreement,
production views, lifecycle, budgets, and separate hardware performance gates.

The user approved this plan for native execution on 2026-10-14. Execute the five
tasks sequentially with an independent whole-branch review. H1 remains a
required input for hardware performance approval, rather than a software
correctness claim.
