# SIGMET Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Make Overview quiet unless a SIGMET needs attention, with compact
relevant-only Configuration and shared manual selection from the globe.

**Architecture:** Extend the existing route notice service with persistent
manual selection, keeping computed intersections distinct. Both screens consume
one server-owned attention projection. Extend the existing aviation picker for
SIGMET polygons; retain the production renderer and ownership budgets.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, filelock, React 19, TypeScript,
Three.js, TanStack Query, pytest, Vitest, Playwright, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-15-sigmet-attention-design.md`
(approved).

## Global Constraints

- With an empty attention set, render no SIGMET status box, count, placeholder,
  detail cards, or reserved panel space.
- The status box contains only `SIGMETS: N`.
- Preserve a maximum of three expanded attention cards in the desktop rail.
- Label a nonintersecting selection `Selected`, never `Intersecting`.
- Unknown intersection results do not create automatic notices.
- Manual selection requires a current route context and a current, eligible
  report.
- The backend remains authoritative; component state and browser storage do not
  own selections.
- Respect reduced-motion preferences with a steady bright border.
- Preserve bounded state, atomic updates, no-store responses, identity checks,
  cancellation, shared data ownership, GPU budgets, and disposal.
- Use `.worktrees/` and a feature branch based on `origin/dev`; keep the primary
  checkout on `dev`. This plan currently builds on the route-linked SIGMET
  candidate `1319b56d` and design commit `881cbcf7`. Inspect upstream
  integration before rebasing; preserve the prerequisite feature and never
  duplicate its changes in a follow-up PR after it merges.
- Keep the requested `starlink-sigmet-lan-review` instance running. Use separate
  task-owned resources for checks and the revised review build.
- Record runtime ownership before starting resources. Apply wall-clock limits
  and cleanup handlers; verify teardown after every check. Do not publish a
  revised review URL until browser checks pass.

## Review Focus

- A report selected on one display while another acknowledges it: confirmation
  order must not resurrect an older state (Tasks 1–3, 6).
- A bulletin has multiple polygons and is both selected and intersecting: one
  count, one card, one acknowledgement (Tasks 2–3).
- Overlapping/dateline polygons, holes, or polygons behind the globe: picking
  must agree with visible geometry (Task 4).
- A route, simulation run, or feed changes while a selection request is in
  flight: reject stale writes and leave the replacement context untouched (Tasks
  2–3, 6).
- The current card expires, is cancelled, or is acknowledged on another display
  while paginated: clamp navigation and preserve access to every remaining
  pending card (Tasks 3, 5–6).

## File and command conventions

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`. New modules are scoped to SIGMET
attention rather than expanding `OverviewPage.tsx` with picking or persistence
logic.

Run backend selections from the backend directory with:

```bash
timeout --kill-after=10s 10m uv run --python 3.11 --with-requirements requirements.txt pytest tests/unit/test_route_sigmets_state.py -q
```

Replace the final test paths with the owning task's files. Frontend selections
run from its directory with
`timeout --kill-after=10s 10m npm run test:unit -- <test paths>`. Provision
dependencies using the tracked lockfiles before execution; verify any reused
installation has the same lockfile. Every task follows failing regression,
minimal implementation, passing regression, then commit. A failure must
demonstrate the missing behavior rather than a broken test harness.

### Task 1: Persist manual selection without losing existing acknowledgements

**Files:**

- Modify backend `app/models/route_sigmets.py` and
  `app/services/aviation_weather/route_state.py`.
- Test backend `tests/unit/test_route_sigmets_contracts.py` and
  `tests/unit/test_route_sigmets_state.py`.

**Interfaces:**

- Add
  `NoticeSelection(context_key: Hash, bulletin_key: Hash, semantic_digest: Hash)`.
- Add `selected: bool = False` to `NoticeRecord` and `RouteSigmetEntry`.
- Add `SelectedSigmetEntry`, containing the same identity, validity, feature
  IDs, attention order and acknowledgement fields as a route entry, but no
  `spans`; it represents selected-only reports.
- Add `selected_entries: list[SelectedSigmetEntry] = []` to
  `RouteSigmetSnapshot`. Keep `entries` exclusively computed intersections and
  preserve its nonempty-span invariant. Enforce combined response size, notice
  uniqueness, and advisory limits across both lists.
- Add
  `NoticeStore.select_sync(change: NoticeSelection, group: BulletinGroup, now_ms: int, *, validate: Validator | None = None) -> NoticeState`.
- Extend `reconcile_sync` with keyword-only
  `selection_eligible: list[BulletinGroup] | None = None`; existing `eligible`
  remains the computed matches. This input lets the store reconcile only
  previously selected lineages against the full eligible feed without
  registering the entire feed.

- [ ] **Step 1:** Add regressions named
      `test_v1_migration_preserves_ack_and_revision`,
      `test_selection_is_idempotent_and_survives_restart`,
      `test_ack_ends_manual_selection`,
      `test_selected_lineage_amendment_starts_pending`, and
      `test_concurrent_select_ack_has_atomic_revision_order`. Assert existing
      acknowledgement/order values survive migration, repeated selection of an
      already pending entry does not increase order, selecting a cleared entry
      reopens it once, acknowledgement sets `selected=False`, and amendments
      follow only still-selected known bulletin lineage.
- [ ] **Step 2:** Run both owning backend test files; record expected failures
      for missing contracts/behavior.
- [ ] **Step 3:** Implement the interfaces. Write schema
      `route-sigmet-state-v2`; explicitly migrate valid v1 records to
      `selected=False` under the existing lock and atomic write path. Preserve
      counters and acknowledgement values. Reject unknown/corrupt schemas
      without rewriting. Retain existing LRU/record/byte limits. Reconciliation
      removes cancelled/expired selections from eligibility; unseen or ambiguous
      lineage must not transfer a selection to an unrelated bulletin.
- [ ] **Step 4:** Run the same tests plus capacity, disk-failure, lock-timeout
      and two-process regressions. Add assertions that selected-only entries
      cannot manufacture spans and union limits cannot be bypassed with two
      separate lists. Expect all selected tests to pass.
- [ ] **Step 5:** Commit as
      `feat: persist route scoped manual SIGMET selections`.

### Task 2: Expose authoritative selection and acknowledgement through the existing service

**Files:**

- Modify backend `app/services/aviation_weather/route_runtime.py` and
  `app/api/route_sigmets.py`.
- Test backend `tests/unit/test_route_sigmets_runtime.py` and
  `tests/unit/test_route_sigmets_api.py`.
- Update `docs/api/aviation-weather.md` for the added endpoint and response
  fields.

**Interfaces:**

- Add
  `RouteSigmetService.select(change: NoticeSelection) -> RouteSigmetSnapshot`
  and `PUT /api/aviation-weather/v1/route-sigmets/selection` returning that
  snapshot.
- Reuse Task 1's model/store interfaces. `acknowledge` accepts either a current
  intersection or a current selected-only notice using the existing
  `NoticeMutation` contract and confirmation shape.
- `read()` returns route intersections in `entries` and unacknowledged
  selected-only bulletins in `selected_entries`; a bulletin present in `entries`
  has its `selected` flag set rather than being repeated.

- [ ] **Step 1:** Add runtime/API regressions for selecting an eligible
      nonintersection, selecting a matched bulletin without duplication,
      selecting an already cleared notice, acknowledgement removing a
      selected-only notice, no-route rejection, stale semantic/context
      rejection, and no-store headers on every endpoint result. Assert `409` for
      obsolete/no-context selections and unchanged replacement-context state.
- [ ] **Step 2:** Run the owning runtime/API tests and confirm failures describe
      the missing behavior.
- [ ] **Step 3:** Implement selection through the existing active-leg gate, feed
      eligibility, `_operation` validation and thread-owned store I/O. Inspect
      the full admitted feed for selection eligibility, independently of
      geometry matches. Recheck the exact context/report after awaits. Reuse one
      identity per bulletin and never synthesize a span. Return a fresh snapshot
      after successful selection. Keep unknown diagnostic results separate from
      automatic attention.
- [ ] **Step 4:** Verify the task tests plus ordinary/simulation route switches,
      route/feed mutation during I/O, expiration, cancellation, amended lineage,
      feature permutation, multiple polygons, and response budget bounds. Verify
      an acknowledged selected-only report does not return after a feed refresh
      or amendment.
- [ ] **Step 5:** Commit as
      `feat: expose shared SIGMET selection and acknowledgement`.

### Task 3: Build a single client attention model and selection mutation

**Files:**

- Modify frontend `src/services/route-sigmets.ts`,
  `src/hooks/api/useRouteSigmets.ts`,
  `src/pages/aviation-weather/route-sigmet-source.ts`,
  `route-sigmet-presentation.ts`, and `route-sigmet-highlights.ts` in that same
  directory.
- Create frontend `src/pages/aviation-weather/sigmet-attention.ts` and
  `sigmet-attention.test.ts`.
- Extend frontend service, hook, source, presentation and highlight tests
  alongside those modules; update `src/test/route-sigmet-fixtures.ts`.

**Interfaces:**

- Parse Task 1's additive wire fields; older snapshots without
  `selected_entries` or `selected` default to `[]` and `false`.
- Add
  `setSigmetSelection(change: NoticeSelection, signal: AbortSignal, budget: WeatherBudget, fetcher: typeof fetch): Promise<RouteSigmetSnapshot>`
  alongside the existing request functions, with their timeout/size/error rules.
- Add
  `RouteSigmetSource.setSelection(change: NoticeSelection): Promise<RouteSigmetSnapshot>`
  and `useSelectSigmet()` returning the corresponding TanStack mutation.
- Export `SigmetAttentionItem` as a discriminated union with
  `kind: 'intersecting' | 'selected'`, the appropriate wire entry, resolved
  reports, label and color.
- Export
  `sigmetAttentionItems(snapshot: RouteSigmetSnapshot | null, reports: readonly AviationAdvisory[], nowMs: number): SigmetAttentionItem[]`.
  Return only current unacknowledged items, ordered by descending attention
  order then notice key. Deduplicate bulletin identities across both lists.
  Carry a selected-and-intersecting bulletin as `intersecting`.
- Export `sigmetNoticeColor(bulletinKey: string): string`; hash the bulletin key
  into the existing palette `['#7dd3fc', '#f0abfc', '#fde68a']`, independent of
  list position. The same identity retains its color in card and map
  presentation.

- [ ] **Step 1:** Add unit regressions asserting an unknown-only snapshot yields
      `[]`, selected plus matched counts once, selected-only has no spans,
      reordered data keeps colors, and expired/cancelled/incompatible-context
      entries cannot enter attention. Add deferred-request source tests where
      selection/ack confirmations arrive around polling, route changes, unmount
      and disposal; assert an older revision never resurrects state.
- [ ] **Step 2:** Run the attention, source, service and presentation tests;
      confirm the expected failures.
- [ ] **Step 3:** Implement parsing, mutation and the pure attention projection.
      Route all writes through the existing source ownership/cancellation rules.
      Accept only matching context and monotonic state revisions; refresh on
      `409`. Selection responses update the shared snapshot after confirmation.
      Make selected-only acknowledgement disappear immediately after confirmed
      success while preserving matched entries as cleared. Expose all pending
      items from the presentation; the component, not the data source, owns the
      three-card page.
- [ ] **Step 4:** Preserve optional map polygon filtering independently of the
      attention filter. Build route-span highlights only for intersection items;
      selected-only items get polygon emphasis without route highlights. Reuse
      admitted source data, rendering budgets and disposal. Run attention,
      source, service, hook, presentation and highlight tests; expect all to
      pass.
- [ ] **Step 5:** Commit as `feat: share a concise SIGMET attention model`.

### Task 4: Select SIGMETs through the visible map

**Files:**

- Create frontend `src/pages/aviation-weather/sigmet-picking.ts` and
  `sigmet-picking.test.ts`.
- Modify frontend `aviation-inspection.ts`, `AviationLayer.tsx`,
  `AviationDetails.tsx` and their tests in that directory.
- Modify frontend `src/pages/OverviewPage.tsx` and
  `OverviewPage.layers.test.tsx`.

**Interfaces:**

- Export
  `pickSigmetFeatures(view: AviationView, camera: THREE.Camera, point: { x: number; y: number }, viewport: { width: number; height: number }): AviationSelection[]`
  from the new picking module.
- Extend existing `pickAviationFeatures`, `inspectionReports` and
  `resolveAviationSelection` to support visible SIGMETs. Preserve existing
  `AviationSelection = { layer: AviationLayer; id: string }` and the
  `AviationLayer.onSelect(candidates)` signature.
- Add
  `visibleSigmetReports(view: AviationView, camera: THREE.Camera, viewport: { width: number; height: number }): AviationSelection[]`
  for the keyboard chooser. Reuse the map's admitted and filtered geometry
  rather than exposing every report in the feed.

- [ ] **Step 1:** Replace tests that explicitly prohibit SIGMET picking with
      regressions for visible interiors and boundaries, holes, multipolygons,
      dateline crossing, overlap candidates, viewport edges, near-horizon
      visibility and far-side exclusion. Keep station and click-versus-drag
      tests. Add a keyboard test selecting a visible SIGMET and assert reports
      outside the rendered map are absent from the chooser.
- [ ] **Step 2:** Run picking, inspection, layer and details tests; confirm
      expected failures without breaking fixture/camera setup.
- [ ] **Step 3:** Implement picking with the existing ray/camera and spherical
      geometry conventions; treat the hit as a point on the visible globe,
      account for holes and dateline wrapping, and return all visible
      overlapping candidates in stable identifier order. Do not add map
      listeners that bypass the existing drag threshold or leak on unmount.
- [ ] **Step 4:** Integrate Task 3's selection mutation when a user chooses one
      SIGMET; overlapping hits first open a compact chooser, with no selection
      write until the user chooses. Focus the resulting card after confirmed
      success. Clicking an existing pending bulletin focuses it without
      repeating a write; clicking a cleared one reopens it. Without a route show
      inspectable report details and a local explanation instead of persisting
      selection. Distinguish loading/save errors from a confirmed selection.
- [ ] **Step 5:** Run the owning frontend tests, including existing METAR/TAF
      picking, keyboard navigation, globe gesture behavior and renderer disposal
      regressions. Commit as `feat: inspect and select SIGMETs on the globe`.

### Task 5: Deliver the quiet Overview and compact relevant-only Configuration

**Files:**

- Modify frontend `src/pages/aviation-weather/RouteSigmetNotices.tsx`,
  `RouteSigmetSettings.tsx`, `AviationSettingsCard.tsx`, `AviationWeather.css`
  and their adjacent tests.
- Modify frontend `src/pages/OverviewPage.tsx` and its layer tests.
- Add frontend `src/pages/aviation-weather/SigmetAttentionCard.tsx` and
  `SigmetAttentionCard.test.tsx` for the shared concise card and confirmed
  acknowledgement behavior.

**Interfaces:**

- `SigmetAttentionCard({ item, onAcknowledged }: { item: SigmetAttentionItem; onAcknowledged?: () => void })`
  uses the existing acknowledgement hook and renders identifier,
  hazard/severity, segment or `Selected`, a collapsed full report, and
  Acknowledge.
- `RouteSigmetNotices({ presentation, focusedNoticeKey }: { presentation: SigmetPresentation; focusedNoticeKey?: string | null })`
  uses the full attention list from Task 3, renders nothing at zero, and pages
  at most three cards. Clamp the page when entries disappear and navigate to an
  explicitly selected key.
- Configuration consumes the same union as Task 3, but includes cleared
  intersections in a collapsed Cleared section. Selected-only acknowledgements
  leave the list entirely. Keep a collapsed Diagnostics section outside the main
  list.

- [ ] **Step 1:** Add tests asserting zero attention produces no region or
      reserved wrapper; four pending bulletins render `SIGMETS: 4` and at most
      three cards; navigation reaches the fourth; acknowledgement on page two
      clamps correctly; removed disclaimer/route/status prose is absent. Assert
      the status border uses the first pending card's stable color and
      reduced-motion CSS disables animation.
- [ ] **Step 2:** Add Configuration tests with hundreds of unrelated reports:
      only matched and selected rows appear, full reports and Cleared start
      collapsed, selected-only acknowledgement removes its row, route
      acknowledgement moves to Cleared, Show again restores attention, and
      failures retain confirmed state. Assert map-only filtering cannot change
      the relevance list or count.
- [ ] **Step 3:** Run the owning card, notices, settings and Overview layer
      tests; confirm expected failures.
- [ ] **Step 4:** Implement the shared card and relevant-only UI. Exact status
      copy is `SIGMETS: N`; use `Pending`, `Cleared`, `Selected`, `Acknowledge`,
      `Show again`, `Previous`, and `Next` for controls/sections. Use a smooth
      2.5-second border/glow pulse on pending cards and the status border; under
      `prefers-reduced-motion: reduce` render a steady bright border. Keep
      readable text contrast throughout. Remove mobile/desktop wrapper gaps when
      empty. Retain the optional map filter with label
      `Show intersecting polygons only`.
- [ ] **Step 5:** Put source/evaluation diagnostics and explanatory validity
      limits in Configuration's collapsed Diagnostics and expanded reports. Keep
      failed write messages next to their action, not in the ten-foot status
      count. Run all owning tests plus frontend unit suite, lint and production
      build with explicit limits. Commit as
      `feat: simplify SIGMET attention and configuration displays`.

### Task 6: Verify production paths, capture evidence, and provide the revised review server

**Files:**

- Modify `frontend/mission-planner/tests/e2e/route-sigmets-production.spec.ts`,
  `tests/e2e/support/route-sigmets-probe.ts`, and
  `tools/acceptance/aviation-weather/runner.py` only as needed for the extended
  scenarios.
- Update `tools/tests/test_route_sigmets_acceptance.py` for runner proof
  requirements.
- Update `docs/features/overview-weather.md` and `docs/api/aviation-weather.md`.
- Create `docs/reports/2026-10-15-sigmet-attention.md` with exact candidate SHA,
  results and evidence paths.

**Interfaces:**

- Keep
  `tools/acceptance/aviation-weather/run.sh exact-SHA provisioned-browser-executable`.
  Add runner proof fields `quiet_overview`, `manual_selection`,
  `shared_acknowledgement`, `configuration_relevance`, and
  `screenshots_complete`; reject PASS when any required proof is absent or
  false.
- Add production scenarios using two independent browser contexts and the actual
  selection/acknowledgement endpoints. Probe geometry to locate candidates, but
  perform selection with actual pointer/keyboard input against the native
  renderer.

- [ ] **Step 1:** Add failing acceptance scenarios for zero-result silence,
      unknown-only silence, four-count/three-card navigation, map
      nonintersection selection, overlap chooser, same bulletin with several
      polygons, selecting a cleared bulletin, and selecting without a route.
      Verify cross-display convergence within the existing 8,000 ms bound and
      refresh persistence.
- [ ] **Step 2:** Add scenarios covering selected-only acknowledgement from
      Overview, simultaneous selection/acknowledgement, route/run switch during
      a pending write, amendment/expiry/cancellation, compact Configuration with
      a large unrelated feed, and reduced-motion presentation. Capture actual
      Configuration Pending/Cleared, not only Overview. Update runner proof
      tests and verify they fail before adding the required evidence checks.
- [ ] **Step 3:** Complete runner proof collection and retain source/browser
      provenance. Run backend `test_route_sigmets_*.py` plus aviation
      runtime/main regressions, runner unit tests, frontend full unit suite,
      ESLint and production build. Use 10-minute limits for tests/lint and a
      20-minute build limit, each with a 10-second termination grace period.
      Apply repository formatting checks and `git diff --check`.
- [ ] **Step 4:** On a clean committed candidate, run
      `timeout --kill-after=10s 35m tools/acceptance/aviation-weather/run.sh "$candidate_sha" "$browser_path"`
      with the runner's required `ROUTE_SIGMET_REAL_CAPTURE` set to the retained
      pinned real-source capture, the configured actor Docker endpoint
      preserved, and a distinct `starlink-route-sigmets-*` project. Capture
      desktop 1920×1080 and mobile 390×844: empty Overview, pending Overview,
      selected-only Overview, and Configuration Pending/Cleared. Verify fixture
      validity dates before the run. If it fails or times out, verify the owned
      process tree and containers are gone before retrying.
- [ ] **Step 5:** Review screenshots for readability, clipping, pulse/color
      consistency and empty layout. Verify cleanup receipts report no acceptance
      containers, networks, disposable volumes, browsers, workers or listeners.
      Record test counts, SHA, limitations and evidence paths in the report;
      update feature/API documentation to describe geographic relevance without
      implying altitude/time matching. Commit the evidence report and rerun only
      checks affected by any new changes; if product code changes, obtain fresh
      exact-SHA acceptance.
- [ ] **Step 6:** Start a separate persistent synthetic review instance on an
      available LAN port, with explicit owner/Compose project/volumes/stop
      command recorded first. Seed pending intersections, one cleared
      intersection, and a selectable nonintersecting polygon. Use synthetic
      validity covering the review period. Confirm API responses and both
      screens through a closed-after-check browser context. Leave only this
      explicitly requested review runtime and the earlier review runtime alive;
      report both URLs and stop commands so the user can compare them.
- [ ] **Step 7:** Use the requesting-code-review skill for a whole-branch review
      and fix material findings with regression evidence. Push the feature
      branch and open a PR against `dev`, accounting for the original SIGMET
      feature's integration state. Include the reviewed spec/plan and acceptance
      evidence in the PR. Keep the worktree while the PR is open. After merge,
      clean up task-owned worktree/branches/files per workspace rules, while
      retaining a review service only as long as the user's request requires it.

## Execution handoff

Plan self-review checks: every spec section maps to a task, union/wire names are
consistent, selected-only entries never gain fake route spans, all five Review
Focus conditions have explicit owning tests, and the user-requested running
server is preserved.

Recommended approach: Native execution. The six tasks share persistence,
response and presentation interfaces, so implementing them in sequence in one
session avoids repeated context setup. Obtain the required fresh whole-branch
review before handoff. Alternatively, use subagent-driven implementation with an
implementer and reviewer per task if the user prefers the additional review
overhead.
