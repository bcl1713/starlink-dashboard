# Live Export Snapshots Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Continue the
> existing isolated export PR; the user has directed implementation without
> further approval gates.

**Goal:** Export an immutable mid-mission snapshot promptly while recording and
dashboard updates continue.

**Architecture:** Capture committed planning sources and matching prepared
customer pages before telemetry generation. Persist the detached planning
snapshot and optional assembled PDF with the queued job. Assembly reads only
captured inputs; cooperative cancellation checks stop/deadline/job cancellation
without rescanning live dependencies or renderer files.

**Tech Stack:** Python 3.11, SQLite, existing export snapshots and slide cache,
FastAPI, ZIP/CSV.

**Spec:** User follow-up: both formats are slow, live changes reject exports,
and dashboard metrics drop during generation. Retain all previously agreed
telemetry and journal data.

## Global Constraints

- Continue `fix/large-mission-export` in its open-PR worktree, based on
  `origin/dev`; preserve the primary checkout.
- Preserve all retained observations, source semantics, journal revisions,
  import compatibility, checksums, deadlines, cancellation, and storage
  accounting.
- Later saves and live egress changes must not cancel an already captured
  export.
- Capture consistency checks apply while copying planning sources, not
  throughout assembly. Each archive component retains its own declared capture
  interval.
- Use matching prepared PDF pages when available. An uncached optional PDF must
  not delay telemetry delivery; rebuild missing forecast timeline/CSV inputs
  once from the frozen sources and report the existing PDF omission status.
- No changes to Overview presentation or metrics freshness rules.

## Review Focus

- Saves, route/POI edits, and egress changes after capture: finish the original
  snapshot without mixing revisions.
- Restart or another elected worker: use persisted planning, never recapture the
  newer plan.
- Cancellation/deadline during copying: remain bounded without live filesystem
  scans.
- Storage rejection/publication failure: atomically account and release
  persisted planning bytes.
- Missing or dirty customer pages: deliver data promptly, never include
  mismatched PDF pages.

## Task 1: Persist immutable planning

Files: new `app/mission/package/frozen_planning.py`; modify preparation
store/service, artifact quota accounting, and customer artifacts.

- [ ] Add regressions proving later edits retain the original mission
      name/route/POI snapshot, edits during telemetry capture are accepted, and
      queued jobs retain planning after restart.
- [ ] Run focused tests and observe failures.
- [ ] Capture normalized detached inputs and matching ready/failed leg
      snapshots. Serialize through existing snapshot codecs; copy optional PDF
      bytes. Persist atomically with the job and archive descriptor, with byte
      limits/quota accounting and terminal cleanup.
- [ ] Make the package builder consume the frozen snapshot and copied customer
      outcome; retain legacy callers without snapshots.
- [ ] Verify original planning content, matching prepared pages, source
      provenance, restart, quota and cancellation cases.

## Task 2: Remove repeated live work

Files: preparation worker, optional bounded compact-series cache if profiling
warrants it.

- [ ] Add a regression forbidding dependency/renderer scans during assembly;
      retain cancellation/deadline behavior.
- [ ] Run it to observe failure, then remove live supersession checks for frozen
      jobs. Poll persisted cancellation at a bounded cadence and check local
      shutdown/deadline immediately.
- [ ] Reprofile the identical synthetic input; compare actual capture/assembly
      time separately from independent verification time.
- [ ] Preserve data hashes in both formats; avoid compression changes unless
      measurements justify them.

## Task 3: Production responsiveness and delivery

Files: mission archive acceptance fixture/runner, export preparation
documentation.

- [ ] Extend acceptance with saves and live appends during generation,
      continuous metrics/status polling, and recording writes. Assert
      completion, original snapshot content, bounded response latency and no
      export-induced metric invalidation.
- [ ] Run focused regressions, full backend, static and frontend gates; commit
      and push the candidate.
- [ ] Run exact-SHA production Docker/Nginx/browser acceptance with private
      owned resources; preserve timings and cleanup evidence.
- [ ] Request one independent final review, fix important findings, update PR441
      and verify CI and resource teardown.
