# Active mission context snapshots (issue 392)

The live telemetry path previously listed and loaded every retained v2 mission
and then reloaded the selected mission during admission. The accepted context is
now an immutable selection containing serialized selected-mission bytes, mission
and leg IDs, a mission digest, accepted route identity, and a generation. It
does not retain all mission models. Public resolver callers receive detached
models; live recording uses a compact binding without parsing those bytes.

## Coherency and ownership

All cache publication and reads use the existing repository-wide active-leg
gate, before parent/component locks. Persistence notifications advance an
in-process generation even without a metrics subscriber. Ordinary saves,
activation/deactivation, planning publication/compensation, availability writes,
and direct mission deletion invalidate the selection. Route identity is checked
at every admitted read; replacing, removing, reloading or switching an accepted
route cannot reuse the prior binding. Callbacks only invalidate; they do not
reconcile or acquire another write lock.

A lifespan owner checks saved-file inventory on an executor worker,
independently of telemetry collection. It polls every 250ms and inventories at
most once per second when unchanged. The normal external-edit detection window
is therefore one second plus scheduling delay. Inventory includes every mission
metadata file and non-timeline leg file, including mission/leg membership,
inode, size and nanosecond mtime/ctime. A second inventory after parsing rejects
a concurrent uncoordinated edit. This also detects edits from another process,
removal, atomic replacement and same-size writes. No external process must send
an in-memory invalidation signal.

Inventory scanning remains proportional to retained mission/leg files. It is
separate from the live tick, performs no JSON reads when unchanged, and uses the
existing fair admission gate. Source changes trigger full reconciliation so a
second active leg cannot hide in a retained inactive mission. A corrupt file,
duplicate/mismatched directory identity, pending recovery journal or failed scan
suppresses the old binding. Failed reconciliation is throttled too. Recovery
retries on the same schedule or immediately after an admitted local mutation.

The poll deadline schedules reconciliation; crossing it never changes the
identity of unchanged in-flight telemetry. If the independent owner cannot
verify storage for three seconds, admitted cached reads return unavailable.
Telemetry without a valid binding may still be archived globally, but cannot be
attached to the previous mission/leg. Input changes during collection or
recording reject the old source before leg observation and phase
synchronization.

The owner drains its executor work during normal or repeatedly cancelled
shutdown. Standalone ticks without a lifespan owner reconcile on their existing
worker before and after collection. Synchronous resolver consumers can reconcile
on demand; HTTP handlers that use them execute in the thread pool. Simulation
and replay retain their existing producers and readiness models.

## Validation and measurement

The focused regression counts real JSON I/O across 125 accepted live ticks and
verifies mission/leg/timestamp association. Additional tests exercise local
invalidation, external edits/removal, conflicting active legs, duplicate IDs,
route changes, reconciliation races, immutable response isolation, retry
throttling, stalled-owner behavior, loop responsiveness and cancellation
cleanup.

`tools/benchmark_active_context.py` runs the same context-resolution/admission
workload against an explicitly selected backend source directory, using private
fictional storage. It reports cold and warm wall/thread CPU, metadata and leg
reads, bytes, model entry points, stat/enumeration counts and log volume for
0/1/10/100 missions with four legs each. Instrumented timings include counter
overhead. They do not measure telemetry transport, SQLite or HTTP.

`tools/acceptance/active-context/soak.py` is an explicit pytest entry point for
a wall-clock live-like soak. It reuses the real live coordinator with stubbed
dish transport, real SQLite recording, and concurrent ASGI status/Operator
records requests over 100 fictional missions/four legs each. Its lifespan and
private stores are closed by the existing fixture and owner. This lane does not
measure Docker, Nginx, physical-dish freshness or rendered browser performance.
Run the production-image/browser lane separately and keep those claims distinct.

## Measured results (2026-10-27)

Application reference: preceding `dev`
`a0cdcfbe0b6923f18f77854d43edcf94ad16f5b0`. Candidate and frozen measurement
harness: `0426b6163c02b38f84550fd4d04fbb5052456077`. The candidate's application
tree and `main.py` are identical to production-image candidate
`83d8ce08e91f880b600b291c14d93e3436be06ac`; intervening commits change tests and
measurement tooling. The original epic application
`25e34168f0e2cecb149b0323f1f5a795cb28cae0` has a separate context-only benchmark
cohort. These new workloads supplement the original #390 controls.

The matched host has an Intel i9-10900K (20 logical CPUs), Python 3.11.16 and a
tmpfs test filesystem. Each application uses the same interpreter and frozen
harness. Filesystem probes count actual file reads/bytes and Python OS stat,
lstat, listdir and scandir entry points. Path-level counters overlap with OS
counters; they are not summed. Gate acquisition wall time includes locking
mechanics and contention. Instrumented timings include probe overhead.

### Context resolution and two admission checks

Three repetitions per application, 250 warm operations per case, four legs per
mission. CPU is the median of the three run means. Original-application results
and min/median/max variation are retained in the
[benchmark summary](../reports/2026-10-27-active-context/microbenchmark-os-summary.json).

| Missions | Previous CPU ms/op | Candidate CPU ms/op | Mission JSON reads/op | OS stat/lstat calls/op |
| -------- | ------------------ | ------------------- | --------------------- | ---------------------- |
| 0        | 0.228              | 0.116               | 0 → 0                 | 22 → 10                |
| 1        | 1.504              | 0.352               | 17 → 0                | 77 → 30                |
| 10       | 6.191              | 0.355               | 80 → 0                | 320 → 30               |
| 100      | 54.895             | 0.353               | 710 → 0               | 2750 → 30              |

The 100-mission original-application control measured 55.797 ms/context, 710
JSON reads and 2,750 OS stat/lstat calls per operation. The new bounded read
measures 0.353 ms/context, zero mission reads and 30 OS stat/lstat calls with a
nonempty active selection. Cold reconciliation remains proportional to retained
files; its work is explicit in the cold counters.

### Matched steady live-like runs

Each source completed 3,660 measured wall-clock seconds after five warm-up
ticks, with 100 missions/four legs each, one manually driven live tick per
second, and concurrent status/Operator records ASGI probes. The fixture stubs
dish transport, controls UTC acquisition time and disables route watchers.
Candidate reconciliation runs independently. Live collection, SQLite recording,
admission, metrics preparation and ASGI handlers remain real. Every status
acquisition and position observation passes a five-second freshness check.

| Metric                         | Preceding dev | Candidate | Change |
| ------------------------------ | ------------- | --------- | ------ |
| Process CPU (seconds)          | 465.961       | 94.016    | -79.8% |
| Tick thread CPU mean (ms)      | 62.024        | 6.482     | -89.5% |
| Tick wall p95 (ms)             | 152.195       | 13.149    | -91.4% |
| Status ASGI p95 (ms)           | 125.975       | 6.460     | -94.9% |
| Operator records ASGI p95 (ms) | 4.907         | 6.257     | +27.5% |

Each run accepted 3,660 observations and completed 3,660 status plus 3,660
Operator records requests, with zero errors. Mission JSON reads fell from
5,160,600 (2,277,354,480 bytes) to zero across the coupled workload. Total
process read calls fell from 10,665,186 to 344,187; `rchar` fell from
3,084,226,224 to 807,323,414 bytes. Existing SQLite/log writes remain: `wchar`
was 271,561,744 versus 271,657,186 bytes. Physical block reads/writes were zero
on tmpfs. INFO volume remained six records per run, with no warnings or errors.

The negative latency result is explicit: Operator-record p95 increased by 1.350
ms, or 27.5%, to 6.257 ms. This single matched pair does not establish its cause
or statistical variability. Status p95 and tick p95 improved in this workload;
all request rates and freshness checks passed.

After the first five measured minutes, observed process RSS rose from 252.227 to
260.777 MiB in the reference and 249.082 to 254.207 MiB in the candidate. Warm
OLS slopes were +13.066 and +7.228 MiB/hour. These include bounded measurement
buffers and allocator behavior; a one-hour slope is not a leak diagnosis or
proof of unbounded growth.

The stationary fixture emitted no flight events in either run and retained one
leg state. The unchanged 35-minute rolling-archive policy retained 2,105 versus
2,100 timestamps at teardown, depending on the ten-second GC phase. Every
retained timestamp had all nine metrics; maximum gaps were 1.002 seconds.
[Archive continuity](../reports/2026-10-27-active-context/archive-continuity.json)
and
[SQLite counts](../reports/2026-10-27-active-context/sqlite-count-comparison.json)
record this check. Positive movement/event transitions, mission switches,
replay, export and recording failures are covered by the regression suites; the
stationary soak does not exercise every detector phase.

Full normalized CPU, I/O, memory, counter and freshness results are in the
[live-like comparison](../reports/2026-10-27-active-context/live-like-comparison.json).
Raw logs, per-command ownership, source/harness identities and reports are
retained at `/tmp/issue392-evidence`. The source/harness Git bundle and hash
inventory preserve the frozen revisions independently of later branch cleanup.

### Correctness, production path and limitations

- Local unit/Operator/selected-integration run: 3,561 passed; final focused run:
  75 passed. The latter includes the 125-live-tick zero-read/association check.
- Canonical static gate passed, including 151 policy tests. All backend shards,
  frontend test/build and static CI gates passed on the frozen measurement head.
- Exact-SHA production images, Nginx, Prometheus and a rendered Overview plus
  Operator completed 90 measured seconds after 30 seconds warm-up, including
  mission switch/deactivation/reactivation, with no request failures. This is a
  simulation functional control, separate from the live-like ASGI measurements.
- Two subsequent production attempts at docs/evidence head `6d830859` failed
  the unchanged synthetic-history density gate (one final, one initial). Raw
  capture showed 11 finite series with 300/301 points, missing the newest second.
  The same harness against unchanged preceding `dev` also failed final density,
  with two interior seconds missing. History services and this harness have no
  source delta. These are retained negative outcomes, not passing qualification;
  the earlier passing application's tree and `main.py` match the later candidate.
- Six broader workspace journeys produced the same four passes/two failures on
  preceding `dev` and the candidate control: 40px controls fail the older 44px
  assertion, and the older `Next requirement` region selector is absent. The
  legacy events fixture also lacks the current `snapshot` guard keyword and
  targets removed controls. These negative results remain recorded.
- Every acceptance project verified removal of containers, networks, private
  volumes, images and listeners. Browser process groups and the long-run process
  group were verified absent after completion. The open-PR worktree remains.

[Production and baseline-comparison evidence](../reports/2026-10-27-active-context/acceptance-summary.json),
[Overview capture](../reports/2026-10-27-active-context/overview.png) and
[Operator capture](../reports/2026-10-27-active-context/operator.png) preserve
the rendered controls. Physical dish/display hardware, an integrated eight-hour
whole-stack soak, alternate motion/failure workloads and production disk
performance remain unmeasured in this lane; #390's final gate stays open.

### Risk and rollback

External changes are accepted on the documented reconciliation cadence. A source
failure suppresses the old binding while preserving global recording.
Reconciliation still holds the existing gate while inventorying retained files;
large mutation/reconciliation bursts can contend with other admitted work.
Reverting the cache/owner/tick changes restores the original resolver. Saved
mission formats and public response models need no migration.
