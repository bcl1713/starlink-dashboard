# Coverage and overhead qualification proposal

Status: **proposal only; requires checkpoint authorization**. No calibration,
production benchmark, browser build or soak was performed for this delivery.
[The orchestrator](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6348817582)
requires review of actual overhead and run economics before sustained work. The
earlier three-pair 61-minute schedule is not authorized by this document.

## Preflight and hard stops

1. Freeze the tooling commit and `release-manifest.json` source/fixture hashes.
   Verify the application reference `3cd79e2a`, actual final application build
   inputs, existing diagnostic revision `f7253c68` and frozen `f3029024` runner.
   Record source archives, dirty status, image/base digests and package
   inventory. Never relabel a diagnostic build as the primary application image.
2. Verify the same Forge hardware/actor daemon/context, 2 CPU/2g service limits,
   ancestor quotas, cpusets, competing workloads and filesystem. Keep shared
   workloads and credentials intact. Do not substitute a cloud host. Compare
   runtime and actual browser binary/package hashes with #406's reviewed table.
3. Review a separate diagnostic-build manifest before runtime. Required sites:
   producer dispatch/start/collection/final authority/successful CAS/end/await
   delivery, request ASGI/worker phases, depth-zero repository admissions,
   source identity and actual retained chart input/commit/plot/paint evidence.
   Verify return/exception/cancellation equivalence using deterministic
   call-site tests. The current SDK does not automatically supply these
   integrations.
4. Verify browser response-size/encoding compatibility without altering the
   workload or app polling. Chunked/compressed bodies remain unavailable until a
   separately bounded streaming adapter is reviewed. Do not disable production
   compression or alter headers just to make this implementation capture bodies.
5. Verify stored range-vector export provenance and all 11 field names, actual
   `up`, scrape duration/counts, exact API evaluation/source/request joins and
   sampled-source timestamps. Test monotonic scope and process restart
   identities.
6. Record each owner's command/session, PID/PGID, project, image tags, ports,
   private volumes and paths before starting. Install bounded cleanup. Require
   zero collection loss, per-stream final summaries and complete claimed joins.
   No required boundary may be silently downgraded. Identity mismatch, missing
   required coverage, unexpected HTTP/schema errors or cleanup failure stops the
   schedule; retain the partial run and return for review, with no retry.

The current missing diagnostic integrations make item 3 a preflight blocker.
This is a concrete implementation boundary, not an application-change proposal.

## Fixed bounded schedule after a separate authorization

Use original A `25e34168` and corrected C at the reviewed final application SHA;
revalidate that its runtime bytes match `3cd79e2a`. A lacks frame identity;
record that role-specific absence without fabricating coherence. Use one
sequential owner/project per run, the same synthetic steady workload, two
Overviews and Operator, 1,800 s history, unchanged production polling and 1 Hz
scrape/evaluation. No broad test suite or competing benchmark runs concurrently.

| Stage                    | Order and count                                                                      | Duration                                                      | Decision                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Diagnostic functionality | C once, collector on                                                                 | 15 s total                                                    | Complete joins, zero loss, bounded cleanup or stop                                                    |
| Matched calibration 1    | A off, A on, C on, C off                                                             | 30 s warmup + 60 s measured each                              | Preserve every result; stop on coverage/integrity failure                                             |
| Matched calibration 2    | C off, C on, A on, A off                                                             | 30 s warmup + 60 s measured each                              | Same rules; no replacement runs                                                                       |
| Offline replay           | Same immutable response/delivery fixture into both exact diagnostic frontend bundles | Three fixed repetitions, reverse bundle order in repetition 2 | Equal input schedule and evidence hash; unexplained data/presentation difference blocks qualification |

This is nine runtime runs, 735 s nominal total before cleanup. Cap the whole
functional/calibration owner at 20 minutes with a 10 s termination grace, and
each run at 120 s plus 5 s grace. The collector's 180 s cap does not authorize
running this schedule. No sustained run or result-driven repetition is included.
Offline frontend replay integration remains separately build-gated; it cannot be
replaced by these analyzer-only fixtures. The statistical unit is a complete
matched run, never individual correlated events or polls.

## Calibration outputs and decisions

Report raw enabled-minus-disabled differences for exporter/backend/collector CPU
and thread CPU, RSS/PSS/heap, write bytes/time/I/O, event/body rates, buffer
high-water marks, request/poll latency, event-loop/frame/long-task
distributions, throttle/scheduler counters and total cleanup time. Separate
passive browser, source-observer traffic and diagnostic-build costs. Never
subtract estimated probe overhead from primary performance results. Two
repetitions establish a coverage/overhead checkpoint, not a reliable rare-tail
confidence interval.

Report per-boundary attempted/recorded/joined/ambiguous/missing counts and
per-stream summary/drop coverage. Require complete joins for every claimed phase
and zero dropped bodies/events. Retain ±10 s resource/event context around
anomalies when within run edges; label unavailable edge context. Preserve all
outliers and all fixture/export/input hashes. Verify memory/disk bounds at
maximum permitted body/event size and deliberate saturation in offline tests.

Without complete required coverage, collection is unqualified. With complete
coverage, submit the measured overhead and all tails for a checkpoint decision;
no CPU/latency tolerance is invented here. A material or unexplained overhead
shift requires redesign/review before sustained work. This task does not grant a
performance pass by choosing an arbitrary overhead threshold.

After that review, independently choose sustained run count, order, early-stop
economics and wall-clock budget. Keep frozen primary off runs independent from
supplemental, counter and replay cohorts. Report CPU benefit, data correctness,
chart quality and reliability separately; a CPU interval spanning zero remains
unproven savings. Keep the historical >1.5 s failures unchanged. #390's
eight-hour integration and physical/live-device qualification are independent
open gates.
