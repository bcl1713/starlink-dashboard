# Itinerary import and X band planning

**Status:** Draft for user review. The workflow was agreed in conversation; this
written spec and its detailed defaults await review. Implementation is not
authorized by this document alone.

**Scope:** Flight planner itinerary PDF, per-leg KML upload, refueling review,
proposed X-band satellite assignments, manual edits, and itinerary revisions.

## Purpose and success criteria

Mission planners should upload an itinerary, attach each leg's KML, and review
automatically identified air-refueling (AR) windows and proposed X-band swaps.
Success means less manual entry, fewer predicted X-band unavailable minutes,
clear explanations of remaining gaps, and reliable preservation of operator
choices. Starshield is preferred whenever usable; X-band yields in conflict
areas unless another permitted satellite avoids the conflict. Proposals are
planning estimates under the configured constraints.

Use itinerary-first creation with independent leg review. Existing manual
mission creation and mission ZIP import remain available.

## User workflow

1. Choose **Create from itinerary** and upload the PDF. Extract mission
   identity, revision, aircraft, call sign, ordered legs, UTC dates, airports,
   AR windows, and listed altitudes. Show extracted values and warnings for
   correction. Confirm altitude units and the permitted X-band satellites here;
   these settings can be changed during leg review.
2. Confirm the itinerary and create the mission with expected leg cards. Each
   card shows departure, arrival, dates, AR count, and **Upload KML**. The
   mission can be left and resumed before any or all routes have been uploaded.
3. Upload a KML into the selected card. Validate the primary route's endpoints
   and timing against that expected leg. File order and filename are hints;
   neither assigns the leg. Report discrepancies before accepting the binding.
4. After accepting a usable route, match AR windows and automatically request a
   draft satellite proposal for that leg. Navigate directly to its review page;
   show computation progress there. Other legs need not have routes yet.
5. Review **AR windows** first, then **X-band plan**, using the existing leg map
   and timeline. Correct matches and edit the plan. A proposal based on
   unresolved AR inputs is visibly provisional and cannot be marked reviewed.
6. Choose **Save draft**, **Save reviewed plan**, or **Save reviewed plan and
   upload next leg**. The next upload targets the first expected leg without a
   route; if none remain, return to the mission overview.

The review page also offers **Return to mission** and preserves the existing
unsaved-change protection. Upload, computation, and review do not activate a leg
or send commands to an aircraft or satellite terminal.

```mermaid
flowchart LR
    A[Upload itinerary] --> B[Confirm expected legs]
    B --> C[Upload KML for selected leg]
    C --> D[Match AR and generate draft]
    D --> E[Review AR windows]
    E --> F[Review and edit X-band plan]
    F --> G[Save reviewed plan]
    G --> C
```

## Review state and presentation

| State        | Meaning                                                    | Next action        |
| ------------ | ---------------------------------------------------------- | ------------------ |
| Awaiting KML | Expected leg has no accepted route                         | Upload KML         |
| Needs review | Route attached; AR or satellite plan unreviewed or changed | Review leg         |
| Reviewed     | Both reviews saved against current planning inputs         | Open reviewed plan |

Computation status is separate: idle, calculating, ready, failed, or stale. It
must not replace review state. A failed optimizer leaves the route and draft
available. Legacy legs show **Review status not recorded** until explicitly
reviewed; they are not retroactively labeled reviewed or blocked from their
existing activation workflow. This feature adds no new activation approval gate.

AR rows show track, source page/row, source UTC entry/exit, matched route times
and endpoints, altitude with units, and match status. Map highlighting follows
the actual route span. AR review can confirm, correct, add, or exclude a row;
exclusion requires a note. Leg 2 in the sample explicitly shows no listed ARs.

X-band review shows the initial satellite, ordered swaps, swap locations and UTC
times, degraded intervals, reason codes, and remaining constraints. Show
**X-band outage under Starshield preference**, swap count, longest outage, and
periods with no usable backup transport. Compare the proposal with the current
draft; on the first run use the best permitted constant-satellite plan as the
baseline. A baseline is not installed automatically.

Every proposal identifies its permitted satellites, constraints, timing and
altitude assumptions, model version, and resolution. If constraints prevent
continuous service, show the gaps and their reasons. Review can accept a plan
with modeled gaps after acknowledgment; unresolved input errors block review.
Reviewed save requires confirmation of every AR row (or no ARs) and explicit
acceptance of the current satellite plan, not merely viewing its preview.

## Itinerary extraction and route matching

Initially support text-bearing PDFs in the supplied flight planner format,
including rotated pages. Use the existing pypdf dependency with extraction that
retains rotated text. Retain source page/row and original values alongside
normalized values. Do not rely on visual table order from one extraction mode.
Scan-only, encrypted, unreadable, or unsupported documents produce a specific
error; OCR and arbitrary document templates are outside this first version.

Use UTC columns, full dates, and timezone-aware timestamps. Never substitute
local or home times. Validate increasing leg times, AR start before end, and AR
membership within its leg. A parser must distinguish an empty AR section from an
unrecognized section; the latter needs correction rather than implying none.

Match the selected KML's primary route, excluding alternate-airport branches.
For minute-only itinerary times, a KML timestamp in that same UTC minute is a
candidate. Compare dates, route order, and coordinates as well as names. Merge
duplicate representations at the same time and position; retain distinct route
occurrences. Ambiguous or absent matches require operator selection. Do not
infer an AREX from the last explicitly named AR waypoint.

A valid time inside a timed segment may produce an interpolated route anchor,
clearly labeled for review. Store anchors as route segment/waypoint occurrences
with time, fraction, coordinates, and route identity; names alone are inadequate
for repeated waypoints. Imported ARs use the existing sector-based AAR window
semantics. Do not convert them into Manual AR Tracks, which currently impose an
independent X-band degradation over their projected span.

The itinerary describes the refueling span along the supplied route. It does not
provide a complete published track corridor or tanker trajectory.

## Timing and altitude rules

Preserve original itinerary times for provenance. After matching, bind ARs to
their reviewed route anchors, using the KML's second-level timing. Preserve the
PDF's minute precision; do not describe the difference as a flight delay.
Departure adjustments shift route-bound ARs and swaps by the same delta exactly
once. An explicitly entered fixed UTC override remains fixed and is labeled; an
elapsed-time override follows departure. Timing mode is stored per override.

AR altitude is shown as the source value until its units are confirmed during
itinerary review. Numeric values such as 210 or 230 are not silently treated as
meters. Confirmed flight levels retain their pressure-altitude meaning; if used
as approximate geometric heights, expose that assumption and conversion. Within
an AR span use the confirmed AR height when geometrically usable; otherwise use
valid route height, then the existing documented cruise fallback. Record every
fallback. Optimizer, map, timeline, and exports use the same chosen height
profile.

## Satellite proposal and optimization

Use configured X-band satellite POIs and their validated orbital positions,
through the same resolution path as timeline planning. Never use the default X-1
placeholder as evidence that a satellite is usable. The operator selects the
permitted satellite set before the first run; initially preselect configured
X-band satellites with valid positions and label access as operator-confirmed.
Orbital visibility does not establish terminal compatibility or service access.

The
[required planning contracts](2026-10-09-itinerary-xband-planning-contracts.md)
are part of this spec. They define the Starshield preference policy, exact
outage predicate, common evaluation boundaries, interval conventions, route
ownership, replacement recovery, and package coverage.

For each permitted satellite evaluate the effective timed route using the shared
constraint evaluator. Existing defaults are normal conflict 135–225 degrees, AR
exclusion 315–45 degrees, minimum elevation 10 degrees, and swap degradation of
15 minutes on each side. Read these from shared configuration. Takeoff and
landing safety advisories remain visible but do not alone count as X outages.

Optimize each leg independently with a shortest-path/dynamic-programming search
that accounts for the complete swap buffer and the shared evaluation grid.
Generated swaps have their full buffer within the leg; consecutive generated
buffers may touch but not overlap. Existing manually overlapping swaps remain
editable and are scored by the union of their outage intervals.

Minimize Starshield-preference X outage seconds, then swap count, then stable
satellite ID/time ordering. Report backup gaps using the same operating policy.
Ka/Ku allocation and total communications downtime are not extra objectives.
Canonical validation must reproduce the winning cost exactly; disagreement is a
computation failure, not a proposal to apply. Describe optimality within the
permitted set, constraints, and stated candidate grid. A 30-second computation
deadline returns failure rather than a partial optimum; retry needs no reupload.

Geometry and warnings are predictions from the existing geostationary model.
Live RF interference, airframe/antenna masking, terrain, pitch/roll, tanker
occlusion, link budgets, and guaranteed acquisition time are outside scope.
Route bearing may approximate aircraft heading; label that assumption.

## Manual edits and recalculation

Manual changes update the availability preview without automatically replacing
the edited plan. Operators can change the initial satellite and add, move,
remove, or change swaps. They can lock the initial selection or a swap's
satellite and route/time anchor. Moving a locked item is an explicit edit.

**Re-optimize** generates a separate proposal that honors all locks. Show a
comparison and require **Apply proposal** before replacing unlocked choices.
Applying never clears locks. If no schedule satisfies the locks, identify the
conflicting choices and leave the current draft intact. Unlocking is explicit.

AR, route, altitude, timing, permitted-set, satellite-position, constraint, or
manual-plan changes invalidate affected review state and proposals. Ka/Ku edits
refresh backup-gap metrics and review state. A changed AR does not silently
rerun optimization over manual work. The page offers re-optimization and labels
the existing proposal stale. Upload retries do not overwrite reviewed work.

## Persistence and backend boundaries

Store an itinerary manifest in mission planning metadata with immutable source
revision identity, source filename/hash, extracted values, corrections, expected
leg IDs/order, and links to executable leg IDs. Expected legs, accepted route
bindings, and drafts live in this manifest until the first reviewed save creates
an executable MissionLeg. Do not fabricate route IDs or satellite settings to
satisfy the existing MissionLeg requirements before that save. The leg review
page must support these draft records as well as existing executable legs.

Persist per-leg AR anchors/provenance, current draft, locks, review records, and
proposal identity separately from executable transport settings. **Save draft**
does not publish a proposal as the operational plan. **Save reviewed plan**
atomically installs validated transport settings, reviewed metadata, and derived
timeline/POIs. Ordinary edits of an installed plan clear its review status.

Extend AR and swap resolution to accept occurrence-aware anchors while retaining
legacy name/coordinate inputs. Reuse timeline preparation for previews and
validation; preview/optimization must not publish POIs or change active state.
Keep extraction, matching, optimization, and review persistence in separate
modules outside the already large mission routes and timeline event files.

API operations cover itinerary preview, confirmed creation, accepted leg route
binding, proposal generation/read/apply, draft save, reviewed save, and revision
preview/apply. Exact paths and wire schemas belong in the implementation plan.
Preview responses expose field errors, provenance, assumptions, and input
identity. Mutations require matching persisted revision and planning identity;
conflicts return 409, invalid inputs 422, and unavailable computation 503.

Planning identity includes effective route/timing/altitude, ARs, manual
overlays, permitted satellites and positions, constraints, locks, relevant
outage policy, and algorithm version. Late results cannot replace newer drafts.
Reload can retrieve persisted proposals; retries are idempotent. Include the
persisted Starshield preference policy in planning identity. Reject changes to
active legs until deactivation under the existing global activation/mission
locks.

Preserve source PDFs in mission-owned storage, not temporary upload paths.
Validate PDF uploads with a 10 MiB limit; preserve existing KML limits. Parse
with a 10-second deadline and remove failed staging artifacts. Route bindings
use mission-owned immutable IDs; imports remap collisions without overwriting
another mission's resources. Packages and dependency snapshots include draft,
reviewed, retired, and retained prior-route KMLs as specified in the contracts.
Missing new fields remain backward compatible. Imported reviews require
revalidation against available inputs before showing Reviewed.

## Itinerary revisions and recovery

Uploading a revision first shows a diff of mission fields, legs, AR rows, and
times. Match stable leg IDs using itinerary leg number plus endpoints; ambiguous
reorders/splits require explicit mapping. Apply only after confirmation. Keep
old source revisions for traceability; do not duplicate missions or AR rows.

Preserve routes, corrections, and locks on retained legs. Show source changes
that conflict with manual corrections for resolution. Mark affected legs Needs
review. Added legs await KML; removed legs remain explicitly retired with their
previous work retained. A lower revision needs explicit override; identical
content is a no-op. Validate the complete change set before committing it, and
reject a revision affecting an active leg before any mutation.

Replacement KMLs use the staged recovery contract: retain the previous route and
plan, preserve departure adjustments, and expose unresolved AR/lock anchors for
correction. Do not reuse the legacy destructive replacement behavior unchanged.

## Acceptance and delivery

The supplied package provides five matching examples, all in UTC:

| Leg | Track    | Entry        | Exit         | Route anchors       |
| --- | -------- | ------------ | ------------ | ------------------- |
| 1   | AR106LW  | Oct 25 14:26 | Oct 25 15:23 | ABR → MLS346021     |
| 1   | GRIZZ-W  | Oct 25 19:20 | Oct 25 20:33 | GRIZZ → 57N162W     |
| 1   | TROJAN-W | Oct 26 00:47 | Oct 26 02:08 | 4030N15700E → 35E50 |
| 3   | TITAN-E  | Oct 29 18:18 | Oct 29 19:50 | 35E50 → 43E60       |
| 3   | GRIZZ-E  | Oct 29 22:58 | Oct 30 00:05 | 57N162W → GRIZZ     |

All dates are 2026. Leg 2 has no listed AR. Use sanitized fixtures preserving
these structural cases; do not commit the supplied operational documents.

Acceptance covers rotated PDF extraction; UTC/local separation; midnight and
antimeridian crossings; duplicate waypoint occurrences and alternate branches;
interpolated anchors; malformed files and ambiguous matches; uniform departure
shifts; altitude assumptions; and unavailable configured satellites. Optimizer
tests compare tiny cases with exhaustive enumeration, include swaps whose
buffers erase their benefit, unavoidable gaps, deterministic ties, and locks.
Integration tests cover stale results, atomic reviewed saves, inactive imports,
revision conflicts, retry cleanup, and complete draft/retired package
round-trips. The contracts add policy, exact-boundary, collision, and
replacement tests.

Rendered browser acceptance follows itinerary confirmation through per-leg KML
upload, AR correction, proposal comparison, manual locks, re-optimization,
reviewed save, next-leg upload, reload/resume, and revision reconciliation.
Include keyboard use, accessible errors, mobile review, and failure recovery.
Use isolated projects and bounded runners under the workspace lifecycle rules.

Implementation planning follows approval of both design documents: import and
matching, optimization, revision/package compatibility, and browser acceptance.
