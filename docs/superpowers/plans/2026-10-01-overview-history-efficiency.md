# Overview history efficiency implementation plan

Issue: #224. Baseline: post-#216 `dev`,
`1542a7d6a64ade14fbef5f8b800e37266743b5c7` (#227).

## Design

- Keep the full public bundle and authoritative five-minute PromQL. Do not add
  recording rules, change telemetry acquisition, or derive statistics from
  displayed samples. One Uvicorn worker is configured; reuse is per process.
- Use a demand-driven cache with one selected configuration, one snapshot and
  one shielded refresh task. Different seconds join the existing refresh instead
  of starting concurrent work. Shutdown cancels/drains it before closing httpx.
  No viewers means no queries or periodic producer. Snapshots are replaced,
  never changed after publication.
- Preserve `ceil(window / 1800)` resolution and the exact selected duration.
  Align the end down and the first evaluation up to the fixed Unix epoch grid.
  Return `start = aligned_end - window`; a non-divisible custom duration can
  start before its first evaluation. There are at most 1,801 points per trace.
- Hydrate once, then replace the authoritative overlapping tail, deleting
  disappeared/non-finite points and trimming the left boundary. Support ten
  seconds of lateness provisionally: the bundled scrape interval and timeout are
  each one second, leaving several scrape cycles of margin. This is an explicit
  supported bound, not a measured production ingestion percentile. Validate the
  margin on the representative host before enabling faster polling.
- Rehydrate after settings invalidation, source/label changes, backwards clock
  movement, a gap over 30 seconds, aggregate recovery, and every five minutes of
  demand to reconcile older corrections. A late sample outside the overlap can
  remain absent until reconciliation. Keep source identities internal; query
  coordinates and cache generation are never observation timestamps.
- Preserve finite-value validation and raw-step aggregate masking. A failed
  aggregate clears all three traces for its metric; recovery rehydrates history.
  Raw failure keeps the internal last-good snapshot without returning it as a
  new response. Return 503, share failures, and back off monotonically from one
  to five seconds. A refresh has a five-second deadline. No request queue grows
  behind a slow refresh. The browser retains explicitly marked last-good data.
- Window changes invalidate synchronously after durable persistence. Old
  in-flight results cannot publish into the new generation. External duration
  changes are detected by the existing durable read; settings storage stays
  unchanged. Changing Prometheus URL/metric configuration requires restart.
- Memoize chart retention/projection and scale scans by accepted bundle,
  descriptor and selected window. Split the projection's clock-only edge from
  aligned traces. Keep compositor movement, labels, freshness, width, fullscreen
  and visibility behavior responsive. One shared query pauses while hidden and
  refetches on focus. Add a build-time 1s/5s cadence switch with error backoff.

## Budget and acceptance gate

Representative host budget: healthy warm response p95 <500ms; combined backend
and Prometheus CPU increase <=10 percentage points over 5s baseline; backend RSS
growth <=16MiB after warm-up over 60 minutes; browser retained heap growth
<=16MiB after warm-up, no extra uploads/projection scans on 250ms clock ticks.
Record actual hardware and exact SHAs when applying these budgets. Do not
interpret mock transport latency as Prometheus CPU or production acceptance.

Keep the shipped default at 5s until the same-host real Prometheus/browser
budget and exact-SHA production-path controls pass. Exercise 1s using
`VITE_OVERVIEW_HISTORY_POLL_SECONDS=1`; rebuilding with `5` is the rollback. The
implementation and draft PR can be reviewed while that gate is pending.

## Implementation and verification

- [x] Add cache/grid/concurrency/settings/shutdown behavior and deterministic
      incremental/full-reference comparisons for 5/15/30/60-minute and custom
      windows, overlap deletion, delayed samples, identity changes and failures.
- [x] Memoize chart work and add a processing-count regression; retain existing
      visibility, motion and scale contracts. Pure frontend controls pass.
- [ ] Run the component processing-count regression and rendered
      motion/lifecycle controls with the complete jsdom/browser dependencies.
- [x] Add a bounded benchmark reporting queried spans/evaluation points,
      cold/warm latency and JSON costs, with one/two sequential viewers and
      bounded cache state. Separate simulated-time tests from a 60-minute soak.
- [x] Update API and Overview guidance with sampling, cache semantics,
      polling/resolution distinction, hidden tabs, failure behavior and
      rollback.
- [ ] Run focused backend/frontend checks, full relevant suites, lint/build,
      repository static checks and exact-head CI. Recheck `dev` before PR.
- [ ] Run isolated production Docker/Nginx controls, real Prometheus comparison
      at optimized 5s and 1s, and a >=60-minute resource soak. Record hardware,
      CPU/RSS/browser heap, SHAs, source/mode/windows/viewport and p50/p95/p99.
- [ ] Record exact-SHA 1920x1080 browser motion and lifecycle evidence. Enable
      the 1s default only after the measured budget passes. Keep #211/#213 open;
      do not claim a cause for long-run degradation from cache improvements.

## Recorded controls

The
[fixture measurement report](./2026-10-01-overview-history-efficiency-measurements.md)
records clean code SHA `f42699e9c3e37f4bb9add51015ffd68bd6858bad`, cold/warm
query work, latency and JSON processing for all selected windows. Local controls
include 96 backend tests, 93 frontend tests, full frontend ESLint, changed-file
Black 26.5.1, filename and typing-policy checks. The simulated-hour state test
is separate from the still-required wall-clock resource soak. Draft PR #228
targets `dev`; the real-host budget, complete suites/CI and production recording
remain acceptance blockers, so the shipped default remains five seconds.
