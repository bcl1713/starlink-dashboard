# Overview Metric-History Graphs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put five compact, continuously moving history graphs above Upcoming
POIs on `/overview`, each showing observed and trailing-five-minute
low/average/high without a second browser history request.

**Architecture:** Extend the existing shared Prometheus `/api/overview-history`
bundle with bounded aggregates, preserving its raw `series` contract and
five-second frontend poll. Project four truthful traces per metric in a pure
frontend adapter, then render five uPlot panels with clipped CSS-translated
plots and fixed labels in a left layout region. Keep Grafana and live
`/api/status` unchanged.

**Tech Stack:** FastAPI/httpx/Prometheus query_range, pytest,
React/TypeScript/TanStack Query/uPlot, Vitest, Playwright, CSS.

**Spec:** `docs/superpowers/specs/2026-09-29-overview-metric-history-design.md`

## Global Constraints

- Work from the then-current immutable `dev` head in isolated worktree
  `feat/overview-metric-history`; recheck all contracts against it before
  product edits. PR targets `dev`, never `main`.
- The five panels are latency (ms), positive downlink (Mbps), positive uplink
  (Mbps), packet loss (%), and obstruction (%); each has observed,
  trailing-five-minute minimum, average, and maximum. Signal quality is not a
  sixth graph.
- Reuse one `/api/overview-history` frontend request and one persisted
  legend-selected timeframe; retain the current five-second polling interval and
  raw aircraft-trail fields. Do not add configuration-page controls or a second
  frontend endpoint.
- At 1920×1080 all five distinct panels fit above Upcoming POIs without internal
  scroll, obscured globe context, or illegible labels; smaller screens use
  responsive flow.
- A clipped overscan and CSS translation give continuous movement with the
  visible right edge initially ~7.5 seconds behind the current clock. No special
  delay badge. Never extrapolate, bridge missing samples, turn unavailable into
  zero, or hide errors.
- Prometheus performs trailing-five-minute aggregates; the source raw bundle
  uses a maximum of 1,801 samples per series. Preserve its existing sample-step
  planner unless explicit evidence warrants a reviewed change.
- Documentation impact is in scope: extend the history API documentation and
  Overview user/architecture description. Grafana remains fallback and
  untouched.
- Use TDD, small Conventional Commits, independent per-task review, exact-head
  1920×1080 rendered browser evidence, and the canonical project checks. No
  added Python `# type: ignore` directives.

## File structure and contracts

- `backend/starlink-location/app/services/overview_history_rollups.py` (new):
  five-metric allowlist, trailing-5m PromQL planning, bounded aggregate
  query/projection. `query_overview_history_rollups(client, plan)` returns
  `dict[str, dict]` keyed by existing Prometheus metric names, each
  `{state, min, avg, max}`. `state` is `available` or `unavailable`; the other
  fields are timestamp/value arrays. No raw-series duplication.
- `backend/starlink-location/app/services/overview_history_prometheus.py`
  (modify): preserve existing raw query and fields; extend
  `query_overview_history_bundle` with `rolling_5m`, sharing the same query plan
  and existing `OverviewHistoryBundleSingleFlight`. Raw failure still raises;
  aggregate failure yields `unavailable` for that metric, not a failed raw
  trail. One browser API call does **not** promise one internal Prometheus call.
- `frontend/mission-planner/src/services/overview-history.ts` (modify): declare
  `rolling_5m` response type alongside existing `series`; no new service URL or
  hook.
- `frontend/mission-planner/src/pages/overview-metric-history.ts` (new): five
  metric descriptors and pure `projectMetricHistory(bundle, metric, nowMs)`
  producing aligned uPlot arrays and explicit gaps/state, independent of chart
  lifecycle.
- `frontend/mission-planner/src/pages/OverviewMetricHistoryPanel.tsx` (new):
  uPlot lifecycle, fixed surrounding labels/legend, missing-data and last-good
  status, translated clipped surface, ResizeObserver and cleanup.
- `frontend/mission-planner/src/pages/OverviewMetricHistoryPanels.tsx` (new):
  five-panel composition using the shared query result, not five query
  instances.
- `frontend/mission-planner/src/pages/OverviewPage.tsx` and `OverviewPage.css`
  (modify): place graph region above Upcoming POIs with no internal scroll;
  retain clocks/current metrics, map context and legend; adapt responsive flow.
- Existing backend history unit/integration tests, frontend service/hook tests,
  page component/projection tests, and
  `frontend/mission-planner/tests/e2e/overview-globe.spec.ts` plus a focused
  `overview-metric-history.spec.ts` (new) prove the contract and rendered fit.
- `docs/api/endpoints/overview-history.md` (new) and `docs/features/overview.md`
  (modify) document response, behavior, and explicitly deferred configuration
  controls.

## Review Focus

1. A successful raw query with one aggregate query failing still renders the
   aircraft trail and names the affected graph's unavailable statistics; Task 2
   tests it.
2. A successful query with no samples for one metric yields a gap/empty panel,
   not zero or a line carried from an earlier timestamp; Tasks 1 and 3 test it.
3. A persisted custom window longer than an hour remains bounded, with all
   history using the same selected window and query plan; Tasks 1 and 2 test it.
4. A fetch delayed beyond the display buffer never extrapolates the last point
   or lets moving labels drift from plotted timestamps; Tasks 3, 4 and 5 test
   it.
5. A changed history window while an old response is cached does not present
   old-window graphs under the new selector; Tasks 3 and 5 test it.

---

## Task files

- [Backend Tasks 1–2: rolling Prometheus queries and shared bundle](./2026-09-29-overview-metric-history-tasks-1-2.md)
- [Frontend Tasks 3–4: projection and moving uPlot panels](./2026-09-29-overview-metric-history-tasks-3-4.md)
- [Integration Task 5: layout, acceptance, and documentation](./2026-09-29-overview-metric-history-task-5.md)

## Final delivery and review gate

- [ ] Re-run `uv run --with-requirements requirements-dev.txt pytest tests/ -q`
      from `backend/starlink-location`; `npm run test:unit`, `npm run lint`,
      `npm run build` from `frontend/mission-planner`; canonical
      `ACCEPTANCE_POLICY_BASE_SHA=<verified integration SHA>` with
      `uv run --with pytest ./tools/verify static` (or project-supported exact
      equivalent) from repo root; and exact-head Chromium Overview acceptance at
      1920×1080. A test that cannot run is a blocker, not a pass. Refresh the
      live `origin/dev` SHA and reconcile divergence before PR publication.
- [ ] Have an independent whole-branch reviewer inspect spec adherence,
      correctness, security/performance, data gaps, browser layout, docs, and
      changed-file policy at the exact pushed SHA. Rework and re-review on the
      same branch/PR; push only verified commits to its own upstream. Record
      review and acceptance in the plan-owned
      `.superpowers/sdd/2026-09-29-overview-metric-history/` ledger.
- [ ] After exact-head CI and review are green, verify PR
      base/head/non-draft/mergeable status; merge into `dev` only, run
      post-merge affected suites and exact-merge-SHA browser acceptance, then
      read back the issue/PR state and record evidence. `main` is Brian-gated
      separately.
