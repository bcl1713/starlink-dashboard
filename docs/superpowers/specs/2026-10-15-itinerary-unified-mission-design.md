# Automatic itinerary import into ordinary missions

Status: Design and implementation plan approved by the owner on 2026-10-15.
Native execution was selected.

## Outcome and agreed requirements

Upload an itinerary PDF and its KMLs together and receive an ordinary mission
with editable legs, routes, timing, AR windows and generated X-band planning.
The operator reviews the result through the same pages used for manual missions.
Routine import processing happens automatically. Only unresolved evidence
requires correction. New missions remain inactive until normal activation.

All configured X-band satellites are permitted for planning. Do not ask for
access confirmation or maintain a second import-specific satellite selection.
The optimizer uses the existing geometry, elevation and handover constraints;
catalog membership does not guarantee coverage at every route position.

KML timestamps govern route timing, including seconds. PDF timing normally has
minute precision. Approximate timing must not prevent an otherwise clear match.
AR timing uses offsets from itinerary takeoff and landing applied to the KML
timeline. Preserve original source values separately from effective values.

An operator can shift takeoff, replace routes and edit transports through normal
mission controls. Uploading a revised PDF and optional replacement KMLs prepares
a new revision of the same mission, retaining its ID and operator-visible name.
Previous revisions remain available. Manual edits survive where compatible.

This design supersedes the separate itinerary review/publication workflow for
ordinary use. It preserves the existing planning calculations and resource
lifecycle requirements rather than discarding those contracts.

## Current implementation and causes of friction

- `CreateFromItinerary.tsx` exposes extraction, source correction and route
  attachment as successive stages before mission review.
- `MissionDetailPage.tsx` branches on `metadata.itinerary_planning`, presents
  separate source/proposal/publication sections, and excludes installed
  itinerary legs from the ordinary leg cards.
- `LegDetailPage.tsx` redirects expected or installed itinerary legs into
  `PlanningLegReview`, bypassing the ordinary editor.
- `planning/intake.py:candidates` compares the complete departure/arrival tuple
  for equality. Harmless PDF minute versus KML second differences become errors.
- `planning/match.py` matches source clock times, with same-minute matching for
  minute precision; it does not implement the agreed endpoint-offset policy.
- `planning/legacy.py` reconciles ordinary edits through a separate draft and
  publication lifecycle and rejects some ordinary transport changes.
- `planning/canonical.py`, exposed through `inputs.py:draft_to_mission_leg`,
  already projects planning results into normal mission legs. Revision history,
  immutable sources and transactional publication also have reusable machinery.

## Approach and alternatives

Recommended: use import as a producer of ordinary mission data. Keep import
sources, associations and revisions as supporting records, with one
authoritative editable mission. Both manual and imported legs use the normal
read/write, timeline, activation and export paths.

Automating the existing planning screens alone would retain two editing models.
Discarding provenance after conversion would simplify creation but make revised
PDFs overwrite manual edits without a reliable baseline. Neither meets the full
workflow requirement.

## Operator flow

1. Choose Create from itinerary and upload one PDF and multiple KMLs in one
   form. Allow the extracted name to be edited, without requiring re-entry.
2. Start one resumable import operation. Show plain progress: reading documents,
   matching routes, building plans, preparing mission. No generate/apply/publish
   sequence is required.
3. Automatically accept uniquely supported matches, resolve AR occurrences,
   generate satellite choices and handovers, and compute normal timelines.
4. If evidence is insufficient, show only the affected leg or field and its
   proposed correction. Retain uploads and completed work across reload/retry.
5. On success, open the normal mission page with its ordinary leg cards. Show
   generated coverage gaps and other planning warnings there. Editing, route
   upload, takeoff adjustment, activation and exports work normally.

Do not create plausible-looking complete legs from missing required evidence. An
interrupted import remains a recoverable import operation, not a second
operator-facing mission type. Do not activate any generated leg automatically.

## Route association and timing

Build a global one-to-one assignment between itinerary leg occurrences and KMLs.
Use normalized airport identifiers, endpoint evidence, ordered leg occurrences,
flight dates, duration and timing shifts. File order and names are hints, not
authoritative identities. Repeated airport pairs must remain distinct.

For matching only, compare UTC minute values. Endpoint differences within one
minute are equivalent evidence and require no discrepancy acknowledgment. Larger
differences are eligible for automatic matching when independent evidence
identifies a unique assignment, including consistent departure/arrival shifts
with compatible duration. Time proximity alone must not choose between repeated
routes. Do not introduce a wider universal time cutoff as the only decision
rule.

Store the accepted association and evidence so reload does not rerun a different
match. Resolve dates and midnight crossings explicitly; never match only the
clock portion across dates. Incomplete, ambiguous or contradictory source dates
require correction. Preserve existing explicit source units and UTC semantics.

Effective departure, arrival and route waypoint times come from the KML and
retain seconds. A later ordinary takeoff shift changes the effective route
baseline without modifying immutable source timestamps. If KML timing is absent,
the importer must expose that exception rather than pretend PDF times were KML
evidence. Existing parser-supported timing derivation remains labeled as such.

## AR association

For each itinerary AR row derive candidate effective bounds:

```text
entry = KML departure + (PDF AR entry - PDF departure)
exit  = KML arrival   - (PDF arrival - PDF AR exit)
```

Example: PDF departure 10:00 and entry 11:30, with KML departure 10:00:42,
produce an entry candidate of 11:30:42. Keep PDF minute precision in provenance;
the resulting seconds reflect the KML baseline, not extra PDF precision.

Use these bounds plus track identity, waypoint role and ordered route occurrence
to associate the AR. Accept a unique named/role occurrence within one minute
without operator confirmation. Larger timing differences require consistent
track/occurrence evidence; nearest-time matching alone is insufficient. Repeated
track names and loops must be distinguished by route order and effective time.

Where no explicit boundary waypoint exists, retain the existing timed-segment
interpolation capability at the derived bound, with its derivation recorded.
Never substitute an arbitrary nearest named waypoint. Exact eligible KML
boundary occurrences take precedence over interpolated candidates. If multiple
ordered pairs remain plausible, ask only for that AR association.

Validate entry before exit, both inside the flight, and route-occurrence order.
Do not clamp or silently stretch invalid intervals. Different flight durations
may alter the derived AR duration; validate the result and retain both offsets.
AR display and all exports use the same resolved windows.

## One authoritative mission and ordinary editing

Published data uses the existing Mission, MissionLeg and TransportConfig
contracts. Import provenance must not route the UI to a different editor or
require planning access confirmation. Both creation paths share normal editing
and timeline preparation. Reuse the optimizer as an optional generation service.

Record subsequent manual changes against their source baseline for later
revision reconciliation. Saving an edit must not silently rerun the optimizer
and replace chosen satellites or handovers. Normal edit validation still
applies. Takeoff shifts reuse existing ordinary route-relative timing behavior;
fixed UTC overrides retain their explicit semantics. Source bindings and derived
artifacts must be invalidated or recomputed consistently after edits.

Ordinary route replacement works for either origin. Preserve compatible
settings, remap route-bound ARs/handovers only with reliable occurrence
evidence, and show unresolved affected fields in the same editor. Active-route
replacement retains the existing deactivation requirement. An old route hash
cannot validate an anchor on the replacement route.

## Revised itinerary and manual edits

Provide Update from itinerary on the normal mission page. Upload a replacement
PDF and any changed KMLs together. Reuse unchanged routes only when their source
identity and new leg association are still valid. New or changed route evidence
is processed with the same automatic matching rules as creation.

Prepare the revision without changing the current mission. Match legs by stable
source evidence and ordered occurrence; preserve IDs for surviving legs. Preview
added/removed legs, timing/AR changes, route replacements and changed plans.
Keep the mission name unless the operator explicitly changes it.

Use a three-way merge: last accepted imported baseline, current ordinary
mission, and newly generated source revision. Preserve manual-only changes;
accept source- only changes. When both change the same value differently,
request a field-level choice. Even an unchanged manual value requires correction
if it references a removed route occurrence or a satellite no longer in the
configured catalog. Recompute affected plans without altering unrelated legs.

Apply the prepared revision only after explicit review. Store an immutable
previous revision and commit mission/legs/routes/timelines/provenance
atomically. Reject a stale preview if the mission, satellite configuration or
relevant source generation changes. Updating an active mission must not replace
active leg data; require deactivation of affected active legs before commit. No
implicit activation. Revision history must survive package export/import with
its source relationships.

## Existing itinerary missions

Provide a versioned, idempotent conversion into the ordinary editing model.
Preserve mission and installed-leg IDs, names, routes, activation state, saved
transport choices, timelines, source documents and revision history. Do not
regenerate accepted plans during conversion.

Preserve unfinished expected legs as resumable import work. Already installed
legs remain ordinarily editable even when another leg has unresolved import
work. Archive the old manifest for provenance; prevent its former draft from
later overwriting ordinary edits. Apply conversion transactionally with recovery
on failure, including legacy package import. No destructive deletion of sources.

## Execution, compatibility and resource ownership

Use a server-owned import operation with persisted stage/status, idempotent
retries, cancellation and reload recovery. Reuse existing bounded parsing and
planning workers, upload validation, immutable source storage and transaction
journals. Do not orchestrate correctness through a chain of browser-only clicks.
Keep the existing 16-file and 40 MiB route-batch caps and 10 MiB PDF cap unless
a separately measured requirement changes them. Report those limits before
upload.

Capture ordinary mission edits and revision commits through the same concurrency
gate. Existing API clients must not be allowed to bypass revision checks or edit
a different copy of the mission. Preserve canonical timeline/export semantics,
package relationships and renderer cache invalidation after changed inputs.

Every operation has an overall wall-clock deadline and termination grace period,
bounded admission and stage work, and owned temporary paths/processes. Cancel or
timeout must reap workers and remove only owned temporary resources. Preserve
uploaded evidence needed for resumable work under the existing source lifecycle.
No shared runtime configuration or credentials are changed by this work.

## Acceptance and verification

Use wholly invented PDF/KML fixtures in Git and public artifacts. Existing
private inputs may be used only within their original authorization and remain
private. Do not publish operational routes, timestamps or screenshots.

- Happy path: upload PDF and KMLs once, no intermediate confirmation clicks,
  open a complete inactive ordinary mission with generated satellite planning.
- Timing: minute/second differences; adjacent minute within tolerance; common
  larger schedule shifts; different durations; midnight; shuffled file order;
  repeated airport pairs; contradictory dates; missing timing.
- ARs: endpoint offsets, retained seconds/precision, repeated tracks, loops,
  missing named exits, interpolation, ambiguity and invalid derived windows.
- Ordinary behavior: edit takeoff, transports and ARs; replace KML; activate and
  deactivate; reload; preview/save/recompute; CSV/PDF/ZIP round-trip agreement.
- Revisions: unchanged routes, whole replacement, additions/removals, same name
  and stable mission ID, preserved history, manual-edit merges/conflicts, active
  leg protection and concurrent edits invalidating a prepared revision.
- Conversion: current installed itinerary missions and unfinished imports,
  idempotent migration, rollback/restart recovery and legacy package import.
- Failure lifecycle: cancellation, worker timeout, reload/retry, duplicate
  submit, late responses, no leaked processes or task
  containers/volumes/listeners.
- Required repository static/backend/frontend checks, independent code review,
  and exact-candidate production Docker/Nginx browser journeys on
  desktop/mobile. Compare manual and imported missions through the same editor
  and API paths.

## Review boundary

This scope covers automatic import, ordinary mission parity, source revision
updates and existing-mission conversion. It adds no weather, operational data
collection, new altitude inference or communications-model changes. Review this
written design before producing the implementation plan and choosing execution.
