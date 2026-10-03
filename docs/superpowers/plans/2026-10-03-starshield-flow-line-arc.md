# Starshield Flow Line Arc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` for recommended native execution, or
> `superpowers:subagent-driven-development` if the user selects delegation.
> Implement task by task and track the checkbox steps below.

**Goal:** Show measured Starshield traffic on an aircraft–PoP arc, independent
illustrative X-band activity, and two durable Configuration visibility switches.

**Architecture:** Add a dedicated settings store/API using the existing atomic
file persistence and shared React Query conventions. Build a bounded elevated
arc from existing endpoint projections; derive each link's visibility and
activity independently, then reuse the buffer-based particle renderer with
explicit clearing and visibility lifecycle handling.

**Tech Stack:** FastAPI/Pydantic, filelock, React 19, TypeScript, React Query,
Three.js/React Three Fiber, Vitest/Testing Library, pytest and Playwright/CDP.
No new product dependency is needed.

**Spec:** [Approved traffic arc and link controls design](../specs/2026-10-03-overview-traffic-paths-design.md).

**Authority:** The user requested implementation planning on 2026-10-03. This
plan implements the already approved architectural design; product execution
awaits plan review. “Starlink flow line arc” refers to its production Starshield
arc, not the separate deferred orbital experiment.

## Baseline and execution boundary

Inspected local `dev` at `f0a176b4d7dece11af4e3bd17db10f69b1bb5389`, with a
clean worktree before this document. Its parent is the design's code baseline
`bcf15704bd71b9abb7857b23ce9dfc2a06e58ad5`; the latest commit adds the approved
designs. At execution, refresh `dev`, inspect drift and use
`superpowers:using-git-worktrees` to create an isolated feature branch from
then-current `dev`. Do not create an orbital branch or implement that experiment.

Current measured network values feed the configured X-band line directly.
`activeLinkFlowEmitters` ignores metric availability and age and substitutes
100 ms when latency is absent. `FlowParticlePool.configure` does not remove
existing particles. `AnimatedFlowLine` has reduced-motion draw suppression but
no hidden-page/reset handling. Existing history and clock stores establish the
persistence, initialization and shutdown patterns to follow.

## Global constraints

- Settings: `starshield_link_enabled` and `x_band_link_enabled`; both default
  to `true`. They are shared installation settings, not local storage.
- Labels: `Starshield data link`, `X-band data link`. Descriptions:
  `Show aircraft-to-PoP traffic.` and
  `Show the configured satellite link and its activity.`
- No confirmed settings means both links hidden. Loading/read/save errors retain
  the last confirmed pair; saved `false` must survive default migration.
- Measured upload goes aircraft → PoP; download goes PoP → aircraft, using
  amber/cyan. Only fresh, available, finite, positive throughput emits.
- Status request failure or acquisition age at least ten seconds clears measured
  particles. Position freshness uses the original shared acquisition timestamp,
  independently of network availability; do not invent GPS provenance.
- X-band uses only synthetic `4 Mbps` in each direction and `500 ms` RTT, with
  no random bandwidth or loss. It emits only with valid fresh aircraft geometry,
  available configured selection and current `normal` state.
- Warning clears X-band particles immediately; its existing red line remains
  only if enabled. Unknown state or failed selection cannot emit.
- Synthetic values stay local to rendering; never enter telemetry, Prometheus,
  metric history/readouts, packet-loss statistics, alerts or link-state rules.
- Disabling hides the entire link and releases its resources. Preserve markers,
  labels, route/history, camera, metrics, collection and warning computation.
- Legend `Traffic path` and `Planned satellite link` follow actual draw guards.
  Add no globe caveats, warning banners or synthetic numerical metric cards.
- At most 100 particles per direction per link, reusable typed buffers, endpoint
  geometry updates only on endpoint changes. No per-particle React components.
- Hidden pages pause/clear particles; resume fresh after eligibility checks.
  Reduced motion preserves enabled lines without moving particles.
- Verify 1920×1080 with existing layers and unchanged pixel-ratio cap. No orbital
  dependencies, catalog, propagator, workers, controls or extension scaffolding.

## Review focus

1. A GET started before a save must not restore a disabled link; test cancellation
   and late completion in Task 2, including unmount before completion.
2. Concurrent viewers editing different switches must preserve both edits; test
   atomic partial merge under the store lock in Task 1.
3. Safe arc vertices can still produce chords inside Earth; test every segment's
   minimum radius, not just vertex radii, in Task 3.
4. A healthy status response with unavailable network metrics still permits
   X-band activity; failed requests and age exactly 10,000 ms do not. Test Task 4.
5. Old particles/emission remainders must not reappear after warning, loss of one
   direction, hidden-page return or reduced-motion changes; test Task 5.

## File responsibilities and order

Paths below are relative to the repository root. Tasks 1–2 own settings;
Task 3 owns geometry; Task 4 owns eligibility/appearance; Task 5 owns particle
lifecycle; Task 6 integrates those units; Task 7 verifies the shipped behavior.
New modules stay next to their existing counterparts. Avoid unrelated Overview
refactors or changes to the operational data pipeline.

## Task 1: Durable independent link settings

**Files:** Create `backend/starlink-location/app/services/overview_link_settings.py`,
`app/api/overview_link_settings.py`, `tests/unit/test_overview_link_settings.py`,
`tests/unit/test_main_overview_link_settings.py` and
`tests/integration/test_overview_link_settings_api.py` under that backend.
Modify `backend/starlink-location/main.py`. Reuse the already persisted settings
directory and its entrypoint permissions; no additional volume is required.

**Interfaces:** `OverviewLinkSettings` is a frozen dataclass with the two
boolean fields above, both defaulting to true.
`OverviewLinkSettingsStore(path: Path)` exposes `get() -> OverviewLinkSettings`
and `update(changes: dict[str, bool]) -> OverviewLinkSettings`.
`set_overview_link_settings_store(store: OverviewLinkSettingsStore | None)`
registers it. GET and PUT `/api/overview-links/settings` return the full pair;
PUT accepts either or both fields and atomically merges only supplied fields.

- [x] Write store tests for absent file → true/true, missing individual fields
  → defaults without overwriting false, all four combinations, recreation of the
  store and concurrent disjoint updates → both false. API tests assert strict
  booleans, unknown/empty/null/string/numeric updates → 422, and no initialized
  store → 503. Invalid persisted JSON/types and failed atomic replacement must
  produce an error without overwriting last-good disk contents.
  Name the concurrency case `test_disjoint_updates_preserve_both_switches`;
  its final assertions are:

  ```python
  assert store.get().starshield_link_enabled is False
  assert store.get().x_band_link_enabled is False
  ```

- [x] From `backend/starlink-location`, run

  ```sh
  uv run --with-requirements requirements-dev.txt pytest tests/unit/test_overview_link_settings.py tests/unit/test_main_overview_link_settings.py tests/integration/test_overview_link_settings_api.py -q
  ```

  expect missing-module/API failures before implementation.
- [x] Implement strict validation, FileLock-protected read/merge/write and
  temporary-file/`os.replace` persistence; ensure the parent directory exists
  before acquiring the file lock. Pydantic uses optional `StrictBool`
  fields, rejects extra keys and explicit null, and extracts only supplied
  fields. Persist at `data/settings/overview-links.json`. Initialize/register
  during startup and clear store/API references on shutdown like clock settings.
  Translate store read/write failures to 503, not a fabricated default pair.
- [x] Rerun the focused tests; require passing restart, lock/merge, failure and
  startup/shutdown assertions. Confirm both Compose deployments persist the
  settings directory through their existing data mounts and the app user can
  write it.
- [x] Commit this task with `feat: persist overview data link visibility`.

## Task 2: Confirmed settings query and Configuration controls

**Files:** Create `frontend/mission-planner/src/services/overview-link-settings.ts`
and `.test.ts`, hooks `useOverviewLinkSettings.ts` and
`useUpdateOverviewLinkSettings.ts` plus corresponding tests under `src/hooks/api/`,
and `src/pages/OverviewLinkSettingsCard.tsx` plus `.test.tsx`.
Modify `src/pages/ConfigurationPage.tsx` and `.test.tsx`.

**Interfaces:** Export `OverviewLinkSettings` matching Task 1 and
`OverviewLinkSettingsUpdate = Partial<OverviewLinkSettings>`.
`overviewLinkSettingsApi.get(): Promise<OverviewLinkSettings>` and
`.update(changes: OverviewLinkSettingsUpdate): Promise<OverviewLinkSettings>`
use Task 1's route. `useOverviewLinkSettings()` shares query key
`['overview-link-settings']`; `useUpdateOverviewLinkSettings()` accepts updates.
No-prop `OverviewLinkSettingsCard()` mounts independently of clock errors.

- [x] Write service/hook tests for valid pairs and rejected malformed responses;
  initial loading/error keeps `data` undefined, refresh errors retain confirmed
  data, and failed saves do not change the cache. Test a stale GET racing a
  successful save, another mounted consumer, late completion after unmount and
  refetch observing another viewer's change. Component tests assert exact labels
  and descriptions, accessible checked states, loading/pending disabled controls,
  visible saving/saved/error feedback and one-field payloads preserving the peer.
- [x] Run the focused tests from the frontend:

  ```sh
  npm run test:unit -- src/services/overview-link-settings.test.ts src/hooks/api/useOverviewLinkSettings.test.ts src/hooks/api/useUpdateOverviewLinkSettings.test.ts src/pages/OverviewLinkSettingsCard.test.tsx src/pages/ConfigurationPage.test.tsx
  ```

  Expect missing modules/new-card assertions to fail.
- [x] Implement response validation and confirmed-only query state: no placeholder
  true/true or optimistic updates; use `retry: false` like existing settings.
  Poll every 5,000 ms while visible and refetch
  on focus to synchronize viewers. Cancel in-flight settings reads before saving;
  on success synchronously cache the returned full pair and invalidate the query.
  Serialize mutations using scope ID `overview-link-settings`; disable both
  controls during a pending save. Cache updates create no scene resources.
- [x] Rerun the focused tests; require immediate shared-cache update, no late
  pre-save GET rollback, preserved saved false and clear recovery after errors.
- [x] Commit with `feat(configuration): add independent data link switches`.

## Task 3: Bounded globe-safe aircraft–PoP arc

**Files:** Create `frontend/mission-planner/src/pages/overview-traffic-arc.ts`
and `.test.ts`. Reuse `globe-coordinates.ts`, `globe-render-radii.ts`,
`status-projection.ts` and `x-band-active-link-projection.ts` without changing
their existing marker/history/X-band projection contracts.

**Interfaces:** `projectTrafficArc(aircraft: AircraftScenePosition | null,
pop: GlobeCoordinate | null): FlowPoint[]`. Start at `aircraft.position`; end at
`globePosition(pop.latitude, pop.longitude, ROUTE_OVERLAY_RADIUS)` as used for
the existing GEP surface overlay. Return `[]` for missing/invalid inputs,
nonfinite projections or aircraft projected below the scene Earth surface.

- [x] Write tests for exact endpoints/valid altitude, dateline and polar routes,
  long routes, antipodal/near-antipodal pairs, coincident ground coordinates and
  repeated identical inputs. Assert finite coordinates, deterministic orientation,
  at most 129 points, interior lift bounded by 0.6 scene units above interpolated
  endpoint radius, and every segment's analytic closest radius ≥ 2 within 1e-7.
  Include invalid ranges, NaN/infinity, missing altitude and below-surface inputs.
  Name the clearance case `keeps every antipodal segment outside Earth`;
  use the segment's closest point parameter, clamped to [0,1], to assert:

  ```ts
  expect(closestRadius).toBeGreaterThanOrEqual(2 - 1e-7);
  expect(arc.length).toBeLessThanOrEqual(129);
  expect(arc[0]).toEqual(aircraft.position);
  ```

- [x] Run `npm run test:unit -- src/pages/overview-traffic-arc.test.ts`;
  expect failure because the module does not exist.
- [x] Implement 128 segments along unit-sphere interpolation with radial envelope
  `lerp(startRadius, endRadius, t) + height * sin(Math.PI * t)`, where
  `height = clamp(0.6 * sin(angle / 2), 0.04, 0.6)`. For dot < -0.9995, split
  via a deterministic midpoint perpendicular to the start using its least-aligned
  Cartesian axis, then interpolate each half without an antipodal singularity.
  Near coincident directions normalize their linear blend; preserve exact end
  points. Coincident coordinates yield a shallow radial arch, not an unbounded
  loop. Validate segment clearance before returning; an unsafe result fails
  closed. Use this single geometry for both line and particle traversal.
- [x] Rerun the tests and existing coordinate/radius/projection tests; require
  analytic chord clearance for all valid adversarial fixtures, not omission of
  valid long or antipodal routes as a way to pass safety assertions.
- [x] Commit with `feat(overview): add globe-safe traffic arc geometry`.

## Continue with Tasks 4–7

[Tasks 4–7: activity, lifecycle, integration and acceptance](2026-10-03-starshield-flow-line-arc-tasks-4-7.md)
completes this same plan.
Read both files and the approved spec before execution.

## Handoff

Recommended execution is native: these seven tasks share settings and renderer
interfaces, and their focused tests provide useful gates without per-task agent
context overhead. The user should review this plan and select native or delegated
execution before product implementation begins. No product code, dependency
installation, runtime project or feature branch is created by planning.

## Execution status — 2026-10-03

Task 1 is implemented: durable independent backend settings, strict partial
GET/PUT contract, locked atomic merge and application startup/shutdown wiring.
Verification: 56 focused tests passed; full backend suite 1,350 passed and
20 skipped; canonical Ruff and Black passed. Existing settings data mounts
cover both deployments. An isolated cached-backend container running as
appuser saved both switches disabled and a fresh container retained them.
This checks the current store and existing entrypoint, not a full candidate
image deployment; final exact-candidate acceptance remains Task 7.

Task 2 is implemented: validated confirmed-only settings query, serialized
partial saves, cancellation before PUT and before publishing its full response,
and independent accessible Configuration switches with save feedback. Reads
poll every five seconds while visible and refresh on focus. Deferred-response
tests cover stale GET completion after saves/unmount, reads during PUT, shared
consumers, queued saves, errors and another viewer's changes. Verification:
43 focused tests and 447 frontend unit tests passed; ESLint, full source Prettier
check and production build passed. Existing dialog/Three.js test warnings and
large-bundle build warning remain. No scene integration was added in this task.

Task 3 is implemented: a 128-segment aircraft–PoP arc with exact projected
endpoints, bounded sinusoidal lift, deterministic perpendicular antipodal
midpoint and analytic clearance validation for every chord. Invalid or
below-surface inputs fail closed. Existing projections remain unchanged.
Verification: 48 new arc tests, 78 focused geometry/projection tests and all
495 frontend unit tests passed; ESLint, full source Prettier, filename checks
and production build passed. Existing test/build warnings remain.

Task 4 is implemented: independent visibility/activity policies use original
status acquisition age, request errors, valid aircraft projection and explicit
metric availability. Missing latency/loss omits modulation; measured directions
retain logarithmic activity, fixed speed and particle caps. X-band uses only the
steady 4/4 Mbps, 500 ms preset with a 1.35 brightness floor and no loss. Cached
X-band line geometry is retained while ineligible activity stops. Verification:
115 focused flow/state/freshness/readout tests and all 562 frontend unit tests
passed; ESLint, full source Prettier and production build passed. Existing
test/build warnings remain. Overview's helper import/call was mechanically
renamed to keep compilation working; scene integration remains Task 6.

Task 5 is implemented: stopped directions clear particles/counts/remainders,
endpoint changes start fresh, and visibility/reduced-motion/operational pauses
clear draw ranges and release particle resources. Wall-clock eligibility is
checked before frames and hidden return; resumed delta is discarded and active
delta capped at 0.1 seconds. Layout effects allocate fresh GPU resources
for particles, short lines and ribbons on each StrictMode setup. Verification:
39 focused lifecycle/renderer tests, 78 ribbon/route/history compatibility tests
and all 587 frontend unit tests passed; ESLint, full source Prettier and
production build passed. Existing test/build warnings remain.

Task 6 is implemented; see [execution status](2026-10-03-starshield-flow-line-arc-tasks-4-7.md#task-6-execution-status).
Task 7 execution and gaps are recorded in the split plan. Stop after Task 7.
Use Superpowers; preserve a12a61b5, abb650ab and concurrent ADS-B documents.
