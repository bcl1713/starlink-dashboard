# SIGMET Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for
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

  ```typescript
  NoticeSelection(context_key: Hash, bulletin_key: Hash, semantic_digest: Hash)
  ```

- Add `selected: bool = False` to `NoticeRecord` and `RouteSigmetEntry`.
- Add `SelectedSigmetEntry`, containing the same identity, validity, feature
  IDs, attention order and acknowledgement fields as a route entry, but no
  `spans`; it represents selected-only reports.
- Add `selected_entries: list[SelectedSigmetEntry] = []` to
  `RouteSigmetSnapshot`. Keep `entries` exclusively computed intersections and
  preserve its nonempty-span invariant. Enforce combined response size, notice
  uniqueness, and advisory limits across both lists.
- Add

  ```typescript
  NoticeStore.select_sync(change: NoticeSelection, group: BulletinGroup, now_ms: int, *, validate: Validator | None = None) -> NoticeState
  ```

- Extend `reconcile_sync` with keyword-only
  `selection_eligible: list[BulletinGroup] | None = None`; existing `eligible`
  remains the computed matches. This input lets the store reconcile only
  previously selected lineages against the full eligible feed without
  registering the entire feed.

- [x] **Step 1:** Add regressions named
      `test_v1_migration_preserves_ack_and_revision`,
      `test_selection_is_idempotent_and_survives_restart`,
      `test_ack_ends_manual_selection`,
      `test_selected_lineage_amendment_starts_pending`, and
      `test_concurrent_select_ack_has_atomic_revision_order`. Assert existing
      acknowledgement/order values survive migration, repeated selection of an
      already pending entry does not increase order, selecting a cleared entry
      reopens it once, acknowledgement sets `selected=False`, and amendments
      follow only still-selected known bulletin lineage.
- [x] **Step 2:** Run both owning backend test files; record expected failures
      for missing contracts/behavior.
- [x] **Step 3:** Implement the interfaces. Write schema
      `route-sigmet-state-v2`; explicitly migrate valid v1 records to
      `selected=False` under the existing lock and atomic write path. Preserve
      counters and acknowledgement values. Reject unknown/corrupt schemas
      without rewriting. Retain existing LRU/record/byte limits. Reconciliation
      removes cancelled/expired selections from eligibility; unseen or ambiguous
      lineage must not transfer a selection to an unrelated bulletin.
- [x] **Step 4:** Run the same tests plus capacity, disk-failure, lock-timeout
      and two-process regressions. Add assertions that selected-only entries
      cannot manufacture spans and union limits cannot be bypassed with two
      separate lists. Expect all selected tests to pass.
- [x] **Step 5:** Commit as
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

- [x] **Step 1:** Add runtime/API regressions for selecting an eligible
      nonintersection, selecting a matched bulletin without duplication,
      selecting an already cleared notice, acknowledgement removing a
      selected-only notice, no-route rejection, stale semantic/context
      rejection, and no-store headers on every endpoint result. Assert `409` for
      obsolete/no-context selections and unchanged replacement-context state.
- [x] **Step 2:** Run the owning runtime/API tests and confirm failures describe
      the missing behavior.
- [x] **Step 3:** Implement selection through the existing active-leg gate, feed
      eligibility, `_operation` validation and thread-owned store I/O. Inspect
      the full admitted feed for selection eligibility, independently of
      geometry matches. Recheck the exact context/report after awaits. Reuse one
      identity per bulletin and never synthesize a span. Return a fresh snapshot
      after successful selection. Keep unknown diagnostic results separate from
      automatic attention.
- [x] **Step 4:** Verify the task tests plus ordinary/simulation route switches,
      route/feed mutation during I/O, expiration, cancellation, amended lineage,
      feature permutation, multiple polygons, and response budget bounds. Verify
      an acknowledged selected-only report does not return after a feed refresh
      or amendment.
- [x] **Step 5:** Commit as
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

  ```typescript
  setSigmetSelection(change: NoticeSelection, signal: AbortSignal, budget: WeatherBudget, fetcher: typeof fetch): Promise<RouteSigmetSnapshot>
  ```

  alongside the existing request functions, with their timeout/size/error rules.
- Add

  ```typescript
  RouteSigmetSource.setSelection(change: NoticeSelection): Promise<RouteSigmetSnapshot>
  ```

  and `useSelectSigmet()` returning the corresponding TanStack mutation.
- Export `SigmetAttentionItem` as a discriminated union with
  `kind: 'intersecting' | 'selected'`, the appropriate wire entry, resolved
  reports, label and color.
- Export

  ```typescript
  sigmetAttentionItems(snapshot: RouteSigmetSnapshot | null, reports: readonly AviationAdvisory[], nowMs: number): SigmetAttentionItem[]
  ```

  Return only current unacknowledged items, ordered by descending attention
  order then notice key. Deduplicate bulletin identities across both lists.
  Carry a selected-and-intersecting bulletin as `intersecting`.
- Export `sigmetNoticeColor(bulletinKey: string): string`; hash the bulletin key
  into the existing palette `['#7dd3fc', '#f0abfc', '#fde68a']`, independent of
  list position. The same identity retains its color in card and map
  presentation.

- [x] **Step 1:** Add unit regressions asserting an unknown-only snapshot yields
      `[]`, selected plus matched counts once, selected-only has no spans,
      reordered data keeps colors, and expired/cancelled/incompatible-context
      entries cannot enter attention. Add deferred-request source tests where
      selection/ack confirmations arrive around polling, route changes, unmount
      and disposal; assert an older revision never resurrects state.
- [x] **Step 2:** Run the attention, source, service and presentation tests;
      confirm the expected failures.
- [x] **Step 3:** Implement parsing, mutation and the pure attention projection.
      Route all writes through the existing source ownership/cancellation rules.
      Accept only matching context and monotonic state revisions; refresh on
      `409`. Selection responses update the shared snapshot after confirmation.
      Make selected-only acknowledgement disappear immediately after confirmed
      success while preserving matched entries as cleared. Expose all pending
      items from the presentation; the component, not the data source, owns the
      three-card page.
- [x] **Step 4:** Preserve optional map polygon filtering independently of the
      attention filter. Build route-span highlights only for intersection items;
      selected-only items get polygon emphasis without route highlights. Reuse
      admitted source data, rendering budgets and disposal. Run attention,
      source, service, hook, presentation and highlight tests; expect all to
      pass.
- [x] **Step 5:** Commit as `feat: share a concise SIGMET attention model`.

## Tasks 4–6

Continue with [display and acceptance tasks](2026-10-15-sigmet-attention-display.md).

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
