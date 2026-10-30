# Restore telemetry continuity and configured clocks

> Implementation uses systematic debugging, TDD, parallel clock repair, and a
> final independent review.

**Goal:** Fix the dev regressions reported as stale data, graph gaps, transient
missing ETAs, and four UTC clocks.

**Architecture:** Keep archive recovery off the telemetry collection loop, with
one serial lifespan-owned maintenance worker that is drained before runtime
shutdown. Release the lifecycle state lock during maintenance I/O. Continue
applying the existing ten-second observation freshness rules. Restore each
clock's saved IANA time zone and editable settings.

**Spec:** User's regression report and workspace AGENTS.md.

**Constraints:** Preserve customer-facing Overview layout, estimate behavior,
shared resources, credentials, and unrelated Operator Zulu input controls. Work
only on the feature worktree from origin/dev and open a PR against dev.

## Task 1: Archive isolation

- [ ] Reproduce blocked recovery delaying lifecycle reads and live telemetry
      publication with bounded event-controlled tests.
- [ ] Add `FlightMaintenanceOwner.start()` / `close()` with one serial executor
      job and cancellation-safe draining; wire it into application
      startup/shutdown.
- [ ] Remove archive maintenance from `_background_update_tick`; keep
      initialization reconciliation and accepted sample/detector processing.
- [ ] Release lifecycle state locking during maintenance; serialize maintenance
      and drain before runtime close.
- [ ] Verify recovery failure health, simulation maintenance, live collection
      during blocked recovery, and repeated shutdown cancellation.

## Task 2: Configured clocks

- [ ] Reproduce forced UTC rendering and settings overwrites in clock tests.
- [ ] Restore saved-zone formatting, editable zones, and remove false Zulu
      labels.
- [ ] Verify distinct clocks, DST transitions, and preserving/editing zones.

## Task 3: Verification and review

- [ ] Run focused backend tests, frontend suite, types, and changed-file
      formatting/lint checks.
- [ ] Commit the candidate and run isolated production-image/Nginx/browser
      acceptance with ownership and cleanup evidence.
- [ ] Review the complete diff independently, resolve significant findings, push
      the feature branch, and open a PR against dev.

## Review focus

Slow Prometheus responses must not hold the lifecycle state lock; maintenance
must remain serial; cancellation must drain owned threads before closing
clients; simulation must retain archive recovery without writing simulated
samples; clocks must preserve local time zones across settings saves and DST
changes.
