# PR323 operator workflow and customer export repair

## Intent, scope, and delivery

Resolve issues [324](https://github.com/bcl1713/starlink-dashboard/issues/324),
[325](https://github.com/bcl1713/starlink-dashboard/issues/325), and
[326](https://github.com/bcl1713/starlink-dashboard/issues/326) on the existing
[PR323](https://github.com/bcl1713/starlink-dashboard/pull/323). The user
selected that delivery on 2026-10-13. Use the existing isolated
`feat/itinerary-xband-planning` worktree; keep the primary checkout on `dev`.
The inspected starting head is `66577537e6bb8d13308fcfa718cb3175ae7d8a99`.

The outcome is an operator journey that accepts the supplied itinerary and
routes, preserves explicit executable-plan approval, and produces useful
customer maps without making the API unresponsive. This document is a proposed
design for review, not implementation or acceptance evidence. It supplements the
existing
[itinerary planning design](2026-10-09-itinerary-xband-planning-design.md) and
its
[policy/resource contracts](2026-10-09-itinerary-xband-planning-contracts.md).

Private source documents, route coordinates, mission identifiers, screenshots,
and exports stay in private evidence storage. Repository regressions use
sanitized examples that preserve the relevant timing and occurrence
relationships. PDF byte-size reduction and unrelated OpenAPI/link-check defects
are outside these three issues.

## Findings and approaches

Source inspection confirms the following behaviors at the inspected head:

- `CreateFromItinerary` creates a draft before individual route attachment. Its
  AR controls and extraction errors share the initial intake screen.
- `usePlanningLegWorkflow.accept` can generate an initial proposal after route
  acceptance without completing mandatory AR confirmation. Separate draft saves
  and local captured revisions complicate subsequent preview/publication.
- `PlanningStore.save_draft` marks every proposal reference stale, including
  references for other legs. `ProposalService.status` also compares a proposal
  against the mission revision, which changes when another leg is saved or an
  approved leg is published. An older proposal and an outdated approved plan are
  different conditions that the current labels conflate.
- `SlideCoordinator.reconcile` holds the global activation lock through capture,
  input normalization, fingerprinting, and queue writes. Cancellation checks
  invoke full reconciliation, and idle reconciliation repeatedly hashes renderer
  assets. The async background telemetry loop calls synchronous metric/ETA work.
- `await_prepared` can wait 600 seconds inside export preparation.
  `OwnedZipResponse` supplies a binary stream directly to `StreamingResponse`,
  causing line-based binary iteration.
- `build_map_input` requires increasing per-point times, exact flight bounds,
  and fixed route/marker capacity. It collapses several distinct failures into
  one generic warning. The retained real export confirms unavailable maps for
  legs 1 and 3. Their exact failing predicates remain to be reproduced; neither
  repeated coordinates nor networking is an established root cause.

Three approaches were considered. Small isolated fixes to labels, chunks, and
thread dispatch would give quick improvements but leave the intake/publication
contract and cold-export wait unresolved. A replacement planning/export system
would enlarge the migration and ownership risks. The recommended approach is
targeted changes to the existing planning store, journal, preparation cache, and
UI, with explicit batch transactions and preparation state.

## Operator contract: issue 324

### Intake and source review

Provide one resumable itinerary workspace with stages for source attachment,
source review, planning, and final review. Accept an itinerary PDF and a batch
of KMLs before route-dependent confirmation. Reuse immutable staging and source
ownership. An internal resumable draft may be persisted during intake, but the
operator does not have to click a misleading-error Save action to reach upload.

Suggest per-leg KML matches using airports, source timing, and existing mapping
evidence. Automatically suggest only unique matches. Ambiguous, unmatched,
duplicate, or replacement attachments require visible per-leg resolution before
acceptance; filename similarity alone cannot accept a binding. Show all source
timing discrepancies together, retaining individual acknowledgment identities.

Separate pending dependencies from invalid data. Missing route-dependent AR
matches are pending at attachment stage; malformed UTC values, contradictory
data, and ambiguous source evidence remain visible and correctable. After the
attachment stage, unresolved dependencies block the relevant planning action.

Use flight level as the visible default for unlabelled itinerary AR altitudes,
as requested by the user on 2026-10-13. Label the normal field AR altitude (FL)
and display values such as FL200. Standard imports require no separate unit
selection or repeated acknowledgment of that default. The operator's ordinary
AR/source review covers the displayed values and their interpretation.

Honor explicit source unit labels before the import default. Keep feet/meters
available under an advanced import setting with per-row overrides for unusual
sources. One import-wide override applies only to eligible unlabelled rows;
explicit source units and existing row overrides remain intact. Retain the raw
source value, selected units, and their provenance: source-declared, import
default, or operator override. Do not reinterpret previously saved/reviewed rows
when the default changes. Missing altitude, conflicting source labels, or
unusable values still require correction; assigning units does not confirm an AR
interval or invent a missing height.

During AR windows, the accepted AR altitude overrides the route height in the
X-band look-angle model. Flight level conversion uses FL times 30.48 meters as
an approximate pressure-altitude height; disclose that assumption once in the
review and retain it in calculation/export provenance. Feet and meters are
alternative input units, not separate geometric/pressure-altitude models. Keep
KML route altitudes in meters and aircraft status altitudes in feet under their
existing contracts; normalize calculation heights to meters.

Bound extraction to the actual AR table region and recognize page furniture
using layout/context evidence. Retain positive malformed-row controls, including
unreadable row labels with populated track/timing columns. Do not ignore all
nonnumeric rows, footer-like text, or incomplete tables indiscriminately.

Retain the mission-scope satellite selection/access confirmation already
inherited by legs. Invalidate access only for affected changes to the permitted
selection or access assumptions. Catalog position and geometric visibility
cannot establish service permission. Preserve the reported negative control:
unchanged defaults do not add a new confirmation per leg.

### Planning, persistence, and publication

The first optimization is an explicit Generate plans action after prerequisite
AR/unit/timing/access review. Do not optimize implicitly during route upload.
Show per-leg progress and permit retry of failed legs without rerunning valid
unchanged results. Subsequent optimization after changed inputs is Re-optimize.
Proposal comparison and application remain explicit decisions; applying selected
proposals durably saves draft progress without another Save draft prerequisite.

Use one mission mutation controller to serialize the browser's own accepted
writes and update its revision from each committed result. Cancel or discard
obsolete preview responses using captured input identities. Preserve local work
when a genuine external change rejects a stale write; show recovery choices
instead of silently retrying or overwriting another operator. Preview requests
do not increment persisted revisions.

Track freshness by the affected leg's effective inputs and environment. Keep the
mission revision as the concurrency gate for writes. An unchanged leg's
proposal/review is not semantically stale merely because another leg changed. An
applied proposal becomes historical/applied; approved-plan currency comes from
its reviewed inputs and environment, not the revision of that old proposal.
Changed routes, effective ARs, locks, satellite assumptions, or environment
still invalidate the affected computation and approval.

Present a consolidated final review with AR confirmations/exclusions, no-AR
decisions, satellite plans, outages/gaps, and meaningful exceptions for every
selected leg. Existing unchanged approvals retain their identities. An explicit
Publish reviewed plans action authorizes executable installation; autosave never
publishes or activates a leg.

Prepare all selected legs outside commit locks against one captured revision and
per-leg input/environment identities. Recheck every selected binding and
approval, then commit all executable legs, timelines, generated POI scopes, and
review records in one journaled transaction. If any leg fails validation or a
concurrent change occurs, install none of the selected batch and preserve drafts
and prior installed legs. Successful publication leaves installed legs inactive.
Repeated submission is idempotent for the same inputs. Retain individual-leg
review for existing/partial missions.

Show loading/reconciling state while persisted counts are unresolved. A pending
refresh is not evidence that a mission contains zero legs. Save, reload, and
package round-trip must agree on reviewed/current/changed state.

## Preparation and transport contract: issue 325

### Responsiveness and consistent capture

Audit async request/background boundaries that reach synchronous guarded storage
or substantial validation. Dispatch bounded blocking work away from the ASGI
event loop; run only one telemetry update at a time, preserve update order, and
own/drain its worker at shutdown. Moving work to a thread does not by itself
prove responsiveness or solve CPU contention.

Split preparation into raw capture, normalization/computation, and conditional
publication. Capture immutable committed bytes and dependency identities under
the documented lock order. Release the global gate before full planning-model
validation, source normalization, per-leg fingerprint computation, or renderer
work. Perform substantial Python CPU work in an owned bounded process if the
concurrency probe demonstrates event-loop starvation through the GIL.

Before queueing/publishing, recheck the captured input generation/dependency
identity under a short gate. A superseded capture cannot overwrite newer work.
All relevant mutable dependencies must participate, including route/source
versions, POIs, satellite catalog/positions, coverage, constraints, planning
metadata, and fallback timelines. Existing atomic source ownership, journal
recovery, and snapshot consistency guarantees remain mandatory.

Use saved changes and dirty generations to wake preparation. Retain bounded
reconciliation for external dependency changes and crash recovery. Cancellation
polling checks stop/supersession tokens without repeatedly parsing every
mission. Hash immutable deployed renderer assets once per runtime; development
changes must explicitly invalidate that memoization. Cache reads for progress
return state/timing metadata without copying PDF/snapshot BLOBs.

### Preparation workflow and ZIP delivery

Make cold preparation an explicit asynchronous operation rather than keeping a
download request open for minutes. Expose queued, preparing, ready, superseded,
failed, and cancelled export state, plus available per-leg stages and warnings.
Report measured queue/render times or named stages; do not fabricate
percentages.

An export preparation request returns promptly with an owned export identifier
and captured revision/fingerprint. The UI polls cancellable status requests and
enables download only when the complete package is ready. Saves supersede
pending exports, which the UI identifies before preparing the current version.
An already ready download remains an immutable, consistently labeled snapshot.
Failure is recoverable with an explicit retry. Cancelling an export stops its
assembly/wait and releases its resources; shared slide preparation still serving
the mission is not killed by a single browser disconnect.

Retain the renderer's current 120-second per-job wall-clock bound and enforce a
600-second aggregate preparation bound from the export request. A deadline
reports failure/warnings and preserves mission data; it cannot silently reset
itself after every save or retry. A warm ready export avoids heavy recapture on
the request path. Legacy download clients receive an explicit not-ready response
and preparation reference when cold, rather than an invisible 600-second wait.
Document this API behavior change.

Stream ZIP output in fixed byte blocks, initially 64 KiB, with exact-byte hash
verification and a bounded final block. Preserve the package schema and
PDF/evidence pairing. Use owned temporary files or spooling for package assembly
so package size does not require several full in-memory ZIP copies. Start with
an 8 MiB spool threshold and a 30-minute ready-package lifetime. The status
response includes the expiry time; expired downloads require preparation again.
Reap expired artifacts, and verify cleanup on success, failure, disconnect,
cancellation, and shutdown. The existing source/history graph must still be
exported in full.

## Customer map contract: issue 326

First reproduce the failing predicates for each omitted leg using immutable real
inputs and the retained reviewed state. Record privately the effective route
point count, ordered occurrence identity, time deltas, UTC bounds, source minute
precision, and window-anchor relationships. Preserve source dates and
operational values; public regressions use sanitized equivalents.

Choose the smallest repair supported by that reproduction. Valid source-minute
times must be interpreted through the canonical accepted timing/occurrence
contract rather than an invented second-level ordering. Repeated coordinates
cannot erase a distinct occurrence or move an AR/swap to the nearest position.
Exact coincident joins may be normalized only in the display scene when they
retain the same legitimate position/time. If density is the actual cause, scene
simplification must preserve window anchors, route shape, and canonical timing
while enforcing the renderer's capacity. Do not just increase limits.

Return specific diagnostic codes for unavailable timing, non-increasing or
ambiguous segments, mismatched bounds, coordinate errors, and density limits.
Run the same inexpensive scene-eligibility check before final review, using the
captured canonical effective route and coordination windows. An unsupported
input receives an actionable per-leg limitation before publication; any residual
limitation requires Brian's acceptance. A generic missing-map warning after
successful publication is insufficient.

The supported real legs must produce actual route/window overlays using local
renderer assets offline and online. Assert map-stage metadata and inspect
rendered pixels for all three legs; successful PDF creation alone is not map
acceptance. The canonical route/timeline/AR relationships, timezone handling,
exact window boundaries, and installed evaluations remain unchanged by display
normalization.

## Verification and completion gates

Implement and verify preparation/transport isolation first, map diagnosis and
repair second, then the streamlined operator flow. Finish with an integrated run
on the resulting exact PR head. Add meaningful boundary regressions before each
behavior change and run the existing affected suites.

- Exercise real-server health, proxied status, mission reads, and planning while
  queued/cold preparation, warm export, and invalidating saves occur. On the
  named Forge configuration, each normal-work probe has a two-second deadline.
  Retain every timing, failure, and sample count; report event-loop lag and lock
  stages.
- Measure preparation queue/render stages and export headers/body completion
  separately. Compare cold/warm offline/online controls with comparable initial
  state. Preserve baseline differences; do not infer Internet causation.
- Verify exact ZIP hashes, package round-trip, bounded stream chunks/memory,
  disconnect/cancellation ownership, recovery, and process/resource reaping.
- Exercise batch publication atomicity, delayed previews, concurrent edits,
  idempotent retry, mission-scope access inheritance, affected-leg invalidation,
  and post-reload current status.
- Replay the same private real-input journey through production Docker/Nginx and
  the rendered browser, offline and online. Preserve screenshots, action-count
  categories, timings, map-stage evidence, and persistent readback. Target at
  most 20 explicit actions under the original counting convention. If necessary
  safety decisions exceed that target, enumerate them and obtain Brian's
  approval.
- Retain Brian's review of the rendered streamlined journey before closing 324.
  All required CI and applicable exact-head production/browser gates remain
  required before merge; previous-head evidence does not certify a new head.

Use task-specific runtime projects and disposable volumes, record ownership
before launch, wrap checks with explicit wall-clock limits and kill grace, and
install exit/signal cleanup handlers. Verify owned processes, listeners,
containers, networks, and disposable volumes are gone after checks. Preserve
private source artifacts, acceptance evidence, and the open-PR worktree.

The user authorized updates to PR323, not a merge or deployment. Push reviewed
work to its existing feature branch and update its description with the actual
resulting behavior and qualified evidence. Do not close any issue solely on
unit/synthetic evidence or weaken approval, snapshot, or ownership contracts.
