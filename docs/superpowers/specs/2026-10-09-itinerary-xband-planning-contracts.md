# Itinerary planning policy and resource contracts

These contracts are normative parts of the
[itinerary import and X-band planning design](2026-10-09-itinerary-xband-planning-design.md).
They resolve independent-review findings and the user's decision to prefer
Starshield whenever possible. Both documents await design approval.

## Starshield preference and outage cost

Persist a versioned **Prefer Starshield** operating policy in each accepted
planning record. The optimizer may choose X-band satellites and swap points; it
may not turn off usable Starshield to improve its X-band score. Apply the same
policy to proposal scoring, review previews, installed timelines, map warnings,
and customer/package exports. Preserve physical capability separately from
policy-driven operating state and retain reason identities in both.

Starshield is usable when enabled and its modeled Ku capability is available,
before applying any X/Ku transport-choice policy. Existing Ku outages and
overrides determine that capability; an assumed always-on Ku model is disclosed.
Safety-of-flight call advisories alone do not imply RF unavailability.

For the selected X-band satellite, an interval counts as an X-band outage when
any of the following holds:

- A normal-sector X/Ku conflict exists and Starshield is usable. Starshield
  remains selected; X-band is shut down for that interval.
- Elevation or an AR forward-sector exclusion blocks X-band, or an independent
  manual AR overlay blocks it, regardless of Starshield availability.
- The interval falls inside a modeled X-band swap degradation buffer.

If Starshield is disabled or unavailable, a normal-sector concurrency conflict
alone does not block X-band. Other X constraints still apply. Selecting another
permitted satellite may avoid the conflict; swap buffers still contribute to
cost. Do not invent a shutdown where only a historical concurrency advisory is
present without confirmed current constraint inputs.

Cost is the duration of the union of these intervals within the flight, with
overlapping causes counted once. Label it **X-band outage under Starshield
preference** and split reason details into policy shutdown, geometry/AR, and
swaps. This is an operating-plan estimate, not measured physical unavailability.
Takeoff/landing and AR call-safety advice remain separate call restrictions;
they add no outage cost unless an independent blocking condition also holds.

The existing call normalizer can restore X AVAILABLE for pure aft-cone
conflicts. It must not erase the explicit operating-policy shutdown for these
plans. Extend canonical decisions with the policy result, rather than computing
this metric only from legacy normalized x_state or free-text reasons. Under
Prefer Starshield, a conflict-only interval shows Starshield available, X in
policy outage, and the concurrency reason. Backup-gap reporting uses those
effective operating states and the separate call-safety restrictions.

## Shared evaluation boundaries and interval meaning

One shared evaluator owns geometry, raw constraint identities, physical
capability, and policy projection. Optimizer, canonical preview, installed
timeline, map review, and exports use the same route, altitude, configuration,
boundaries, and interval results. Adapting the fixed-minute canonical sampler
and event resolver is required; validating only the winning schedule using the
old sampler is insufficient.

Define candidate swap times C from the departure-relative 60-second grid, route
timing/heading/altitude anchors, AR/overlay/outage/safety boundaries, and every
current draft swap time, whether manual or generated, locked or unlocked.
Include departure and arrival; only eligible interior times can host generated
swaps. Every existing swap retains its exact seconds and buffer edges for
preview/scoring, including manually overlapping swaps.

Define evaluation boundaries B as C plus each candidate's swap-buffer start and
end, clipped to the flight. B is common to all schedules for the same input
identity, independent of the winning schedule. Extra evaluation boundaries do
not become new swap candidates recursively. Display both the candidate cadence
and the fact that exact event boundaries supplement it.

Persist an evaluation context with its seed times, C/B sets, input identity, and
model version. Applying a proposal, saving it, or reloading retains this
context, even if the new schedule omits an unlocked draft swap that seeded C. Do
not shrink B by rebuilding it from only the winning schedule. Structural input
changes or an explicit manual timing edit create a new context and invalidate
old proposals; recompute both the comparison baseline and proposal under that
new context. Persist/export/import the context with the plan.

All intervals are half-open [start, end). AR exclusions apply at AR entry and
cease at AR exit. At swap time the assignment becomes the target satellite; the
buffer is [swap minus buffer, swap plus buffer). End conditions cease before
start conditions and assignments at the same timestamp are applied; evaluate the
resulting state for the interval beginning there. Arrival closes the flight with
no added duration. Reject conflicting locked assignments at one instant.

Sample route position, heading, altitude, and each satellite's geometry at each
left boundary, then hold sampled geometry through the next boundary. This is the
disclosed approximation; no between-boundary crossing is claimed detected. Exact
operational boundaries and their effects are never rounded to a minute.
Reconstruct the same boundary set from the persisted evaluation context after
save or reload; validate it against its input identity before using it.

Score every candidate using these intervals and the outage predicate above.
Reconstruction through canonical preparation must reproduce the same interval
reasons and cost. If it does not, fail calculation with a model-consistency
error and preserve the current draft. Exhaustive tests on small candidate sets
must establish the selected schedule minimizes canonical cost, not merely that
the winner can be serialized.

## Route ownership and replacement recovery

New route versions have opaque mission-owned immutable IDs; uploaded filenames
are display metadata. Maintain references from draft bindings, executable legs,
retired records, and retained prior versions. No import or replacement
overwrites a route file/cache entry in place. Existing routes referenced by
other missions or active legs remain untouched, including legacy
filename-derived IDs.

During package import validate all resource bindings before commit. A collision
with another mission or different content gets a fresh owned ID. Identical
content may reuse an existing immutable version within the same mission only.
Remap executable legs, draft bindings, AR anchors, swap anchors, locks, and
retained history together. Keep content identities separate from storage IDs so
pure ID remapping does not change timing or geometry. Revalidate reviews after
remapping. Guard all affected active references, not only the imported parent.

Replace a KML by staging a new immutable route version and a mapping preview.
Retain the previous KML, AR corrections, locks, departure adjustment and timing
modes, and installed plan until the operator accepts a validated reviewed
replacement. Reapply departure adjustments once to the new source timing and
show the resulting date/time changes; never clear them silently.

Attempt anchor matching using ordered occurrence, timing, and location evidence.
Unmatched ARs/swaps remain visible as unresolved records with their old anchors
and corrections. Do not delete them or silently move locks to the nearest point.
They block reviewed save until explicitly remapped, unlocked/removed, or an AR
is excluded with a note. Cancel or failed staging leaves the installed plan
unchanged; accepted staging saves a Needs review draft without replacing it.

Adapt or bypass the legacy route-replacement path that deletes the previous KML,
clears departure adjustments, and removes AR rows with absent names. Mission
deletion and retirement also respect reference ownership. Retiring a leg
archives it outside activatable executable legs while preserving its work. Only
mission deletion releases its retained owned sources; delete files only after
confirming no remaining references, and never delete another owner's resources.
Failed/abandoned upload staging uses the existing cleanup rules.

## Package and snapshot completeness

Dependency capture and ZIP export enumerate the union of executable routes,
accepted draft routes, retired leg routes, and retained previous route versions.
Do not enumerate only mission.legs. Include all corresponding KML bytes, source
PDF revisions, corrected manifest data, anchors, locks, provenance, and policy.
Preserve logical relationships even when no executable legs have been created.

Import stages and validates this complete graph before committing bindings. A
missing or invalid referenced file fails the new planning package import without
a partial mission/route mutation; legacy packages retain format compatibility
subject to the same collision and ownership protections. An incomplete source
set fails export with actionable errors instead of producing a package that
appears to preserve recoverable work. Successful round-trip resumes unfinished
review and keeps retired work archived.

## Required acceptance cases

- With usable Starshield and a conflict-only X satellite, count the exact policy
  outage while keeping Starshield selected. A different conflict-free satellite
  removes that reason, but swapping incurs its full buffer cost.
- When Starshield is disabled or in a Ku outage, permit otherwise viable X in
  that sector. Elevation/AR blocks and overlaps still count once. Safety advice
  alone contributes no X outage seconds and remains visible in call guidance.
- Use AR boundaries and locked/unlocked swaps at times such as 12:00:30; check
  entry, exit, simultaneous conditions, and both buffer edges. Assert equal
  optimizer/canonical intervals and costs. Remove an unlocked seed swap by
  applying a proposal; verify unchanged C/B and scoring after save/reload and
  package round-trip. A manual timing edit explicitly creates a new context.
- Enumerate all schedules for small candidate sets and compare their canonical
  costs under the same policy, including deterministic ties and manual locks.
- Import a different mission with a colliding filename/route ID, including an
  active existing mission. Its file, cache, bindings, timeline, and locks remain
  unchanged; every imported draft/history anchor follows the remapped ID.
- Replace a route with changed waypoint names and timing. Old AR corrections,
  locks, departure adjustments, KML and installed plan survive; unresolved
  matches require correction. Cancel/failure and retry preserve the old plan.
- Export/import before the first reviewed save, after some legs are reviewed,
  and after route replacement and retirement. Verify every required KML/PDF and
  manifest reference, preserved draft edits, archived status, and policy.
- Delete a mission with drafts/retired history without leaking its owned files
  or removing sources belonging to another mission.
