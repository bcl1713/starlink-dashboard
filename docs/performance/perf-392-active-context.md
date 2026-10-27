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

Measured results and retained evidence will be added after verification.
