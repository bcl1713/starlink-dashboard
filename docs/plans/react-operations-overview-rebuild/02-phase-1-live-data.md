# Phase 1: Independent Live Data

## Identity, input, and objective

Repository `bcl1713/starlink-dashboard`; PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`; base `dev`; feature
`feature/react-operations-overview`. Clean baseline was
`07593c69040ad447000bf526d6453ec5c6faacfa`; historical implementation
`e649ce169cd5adcbdd83d6264290b30d5221599e` belongs at
`archive/pr-143-pre-simplification-e649ce1`.

Input is the exact Oracle-published Phase 0 docs-only SHA recorded in
`SESSION-HANDOFF.md`; never invent it. Build independently scheduled live-stat,
local-history, and overlay lanes from that head. Oracle owns remote publication.

## Product contract

Follow [the full contract](00-product-contract.md). In this phase specifically:

- `/api/status` is the live hot path and remains same-origin.
- Cadence options are exactly `1/2/5/10/30/paused`; `1s` is unconditionally the
  default and fastest. Phase 1 implements and tests this decision; it does not
  decide it.
- One recursive monotonic timer schedules promptly after request settlement,
  with a bounded browser timeout: no overlap, replay, catch-up burst, or global
  transaction. Hidden pauses and visible resume makes exactly one immediate
  request. A slow overlay/history lane cannot delay status.
- Accepted status samples feed bounded local ring buffers. Retain last-good
  content and distinguish observation, receipt, stale, loading, and error.
- Call `/api/monitoring/history` once at bootstrap, on resume/reconnect after a
  detected gap, and on explicit manual reconciliation. It only seeds/repairs
  30-minute buffers, never current values. Optional 30–60 second reconciliation
  requires runtime justification.
- Browser input never contains arbitrary PromQL or upstream URL. History and
  upstream bodies are bounded; CSP remains restrictive; no GEP public IP.
- Grafana is a fallback only. React makes no Grafana request.

Phase 1 supplies data and components for the binding one-screen inventory:
exactly four clocks; current-position map; top-five applicable POIs; current
latency plus five-minute min/average/max; current download/upload; GEP;
obstruction; packet-loss current/average/max; selected refresh interval; and
last successful update or concise failure. Route, track, active-link,
satellites, events, radar, and ancillary controls are optional salvage only.

**Out:** pixel-perfect/fullscreen composition, real-stack acceptance, Grafana
retirement, broad backend refactoring, and operator rollout docs.

## Advisory paths after inspection

These are likely, not binding until the Phase 1 writer inspects the published
head:

- `backend/starlink-location/app/api/status.py`
- `backend/starlink-location/app/models/telemetry.py`
- `backend/starlink-location/tests/integration/test_status.py`
- `frontend/mission-planner/src/App.tsx`
- `frontend/mission-planner/src/services/api-client.ts`
- `frontend/mission-planner/src/services/monitoring.ts`
- `frontend/mission-planner/src/types/monitoring.ts`
- `frontend/mission-planner/src/pages/OverviewPage/`
- `frontend/mission-planner/src/hooks/overview/`
- `frontend/mission-planner/src/pages/OverviewPage/*.test.tsx`
- `frontend/mission-planner/tests/e2e/api-origin.spec.ts`

Do not preserve archive file structure merely because it already exists.
Selective salvage requires a written reason and diff-level review.

## Bounded TDD task order

**TDD expectation:** Each code task proves a narrow RED for the contract, the
minimum GREEN implementation, and a behavior-preserving REFACTOR before broader
checks. Timer tests use deterministic clocks and explicit pending requests.

1. **Inspect and freeze contracts.** Record exact input SHA/clean tree; inspect
   current status DTO, history DTO/query, router, frontend harness, CSP/Nginx,
   overlays, and tests. Pin the `1s` default/fastest cadence and 30-minute ring
   bounds in tests/handoff.
2. **Status hot path.** RED tests pin finite typed fields, truthful source time,
   safe errors, no GEP IP, and bounded work. Make `/api/status` avoid new
   network, Prometheus, overlay, or disk waits; preserve compatibility where
   intentional.
3. **Scheduler primitive.** RED fake-timer tests cover exactly one recursive
   monotonic timer, bounded request timeout, all cadence values, prompt
   post-settlement scheduling, hidden pause, exactly one immediate visible
   resume, cancellation/unmount, manual refresh, slow requests, recovery, no
   overlap/replay, and no burst. Pin the timing oracle: `1s` start intervals
   0.8–1.3s and at least four successes/5s; `5s` no start before 4.5s and one by
   5.5s; `5s`→`1s` next start within 1.3s after settlement; paused manual
   refresh exactly one request.
4. **Live lane.** RED service/hook/component tests cover origin-relative status,
   external DTO validation, last-good state, source freshness, and controls.
5. **Bounded history/backfill.** RED property/boundary tests prove insertion,
   chronological order, invalid rejection, 30-minute eviction, fixed memory,
   bootstrap once, gap-detected resume/reconnect, explicit manual
   reconciliation, and that backfill never changes current values. Retain fixed
   allow-listed queries, point/body bounds, timeout/cancellation, finite
   validation, and safe errors. Deliberately decide/test whether constant
   identity is a deployment-wide backfill guard or remove it; add 30–60s
   reconciliation only with runtime proof.
6. **Required map/POI/GEP data.** RED tests intentionally hold one source
   pending while status and unrelated lanes advance. Implement only what the
   exact one-screen inventory needs.
   Route/track/active-link/satellites/events/radar and ancillary controls are
   optional salvage, never Phase 1 or 2 dependencies.
7. **Integration states.** RED tests cover loading, empty, stale, partial/total
   failure, recovery, IDL, cadence persistence if adopted, same-origin requests,
   CSP, no Grafana request, and no GEP IP in DOM/logged errors.
8. **Refactor and bound.** Remove duplicate timers/global aggregators, abort
   owned requests on teardown, cap caches/listeners, and document deviations.

For every task: write the narrow test, run and retain expected RED, implement
the minimum, prove focused GREEN, refactor, rerun focused checks, then commit a
cohesive conventional increment. Never manufacture RED by breaking unrelated
code.

## Exact checks

Finalize commands after inspecting available scripts, recording substitutions.
Minimum focused checks are changed backend status tests and changed frontend
scheduler/service/component tests. Minimum phase-wide checks are:

```bash
set -euo pipefail
cd backend/starlink-location
python -m pytest tests/integration/test_status.py -q
python -m pytest -q
python -m ruff check app tests

cd ../../frontend/mission-planner
npm run lint
npm run build
npx vitest run
npx playwright test tests/e2e/api-origin.spec.ts

cd ../..
pre-commit run --all-files
git diff --check
```

If the repository's Vitest configuration/script differs, use the inspected
command and record it. Backend Python changes also require the repository's
no-cache Docker rebuild/health sequence before claiming local runtime behavior,
but Docker execution belongs to a capable, isolated writer session and must not
reuse production credentials/resources.

## Independent gates

**Specification review first:** verify every product bullet, RED/GREEN evidence,
all cadence values, bounded ring behavior, hot-path dependencies, independent
slow-lane evidence, security/CSP/no-Grafana/no-IP boundaries, changed paths, and
scope exclusions against the exact candidate SHA.

**Quality review second:** inspect types, timer ownership, cancellation/race
handling, finite bounds, parser/error cohesion, test determinism, accessibility,
and file-size/naming policy. Reviewers do not edit.

Findings return to the one writer, create a new candidate SHA, and invalidate
prior review evidence.

## Public handoff, docs, cleanup, and stop

Oracle's exact PR handoff records input/output SHAs, base/feature, archive ref,
changed paths, selective salvage decisions, focused/full results, runtime
limits, spec then quality dispositions, docs impact, cleanup, gaps, and next
action.

Documentation impact: update this roadmap/handoff only for contract changes;
operator/user docs remain explicitly pending Phase 4. Remove task-owned test
servers, browser processes, output, caches, and runtime resources; preserve
unrelated resources.

Completion requires reviewed immutable code with the live/status path advancing
at selected cadence without overlap/burst while an independent lane is slow,
bounded 30-minute history with the contracted backfill triggers, all scheduler
timing oracles green, and a clean tree. The real ten-second `1s` oracle requires
at least eight successes and a median interval of 0.8–1.3s. Stop. Phase 2 starts
in a new session from Oracle's published Phase 1 SHA and outputs a reviewed
exact 1920x1080 fullscreen candidate.
