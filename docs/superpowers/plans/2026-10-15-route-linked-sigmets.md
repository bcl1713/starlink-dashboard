# Route-linked SIGMETs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display route-intersecting SIGMETs and automatic passive notices on
Overview, controlled and acknowledged from Configuration on another screen.

**Architecture:** A route adapter and owned geometry worker join admitted
SIGMETs to an atomic acknowledgement store. One shared browser source supplies
reports to Configuration and filtered native drawings to Overview.

**Tech Stack:** Existing Python 3.11/FastAPI/Pydantic/filelock/Shapely 2,
TypeScript/React/TanStack Query/Zod/Three.js, pytest/Vitest/Playwright and
Docker. No new provider or product dependency.

**Spec:** [Approved design](../specs/2026-10-15-route-linked-sigmets-design.md).
**Status:** Approved 2026-10-15; Tasks 1–8 implemented;
[production acceptance and evidence](../../reports/2026-10-15-route-linked-sigmets.md)
passed. Review and PR pending. **Companion:**
[Technical contracts](2026-10-15-route-linked-sigmets-contracts.md) defines
shared types, the geometry algorithm, ownership and acceptance commands. Read
both documents; this is one implementation plan with eight sequential tasks.

## Global Constraints

- Inspected production base: `1c0834a1e45685a4dd3592de252db2bea9e08a0d`. Spec
  commit: `ea4f55898d2f8caf0f236a845f53447c9235fb63`. Fetch `origin/dev`; create
  `.worktrees/route-linked-sigmets` on `feat/route-linked-sigmets`. Record the
  actual base and review intervening changes. Carry docs if PR 336 is open. PR
  targets `dev`; keep the primary checkout on `dev` and preserve open-PR
  worktrees.
- `sigmet_intersecting_only: false`; preserve SIGMET's default-off setting.
  Configuration owns Clear/Show again and full SIGMET inspection. Overview has
  at most three passive cards, steady linked highlights and overflow count.
- Match the entire selected route, including current running/completed replay
  geometry. Weather uses actual UTC and `[valid_from, valid_to)`. Altitude and
  passage-time matching are not evaluated; no corridor, rerouting or risk score.
- Store limits: eight route contexts, 4,000 records, 2 MiB serialized; prune at
  bulletin expiry. No eviction of live current-context acknowledgements.
- Worker caps: 20,000 route points, 100,000 combined polygon vertices, 500
  advisories, 100,000 spans, 8 MiB output; five-second wall limit with
  one-second termination grace. Incomplete/unknown never becomes a successful
  zero match.
- Browser limits: 16 MiB encoded, 32 MiB decoded/geometry, 16 MiB GPU, four
  operations, including old-plus-candidate peaks. Five-second visible/online
  polling; controlled cross-browser propagation within eight seconds of save.
- Preserve original freshness/expiry, raw bulletins, revision/cancellation
  semantics, unknown/partial coverage, METAR/TAF, radar and GFS. An empty result
  is not a clear-route claim. Stop and reap owned resources after every check.

## Review Focus

1. Equal notice revisions can accompany different feed generations; Task 5
   rejects a late older response even when its acknowledgement counter ties.
2. Clearing may race a route edit, amendment or cancellation; Task 4 proves an
   old identity cannot acknowledge a replacement or another route.
3. Ring orientation/start order, negative zero and feed ordering may change
   without a new bulletin; Tasks 1/3 pin cross-language stable identities.
4. A SIGMET endpoint can refresh faster than the existing 60-second catalog
   loop; Tasks 5/7 bind exact immutable reports immediately without displaying
   an unfiltered frame or adding another upstream poller.
5. Unfocused visible windows and Configuration-only demand still need updates;
   Tasks 5/8 verify visibility lifecycle, source sharing and bounded cleanup.

## File Map and Commands

Path aliases: `B = backend/starlink-location`, `F = frontend/mission-planner`,
`W = B/app/services/aviation_weather`, `A = F/src/pages/aviation-weather`.
Backend tests use `B/tests/unit/test_route_sigmets_<area>.py`; frontend tests
are colocated `.test.ts(x)`. Use the companion's bounded commands with each
task's selections. Require behavioral FAIL before code and PASS before commit.
Keep new modules focused and below 300 lines. Execution follows plan approval.

## Task 1: Contracts and Authoritative Route Selection

**Files:** Create `B/app/models/route_sigmets.py`, `W/route_context.py`,
`F/src/services/route-sigmet-context.ts`; modify `W/settings.py`,
`F/src/services/aviation-weather.ts`, `F/src/pages/OverviewPage.tsx`.
**Interfaces:** Produce `RouteContext`, `RouteSigmetSnapshot`, `NoticeMutation`,
`select_route_context(route_manager, simulation_service) -> RouteContext | None`
and `routeContextKey(source, routeId, runtimeId, runId, points): string`.

- [ ] Write areas `contracts`, `context`, and the TS context/service tests:
      assert legacy filter is false, null/extra/oversized input is rejected,
      `key(+0) == key(-0)`, rename/ticking leave the key unchanged, reversed
      coordinates/new runs change it, and Python/TS match pinned digests. Test
      running/completed/cancelled replay, no route and concurrent route edit.
- [ ] Run those backend areas and TS context tests; require the new assertions
      to fail. Add fixture-only route metadata, not live provider requests.
- [ ] Add strict models and the filter field/update support. Deep-copy the
      selected route under `get_active_leg_lock()`, use current selected replay
      artifacts only for matching runtime/run status, and hash outside the lock.
      Expose a local context key in Overview without changing its route choice.
- [ ] Re-run green, plus existing `test_aviation_weather_models.py`,
      `test_gfs_settings.py`, `active-globe-route.test.ts` and service tests.
- [ ] Commit `feat: define route SIGMET contracts and route identity`.

## Task 2: Bounded Great-circle Intersection Worker

**Files:** Create `W/route_arcs.py`, `route_geometry.py`, `route_worker.py`,
`route_decode.py`; tests areas `arcs`, `geometry`, `decode` plus
`B/tests/fixtures/route-sigmets/geometry.json`. **Interfaces:** Consume
`RouteContext` and normalized SIGMET features; produce
`intersect_route(points, features) -> GeometryResult` and
`evaluate_in_worker(context: RouteContext, collection: dict) -> GeometryResult`
(async). GeometryResult/spans and the analytic interval method are in companion.

- [ ] Add analytic reference fixtures for equatorial crossing at fractions
      0.25/0.75, both endpoints outside a thin polygon, containment, a hole,
      disjoint spans, endpoint touch, ±180 seam, high latitude, duplicate points
      and antipodal ambiguity. Assert independent reference error <=18.52 m;
      unresolved near-boundary cases must never assert disjoint.
- [ ] Add actual subprocess controls: hung worker, excessive stdout, repeated
      cancellation, supersession and max input/output. Assert one worker at a
      time, bounded queue, <=six-second timeout/termination envelope, reaped PID
      and no leftover pipes. Run all three areas red.
- [ ] Implement the companion's conservative interval classifier with existing
      Shapely, bounded streaming I/O and disposable subprocess ownership. Keep
      all geometry work outside the event loop; never truncate to fit a budget.
- [ ] Run green and `test_aviation_weather_decode.py`; verify PID/pipe cleanup.
- [ ] Commit `feat: evaluate route SIGMET intersections in a bounded worker`.

## Task 3: Stable Bulletin Identity and Atomic Acknowledgements

**Files:** Create `W/route_identity.py`, `route_state.py`; test areas
`identity`, `state`. Reuse `W/relations.py` cancellation semantics without
changing them. **Interfaces:**
`group_bulletins(features) -> list[BulletinGroup]` and
`NoticeStore.reconcile(context_key, eligible, now_ms) -> NoticeState`;
`NoticeStore.set_ack(change: NoticeMutation, now_ms: int) -> NoticeConfirmation`.

- [ ] Add exact assertions: a refresh keeps the key/attention order, equivalent
      ring/text/order changes do not re-alert, a semantic amendment does, series
      reuse has a different identity, and geometry variants retain all feature
      IDs in one group. Run `identity` red.
- [ ] Add real tmp-file/multiprocess store tests: repeated Clear is idempotent;
      Show again advances order once; reopening a store preserves state; expiry
      pruning and inactive LRU obey 8/4,000/2 MiB caps; corrupt files are
      unchanged; disk/lock failure reports failure; current live
      acknowledgements survive capacity pressure. Run `state` red.
- [ ] Implement deterministic grouping/digests and locked tempfile/fsync/replace
      persistence with separate `state_revision` and `attention_counter`. Lock
      operations use a one-second acquisition timeout and run off the event
      loop.
- [ ] Run both areas green; assert failed writes leave bytes/revision unchanged
      and SIGMET settings/GFS demand are untouched.
- [ ] Commit `feat: persist route-specific SIGMET acknowledgements`.

## Task 4: Shared Service, API and Application Lifecycle

**Files:** Create `W/route_runtime.py`, `B/app/api/route_sigmets.py`; modify
`W/runtime.py`, `B/main.py`; tests areas `runtime`, `api` and existing
`test_main_aviation_weather.py`. **Interfaces:**
`RouteSigmetService.read() -> RouteSigmetSnapshot`,
`acknowledge(change: NoticeMutation) -> NoticeConfirmation`, `aclose()` (async);
add `AviationWeatherService.read_layer(layer)` as a shared-lease read returning
the current admitted product/collection without acquiring unrelated layers.

- [ ] Write red tests for each spec lifecycle row, initial existing matches,
      validity start/end without source refresh, stale originals, unknown
      geometry/lineage, duplicate readers and Configuration-only demand.
      Concurrent read/clear/amend/cancel/route-edit tests assert old writes
      return 409 and cannot affect the new route/revision; off performs no fetch
      and no-route starts no matching worker while all-mode SIGMETs remain
      available.
- [ ] Add read-only source access via existing `_acquire`/admission ownership;
      never expose private maps or create a second fetch scheduler. Cache worker
      results by context/content; join eligibility and notice state on each
      read. Hold no route/notice lock during network, worker or geometry
      operations.
- [ ] Wire the exact GET/PUT paths from the companion, `no-store`, validation,
      bounded deadlines and sanitized errors. Revalidate route/feed/eligibility
      before publishing or mutating. Initialize lazily alongside existing
      weather services; use the settings-volume sibling
      `route-sigmet-notices.json` and close matching work before closing the
      bulletin service on shutdown.
- [ ] Run areas `runtime`, `api` and startup tests green. Assert source-service
      failure is isolated, repeated cancellation is reaped, `/health` and
      `/api/status` stay healthy, and clears never change source cadence.
- [ ] Commit `feat: expose synchronized route SIGMET notices`.

## Task 5: Shared Browser Source and Confirmed Mutations

**Files:** Create `F/src/services/route-sigmets.ts`,
`F/src/hooks/api/useRouteSigmets.ts`, `A/route-sigmet-source.ts` and their
tests; modify `F/src/hooks/useAviationWeather.ts`, `A/aviation-controller.ts`.
**Interfaces:** Produce `useRouteSigmets()`, `useSetSigmetAcknowledgement()`,
`RouteSigmetSource.subscribe/snapshot/dispose`; add
`AviationController.setExternalSigmet(view: AviationLayerView)` and an explicit
external-SIGMET constructor option. Exact source/ownership types are in
companion.

- [ ] Write red tests for strict wire parsing, generation mismatch, 404
      immutable payload races, mutation failure/409 recovery and
      same-state-revision late responses. Assert a confirmed Clear cannot be
      undone by an earlier GET. Fake visibility/focus/online transitions; two
      consumers create one poller.
- [ ] Implement the query-client-scoped source, five-second query, local expiry
      boundary timer, monotonic UTC anchor, bounded report fetch and
      reservations. A new product fetches immediately; it must not wait for the
      old 60-second controller poll. Share parsed SIGMET data without
      constructing Configuration GPU objects. Cancel pending reads before
      mutations; commit only confirmed changes, reject obsolete epochs and
      refetch on 409.
- [ ] In external mode, the existing controller neither fetches nor draws its
      own SIGMET layer; consume the externally owned view at publish. Preserve
      its original METAR/TAF paths and old independent unit fixtures.
- [ ] Run new tests green plus aviation-controller, weather-budget and service
      regressions; assert no retained work with zero subscribers or SIGMET off.
- [ ] Commit `feat: synchronize route SIGMET reports across browser views`.

## Task 6: Configuration Controls and Bulletin Review

**Files:** Create `A/RouteSigmetSettings.tsx` and its test; modify
`A/AviationSettingsCard.tsx`, `A/AviationReport.tsx`, `A/AviationWeather.css`.
**Interfaces:** Consume Task 5 hooks and reuse `AviationReport` for original
bulletins. Produce a hazards subpanel with filter and per-notice actions.

- [ ] Add red tests: filter disabled while SIGMET off but remembered; confirmed
      saves only; route-order list; unknown/future reports; Clear/Show again
      actions named per bulletin; UTC/source/bounds/raw text present; failed
      writes and stale-identity refresh leave truthful feedback.
- [ ] Implement the panel inside Hazards, with expandable full reports and
      separate unknown-location/future sections, pending/acknowledged state,
      route name/source, coverage limitations and keyboard-accessible controls.
      Never mount native drawings or change a notice from an unsaved draft.
- [ ] Run panel/settings/report tests green, including non-SIGMET regressions.
- [ ] Commit `feat: control route SIGMET advisories from Configuration`.

## Task 7: Passive Cards, Filtering and Native Highlights

**Files:** Create `A/RouteSigmetNotices.tsx`, `route-sigmet-presentation.ts`,
`route-sigmet-highlights.ts` and tests; modify `A/AviationLayer.tsx`,
`A/AviationStatus.tsx`, `A/aviation-inspection.ts`, `A/AviationWeather.css`,
`F/src/pages/OverviewPage.tsx` and affected existing inspection tests.
**Interfaces:** `createSigmetPresentation(input, budget) -> SigmetPresentation`
owns base and at most three highlight drawings; `dispose()` releases them.
Consume the exact route key, source view, confirmed filter and pending notices.

- [ ] Write red tests: three newest-attention cards plus accurate overflow; Show
      again promotes a card; cleared polygon keeps normal shading; no
      route/wrong generation/loading evaluation shows no intersecting-only
      geometry. Test expiry, budget rejection, uncertain spans and no-route
      text. Assert no SIGMET picker/chooser/dismissal action remains on
      Overview.
- [ ] Implement steady depth-tested polygon outlines and great-circle span
      overlays, with matching bulletin labels and no camera/focus/animation side
      effects. Suppress unknown spans, use one-based segment labels when named
      waypoint occurrence mapping is absent, and state the exact unevaluated
      altitude/time copy.
- [ ] Bind/dispose through the existing native-layer owner. Account for source,
      results, geometry and old/candidate peaks; failure leaves textual notices
      with explicit highlight-unavailable state, not a vanished advisory.
- [ ] Run new tests and inspection/layer/status regressions green. Confirm
      METAR/TAF picking and core route/camera/legend behavior remain intact.
- [ ] Commit `feat: display passive route SIGMET notices and highlights`.

## Task 8: Production Acceptance and Operator Evidence

**Files:** Extend `tools/acceptance/aviation-weather/run.sh`, `compose.yml`,
`backend_fixture.py`, `generate_fixtures.py`; create
`F/tests/e2e/route-sigmets-production.spec.ts`,
`F/tests/e2e/support/route-sigmets-probe.ts`,
`tools/tests/test_route_sigmets_acceptance.py`; modify
`F/playwright.aviation-acceptance.config.ts`, existing aviation production
tests, `docs/api/aviation-weather.md`, `docs/features/overview-weather.md`;
create `docs/reports/2026-10-15-route-linked-sigmets.md` during execution.

- [x] Add failing runner controls proving unique project/ports, exact candidate
      archive/test provenance, cleanup after failed build/test/forced timeout,
      and refusal to claim PASS without browser assertions and verified
      teardown. Implement companion acceptance changes and run those controls
      green.
- [x] Add production-path tests using separate browser contexts for
      Configuration and Overview; assert saves/clears/Show again converge within
      eight seconds, current notices appear initially, and
      new/amended/cancelled/reused-series fixtures obey identity/expiry. Include
      matching route, simulation, incomplete evaluation, stale/empty/unlocated
      source and reversed-response controls.
- [x] Capture native polygon/span evidence and desktop 1920×1080, fullscreen,
      mobile 390×844 views with three cards plus overflow. Verify no
      focus/camera change, no Overview SIGMET controls, readable core overlays
      and keyboard Configuration access. Record source-request counts,
      memory/slot peaks and repeated hide/offline/unmount disposal with existing
      weather layers enabled.
- [x] Run companion final gates and exact-SHA production acceptance. Preserve
      synthetic labels; pin a real normalized SIGMET capture and hashes for a
      separate source-shaped replay control. Missing real-source evidence stays
      unverified and prevents a complete acceptance claim. Document existing GFS
      source/hardware gaps separately; do not claim to close them.
- [ ] Update operator/API docs and evidence report; commit
      `test: verify passive route SIGMET workflow and lifecycle`. Rerun
      acceptance against the final committed SHA if any test, app or runtime
      input changed; push a PR to `dev` with evidence. Stop resources
      immediately after checks; retain the worktree while the PR is open and
      clean task files after merge.
