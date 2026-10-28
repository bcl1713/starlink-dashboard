# Operator saved-record synchronization

Status: approved after incorporating PR #431's baseline/reset clarification.
Implements issue #430 after merged PR #428. Base: `origin/dev`, `f0c1bd49`.

## Intent and constraints

Saved calls, conferences and associated records must converge on already-open
laptop and phone Operator pages addressing the same backend and mission/context.
Preserve the approved Operator layout, tab-local drafts, selection, scrolling,
version checks, explicit conflict review and idempotent retry handling. No
production writes, deployment, shared drafts or push infrastructure are needed.

Target: a successful server save becomes visible on another continuously visible
client within five seconds on a healthy local backend under the acceptance
workload. This is a measured engineering target, not a guarantee for suspended
browsers, arbitrary workloads or unavailable networks.

## Approaches

The approved approach is bounded incremental polling (option 2), as preferred by
the issue and accepted subject to the baseline/reset clarification.

1. Poll the existing infinite records query. Small frontend change, but each
   interval rereads all loaded pages. Polling only its first page misses changes
   to records beyond that page. Replacing pages independently also risks mixing
   snapshot boundaries.
2. Poll a bounded incremental saved-record read through the existing query
   layer. Adds a small backend read contract but avoids repeated full snapshot
   reads, preserves original cursors and provides explicit source identity.
   Recommended.
3. SSE/WebSockets. Requires connection lifecycle and server infrastructure
   without a requirement for instant delivery. Not recommended for this issue.

## Existing behavior

`OperatorWorkspace` reads `workspace-all` through an infinite query without a
refresh interval. `WorkspaceEditor` observes the same query for relationships.
`OperatorWorkspaceProvider` overlays authoritative local-save reads by identity
and record version, then retires them when the snapshot catches up.

The REST list uses immutable revisions at a fixed global high-water sequence
`H`, with records ordered by record ID. Cursors bind store, epoch, filters,
snapshot boundary and read time. The database already indexes revisions by
mission and journal sequence. The timeline and event hooks have separate polling
and subscribe to local query invalidation; these do not refresh saved cards.

## Bounded incremental read

Add a read-only `/api/v2/operator/record-changes` route and matching frontend
service. An initial request supplies mission ID and `after_seq` from a known
snapshot high water; subsequent requests use an opaque cursor. Limit results to
200 records per page. Do not change existing records/history cursor semantics.

Within a consistent database read, capture high water `H` and return the latest
revision at or below `H` of each mission record changed after `after_seq`.
Include removed records. Use deterministic sequence ordering and bind cursor
validation to the lower/upper boundaries, mission, store, epoch and captured
read time. Apply existing read metadata to returned records. Do not read all
history on every poll or return every intermediate version of a repeatedly
edited record.

Return captured source identity with every page: store ID, API epoch, source
mode, simulation run, replay run and operating-context identifiers. Validate
identity before displaying or merging the response. Reject invalid watermarks,
foreign/obsolete cursors and identity mismatches through existing error
patterns. No database migration or mutation behavior change is expected.

## Baseline identity and safe rebaselining

Extend the records list response with captured `source` metadata containing the
requested mission ID and the full runtime health identity, including store,
epoch, mode, simulation namespace, replay and operating context. Capture
metadata under the same runtime binding as the snapshot read. Return it even
when `items` is empty and `H` is zero. Workspace readers validate this metadata
against their intended mission and identity before accepting the page or using
its `H`. A query key or a separate health read alone is not source validation.
Bind workspace continuation cursors to source/context too; preserve the existing
snapshot contents and cursor behavior for other readers.

Retry network failures, timeouts and temporary storage/service unavailability
from the same completed checkpoint. Never advance it after a partial batch.
Invalid watermark/cursor errors and source/epoch/context changes invalidate the
checkpoint: abandon the batch, refresh health/context, and obtain a fresh,
identity-validated first snapshot page before restarting incremental reads. For
an invalid checkpoint in an unchanged identity, replace the old snapshot
pagination generation; never append its old cursors to the new baseline.

Every baseline/reset has a generation. Abort owned requests and ignore late
responses from an obsolete generation, including bootstrap and intermediate
delta pages. Discard incompatible overlays, page cursors and watermarks. On a
source mismatch, quarantine data from the old generation immediately while
health/context catch up. Last-known data may remain visibly stale only in its
original scope; it must not appear as current data for a replacement context.

Resetting saved reads never resets the draft registry. Keep dirty draft input,
original mission/context targets and base versions unchanged. The existing
explicit stale-version/409 reconciliation remains necessary before a stale write
can succeed. Do not rebase or resubmit a write automatically.

## Refresh ownership and merging

One workspace synchronization hook owns the two-second foreground interval. Use
a query key scoped by mission and the existing full Operator identity. Wait for
the first matching records snapshot, then use its `H` as the initial watermark.
Keep delta reads separate from the infinite snapshot query so its loaded pages,
cursors and load-more affordance stay intact.

Drain all pages of a changed batch before advancing the watermark to its `H`.
Keep at most one batch in flight per scope. Use cancellation signals and guard
late completions after mission/context changes. A failed batch can retry from
its last completed watermark without writes or version regression.

Overlay the latest authoritative records from snapshot pages, local confirmed
reads and completed remote batches by record ID and highest record version.
Retain tombstones and prevent a late older snapshot or poll from replacing a
newer version. Expose this merged saved-record view to cards, counts and editor
relationship choices; do not copy it into draft input or alter draft bases.
Retire overlay entries only when an authoritative snapshot contains an equal or
newer version. Scope all retained overlay state to mission and identity.

After a batch containing changes is merged, request one refresh of that scope's
timeline and event projections. Retain their existing refresh behavior for
time-driven changes. Avoid broad records invalidation and invalidation loops.
The acceptance target includes the corresponding saved timeline state.

## Visibility, errors and draft safety

Pause the synchronization interval while hidden. Refresh immediately on becoming
visible, reconnecting or regaining focus; coalesce simultaneous triggers with an
existing in-flight read. Continue bounded attempts while visible so backend
recovery does not depend on a browser online event. Remove listeners and cancel
owned reads on unmount/scope change. Do not promise hidden timer delivery.

Retain last-known saved data after read failures. Reuse the workspace's existing
unavailable/retry presentation to disclose failed synchronization and clear it
after recovery. Do not blank cards or report a successful save from a read.

Incoming versions update saved views while an open draft retains typed values
and its original base version. Existing action rereads and HTTP 409
reconciliation remain authoritative. Do not silently update a draft's expected
version, retry a write, or automatically resubmit user input.

## Validation and cost evidence

Backend tests cover bounded pagination, concurrent writes during a frozen batch,
updates/removal/restoration, cursor and watermark validation, mission/store
isolation and restart/replay context identity. Frontend tests cover version
precedence, stable snapshot cursors, shared relationship views, draft
preservation, hidden/foreground and reconnect behavior, failed reads, teardown
and deduplication. Include empty-baseline identity, identity changing during
bootstrap and during a paginated batch, invalid-checkpoint rebaselining without
endless obsolete retries, late old-generation responses, and recovery while a
dirty draft remains open with its original target/base version.

Run two independent Playwright browser contexts against the same disposable
production-image backend through Nginx, using synthetic simulation data. Keep
both documents visible for foreground measurements. Exercise saves in both
directions, conference establishment/closure, call rescheduling/cancellation and
timeline convergence. Exercise hidden/foreground recovery, offline/online
recovery, backend recovery, stale saves and independent record edits. Cover
pagination and source changes, plus navigation/remount without accumulating
requests. Label simulated browser lifecycle events separately from actual
browser visibility evidence.

Measure server-save completion to other-client rendered state with monotonic
timestamps and a five-second assertion. Record request counts, including
existing context/health/timeline/events traffic, rather than attributing all
traffic to this feature. In steady state, saved-record synchronization adds
approximately 30 small GETs/minute/client and no writes; two visible clients add
approximately 60 GETs/minute. Changed batches add bounded continuation reads and
scoped projection refreshes. Verify idle polling does not reread
snapshot/history pages. Report catch-up workload and latency separately from
idle foreground propagation.

Capture desktop/mobile screenshots and a reproducible walkthrough. Run the
applicable unit, lint, build, CI and exact-commit production/browser checks
before claiming implementation complete. Record all task-owned runners and
temporary resources before starting them, apply wall-clock limits and cleanup
handlers, and verify teardown before handoff. Keep the feature worktree for its
open PR.

## Decisions left to implementation

Choose helper/module names, response model names, the exact SQL query and test
fixture factoring during implementation. If measurement cannot meet five seconds
without changing the agreed scope, report the measured result and proposed bound
before claiming acceptance. This design does not authorize expanding the
Operator redesign or weakening existing conflict handling.
