# Overview history efficiency follow up implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution or superpowers:subagent-driven-development if Brian
> selects that method. Track the steps below without repeating shipped work.

**Goal:** Qualify issue 224's remaining performance gaps with reproducible
real-Prometheus and production-browser evidence, then address measured costs
before conditionally promoting the one-second default.

**Architecture:** Add task-owned measurement tooling around the shipped reader
and production HTTP/browser path. Compare full-range 5s, incremental 5s and
incremental 1s on the same host and equally populated histories. Keep profiling
overhead separate from acceptance measurements and retain raw evidence.

**Tech Stack:** Python 3.11, httpx, pytest, Docker Compose, Prometheus 3.5.0,
Node 22, locked Playwright/Chromium, production FastAPI/Nginx/React/uPlot.

**Spec:**
[Approved addendum](../specs/2026-10-04-overview-history-efficiency-follow-up-design.md),
continuing
[the existing implementation plan](2026-10-01-overview-history-efficiency.md).

## Global constraints

- Start from inspected `dev` SHA `913175dc0e19a349a9d724d1e7efcb32f1489099`;
  recheck remote `dev` and preserve unrelated work before execution.
- Run builds, containers, browser and sampling on the current Forge executor.
  Record hardware; preserve actor Docker configuration/proxy/CA trust.
- Preserve PR 228's cache, full public bundle, authoritative five-minute PromQL,
  source provenance and aircraft trail. Do not redo shipped tasks.
- Preserve issue 257's background polling, focus refresh and cancellation.
  Hidden charts pause motion; background ingestion remains enabled.
- No recording rules, delta interface or scheduler rewrite is selected.
- Keep default 5s and opt-in 1s until applicable acceptance passes.
- Budget: healthy warm p95 <500 ms; backend/Prometheus CPU increase <=10
  percentage points of one core over comparable full-range 5s; backend RSS and
  browser retained heap growth <=16 MiB over >=60 minutes after warm-up.
- Keep earlier operator exceptions scoped to their candidate. Distinguish
  SwiftShader from physical GPU and synthetic from live telemetry evidence.
- Use a task-owned checkout and Compose project. No production deployment,
  shared-resource cleanup, main promotion or issue 211/213 closure.

## Review focus

1. Missing samples, insufficient duration or failed cleanup cannot pass
   acceptance: task 1 tests incomplete evidence.
2. Two viewers must demonstrate both simultaneous and sequential arrivals: tasks
   2/3 measure both rather than extrapolating from one viewer.
3. Profiling overhead, history density and sampling grids can distort cost: task
   2 tests unchanged grids and compares identical replay endpoints.
4. GC, hidden tabs and suspension can distort memory/cadence: task 3 separates
   ordinary/post-GC samples and includes background/resume observations.
5. Interruptions must preserve evidence and stop only owned resources: task 2
   tests runner failures and task 4 audits cleanup.

## Task 1 Performance evidence and budget evaluator

**Files:** Create `tools/acceptance/overview_history/__init__.py`,
`tools/acceptance/overview_history/report.py` and
`tools/tests/test_overview_history_performance_report.py`.

**Interfaces:** `summarize_phase(samples: list[dict], metadata: dict) -> dict`
accepts monotonic timing/resource rows and phase provenance.
`evaluate_budgets(baseline: dict, candidate: dict) -> dict` returns each budget
as `passed`, `failed` or `incomplete`, with measured value, units and reason.
Metadata includes SHA/images, hardware/renderer, window/viewers/cadence, fixture
identity, GC mode, warm-up/measured durations and cleanup outcome.

- [x] Add `test_nearest_rank_quantiles`, `test_missing_samples_are_incomplete`,
      `test_cpu_uses_percentage_of_one_core`, `test_exact_budget_boundaries`,
      `test_short_soak_is_incomplete` and
      `test_mixed_phase_provenance_is_rejected`. Their assertions cover
      nearest-rank p50/p95/p99; no-sample `incomplete`; 0.5 CPU seconds over 5
      seconds = 10 percent of one core; process CPU summed before baseline
      subtraction; exact 16 MiB growth passes and one extra byte fails; 500 ms
      p95 fails; 3599-second soak cannot pass. Reject negative time/CPU deltas
      and mixed provenance within one phase. Missing comparable baseline,
      behavior evidence or cleanup leaves the relevant gate incomplete.
- [x] Run the new pytest file and record missing-module failures.
- [x] Implement both interfaces. Report CPU in percentage of one core, with
      logical-CPU host normalization separately labeled. Separate ordinary and
      post-GC heap results; preserve endpoint growth and late-run trends.
- [x] Run new tests and existing benchmark-report tests; all must pass.
- [x] Commit evaluator and approved planning documents on the task branch.

## Task 2 Real Prometheus and backend cost controls

**Files:** Create `tools/acceptance/overview_history/seed.py`,
`tools/acceptance/overview_history/backend_probe.py`,
`tools/profile_overview_history.py`,
`tools/acceptance/overview-history/compose.yml`,
`tools/acceptance/overview-history/run.sh`,
`tools/tests/test_overview_history_performance_runner.py` and
`tools/tests/test_profile_overview_history.py`.

**Interfaces:**
`write_seed(output: Path, end_seconds: int, duration_seconds: int = 4200) -> None`
emits deterministic one-second OpenMetrics observations for the 11 raw metrics
using production scrape labels. Import with pinned
`promtool tsdb create-blocks-from openmetrics`; current scrapes use public
simulation. The historical seed is explicitly synthetic.

`backend_probe:app` wraps `main.app` only during instrumented controls,
retaining its lifespan, client/settings and invalidation/shutdown. Profile mode
`full` binds an uncached reader using `query_overview_history_bundle` with the
fixed-grid planner; `incremental` wraps the existing reader. Counters cover
query bounds/points, errors/cancellations and read/request timing without
logging telemetry payloads or retaining unbounded request lists.

CLI:

```sh
python tools/profile_overview_history.py --prometheus-url URL \
  --end E --window W --cadence {1,5} --mode {full,incremental} \
  --samples N --output PATH
```

Replay identical historical endpoints through real httpx, with two sequential
readers. Save cold/warm timings, query bounds/count/points, diagnostic cProfile
and JSON encoding time separately.

- [x] Write runner tests patterned on `test_overview_window_runner.py`: reject
      dirty inputs, occupied ports and existing project resources; preserve
      build metadata when browser output resets; retain logs and clean owned
      resources on interruption/failure. Profiler controls cover unchanged 2s/3s
      grids, query errors, cancelled waiters and zero extra queries from a
      second same-interval incremental read. Seed tests assert 4201 observations
      per metric, sorted timestamps, finite zeros/spikes and reproducible
      relative values.
- [x] Run new tests and record failures before implementation.
- [x] Implement seed/CLI/probe/runner. Project `starlink-224-history`, loopback
      ports 18224/15224/19224, task-only named volumes, clean tracked SHA
      archive, separate frontend poll-1/poll-5 images and evidence outside
      source. `run.sh --check` is nonmutating preflight. Refuse existing project
      resources.
- [x] Build production images without Dockerfile changes. Mount archived
      acceptance probe code only for instrumented controls; override only the
      test entrypoint/history URL as needed. Preserve Nginx and scrape/rule
      config. Use documented 3h test retention so preload plus soak cannot
      expire history. Check seed labels do not create a second usable metric
      source.
- [x] Run tests, validate seed with promtool and smoke populated cold history
      through Nginx for all selected windows. Label full/fixed-grid as an
      uncached computation control, not the historical moving-grid/browser
      build.
- [x] Replay 300/900/1800/3600/3601-second windows at identical endpoints for
      all three modes. Exercise two sequential/concurrent readers, scheduled
      full reconciliation and failure/recovery. Keep cProfile diagnostics
      separate from uninstrumented acceptance distributions. Commit after
      controls pass.

## Task 3 Browser cost and lifecycle measurement

**Files:** Create `tools/acceptance/journeys/overview-history-performance.mjs`,
`tools/acceptance/journeys/overview-history-probe.mjs` and
`tools/tests/test_overview_history_browser_contract.py`. Retain existing
`OverviewMetricHistoryPanel.test.tsx` and `useOverviewHistory.test.ts` controls.

**Interfaces:** Journey arguments are:

```text
--session CDP_URL --origin LOOPBACK_URL --artifacts DIR --cadence {1,5}
--viewers {1,2} --window SECONDS --warmup-seconds 300 --duration-seconds N
```

Use locked Playwright and the established platform-owned browser lifecycle. Emit
append-only request timing, API errors, ordinary/post-GC heap, long-task
summaries, process CPU/RSS and behavior observations.
`installOverviewHistoryProbe()` uses bounded counters for JSON processing and
plot canvas activity; CDP profiles and existing unit controls distinguish
projection/upload work from clock ticks.

- [x] Write argument/evidence tests for 1920x1080 DPR1, bounded probe storage,
      separate GC samples, two actual pages for two viewers, and no pass before
      requested duration. Timer delay, request starts and response intervals
      must remain separate fields. Do not intercept the healthy production
      history API.
- [x] Run tests, record failures and implement journey/probe. Record GC markers
      at warm-up/end and every 5 minutes as diagnostic interruptions; avoid
      presenting those periods as undisturbed frame-continuity evidence.
- [x] Run existing processing/motion/retention and history hook controls.
      Clock-only updates must not reproject/upload. Preserve error backoff,
      background polling, focus refresh and query cancellation assertions.
- [x] Run bounded real-path journeys for both cadences, one/two viewers and all
      windows/transitions. Exercise hidden/resume, remount, resize and native
      fullscreen; inspect fixed axes/readouts, gaps, last-good data, trail and
      duplicate subscriptions. Record source/clock/restart deterministic
      controls alongside rendered coverage limits. Controlled error runs are
      separate.
- [x] Capture arrival/rebase screenshots/video where supported. Record renderer
      and unsupported native/recording coverage as explicit gaps. Commit after
      tests and bounded browser controls pass.

## Task 4 Controlled baseline and sustained comparison

**Files:** Create
`docs/reports/2026-10-04-overview-history-efficiency-follow-up.md`; modify
`docs/api/endpoints/overview-history.md` and relevant Overview guidance. Raw
evidence goes in a task-owned SHA-qualified directory outside source.

**Interfaces:** Consume task 1 summaries and tasks 2/3 artifacts. Produce a
report containing exact phase SHAs/images, hardware, source/data density,
viewport/renderer, cold/warm quantiles, CPU/RSS/heap, cadence and cleanup.

- [x] Freeze candidate; run focused and canonical relevant backend/frontend/
      static checks. An intentionally short run must report incomplete sustained
      acceptance. Inventory artifacts and checksums.
- [x] On the same host, run populated-history full-5s, incremental-5s and
      incremental-1s phases with 300s warm-up and >=600s measured duration each.
      Keep viewer/window/browser configuration equal. Repeat in reverse order if
      phase ordering or host load changes conclusions.
- [x] Run >=3600 measured seconds after warm-up at incremental 1s, first one
      then two viewers; sample CPU/RSS/heap every 5s. Save requests/phase
      markers on disk, including scheduled full loads. Provide user updates at
      least once per minute while supervising. Preserve evidence on
      interruption.
- [x] Evaluate budgets and retained-heap endpoints/trends. Publish failed or
      incomplete gates, verify checksums and task-only cleanup.
- [x] Correct the API's hidden-tab statement to shipped background polling.
      Document fixture/profiler/renderer/baseline limits. Attribute cadence loss
      only where query/timer/browser profiles support it. Commit
      report/guidance.
- [x] If a bottleneck fails a budget, append a focused implementation task with
      exact reproducer, interface and before/after measurement before product
      edits. Material interface/statistics/scheduling changes require design
      review. Otherwise continue to task 5; measurements cannot silently waive a
      gate.

## Task 5 Conditional default promotion and final review

**Files if qualified:** Modify
`frontend/mission-planner/src/hooks/api/useOverviewHistory.ts`,
`frontend/mission-planner/src/hooks/api/useOverviewHistory.test.ts`,
`frontend/mission-planner/Dockerfile`, `docker-compose.yml`,
`docs/api/endpoints/overview-history.md`, `docs/features/overview.md`, and the
task 4 report. Update other cadence documentation only if repository search
identifies a statement invalidated by the default change.

- [ ] Proceed only after applicable performance/behavior gates pass; explicitly
      record any operator-approved alternative evidence, without inherited
      waivers.
- [ ] Add failing cadence tests: undefined selects 1000 ms, explicit `5` selects
      5000 ms, explicit `1` selects 1000 ms, invalid values safely select 5000
      ms, errors select 5000 ms. Preserve shared query/focus/background
      behavior.
- [ ] Update helper and all build defaults consistently. Preserve explicit
      `VITE_OVERVIEW_HISTORY_POLL_SECONDS=5` rollback; keep cadence distinct
      from acquisition freshness and long-window resolution. Run
      hook/build/config tests.
- [ ] Rebuild at the product candidate's exact SHA. Run fresh relevant canonical
      checks, production/browser controls and sustained acceptance after
      material changes. Require exact-head CI and whole-branch review before
      integration.
- [ ] Deliver a separate PR against then-current `dev`, with passing gates or
      documented blockers. Do not merge/deploy under this measurement plan. Post
      independently relevant issue 211 findings only if externally authorized.

## Execution handoff

Brian approved the addendum and this plan and selected native execution. Native
execution runs in `/tmp/starlink-224-followup`; the durable task ledger records
completed steps and evidence. Earlier implementation approvals and acceptance
remain intact.

## Focused task 4a Remove redundant HTTP conversion

**Measured trigger:** The pre-change HTTP profile spends 0.351 of 0.380 profiled
seconds recursively converting an already primitive history bundle. The
published full-range diagnostic p95 is 674 ms. The fresh two-viewer incremental
1s phase's initial 99 warm requests have p95 706 ms and no HTTP/browser errors,
with combined CPU about 50.5% of one core; its complete 600-second evidence will
be retained. No default promotion is authorized by these partial measurements.

**Files:** Modify `backend/starlink-location/app/api/overview_history.py`; extend
`backend/starlink-location/tests/unit/test_overview_history_api_cache.py`.

**Interface:** Preserve GET status, media type, full JSON bundle, timestamps,
finite values, gaps and aggregate states. Return `JSONResponse` for the already
validated immutable primitive bundle, avoiding FastAPI's duplicate recursive
conversion. Keep the reader's dict interface, coalescing, invalidation, failure
mapping and JSON rendering unchanged. No byte cache, public delta interface or
scheduling/statistics change is selected.

- [x] Write a failing real-ASGI regression proving identical compact JSON bytes,
      immutable shared reader snapshots and no generic conversion of the bundle.
- [x] Watch the old endpoint fail that assertion; return `JSONResponse` directly
      and run the regression plus existing history API/cache/reference controls.
- [x] Rebuild the exact product candidate. Repeat the separate HTTP profile and
      populated real-path/native controls, keeping profiler overhead outside
      latency/resource distributions.
- [x] Complete canonical checks, comparable full-5s/incremental-5s/incremental-1s
      phases and fresh one/two-viewer sustained evidence. Report before/after
      attribution and gates before considering task 5.
