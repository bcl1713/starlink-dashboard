# Route-linked SIGMETs for a passive dashboard

**Status:** Written spec and subsequent implementation plan approved by the user
on 2026-10-15. Subagent-driven implementation and
[production acceptance](../../reports/2026-10-15-route-linked-sigmets.md) are
complete. Whole-branch review and PR submission remain pending; design approval
is separate from the measured acceptance scope.

**Parent:**
[Issue 290](https://github.com/bcl1713/starlink-dashboard/issues/290). Inspected
base: `origin/dev` at `1c0834a1e45685a4dd3592de252db2bea9e08a0d`. Record the
actual base again when planning implementation. This document supersedes the
earlier interactive route-shortlist concept discussed in chat.

## Intended outcome and scope

An operator leaves Overview on a view-only display and uses Configuration on
another screen. With SIGMETs enabled, the operator can limit polygons to those
intersecting the selected route. Newly relevant bulletins automatically produce
passive details and a highlighted polygon on Overview. Configuration owns
review, acknowledgement and redisplay. No dashboard action is required.

The user approved intersecting-only filtering, automatic notices, highlighting,
and clearing from Configuration. The agreed clearing behavior acknowledges the
notice: remove its card and attention highlight while retaining the normal
still-valid polygon. Acknowledgement synchronizes across screens and survives
refresh. The limits, identity rules and API below were accepted with spec
approval.

Reuse the international SIGMET feed, normalization, raw bulletins, finite
freshness, cancellation lineage and native renderer. No new provider, corridor
buffer, automatic rerouting, risk score, sound, dedicated turbulence/icing
layer, wind calculation or ETA-valid weather prediction is included. Existing
SIGMET reports can describe turbulence/icing without claiming complete coverage.

## Existing boundaries and architecture choice

`AviationSettingsCard.tsx` and `useAviationSettings.ts` already provide
confirmed, installation-wide settings with five-second reads.
`aviation_weather/settings.py` provides locked atomic persistence.
`AviationWeatherService` owns shared feed acquisition and admitted snapshots.
`relations.py` resolves cancellation targets. `AviationLayer.tsx` and
`AviationDetails.tsx` currently own browser-local report selection and
highlighting; they cannot synchronize acknowledgement.

Use a small backend route-advisory service plus REST polling. It resolves route
identity, evaluates normalized geometry, and joins results to persistent
acknowledgements. Both screens consume the same authoritative result. Reuse
atomic file/lock conventions, with a separate notice-state revision so clearing
a notice cannot restart weather acquisition or invalidate GFS demand.

Browser-only matching with local dismissal would be simpler but would diverge
across browsers and restarts. A pushed event stream would add connection and
replay machinery without improving the required five-second control cadence.
Neither alternative is selected.

## Configuration and passive presentation

Under **Weather → Aviation weather → Hazards**, retain the SIGMET toggle and add
**Intersecting route only**, backed by `sigmet_intersecting_only: false` in the
existing settings contract. Preserve the filter while SIGMETs are disabled;
disable its control until SIGMETs are enabled. Legacy files default to false.
Filter changes save atomically and use the existing confirmed-revision behavior.

When SIGMETs are enabled, route notices operate in both filter modes. All mode
shows ordinary eligible polygons; intersecting-only shows geographic matches.
The filter changes presentation, not feed scope, acquisition or acknowledgement.
With no usable route, intersecting-only shows no polygons and a
route-unavailable status; never silently fall back to all polygons or claim zero
hazards.

Configuration lists matching bulletins in route order, showing pending or
acknowledged state. Each entry offers **Clear advisory** when pending and **Show
again** when acknowledged. Expandable details preserve the original bulletin,
issuer/FIR, provider and canonical series, issuance, validity in UTC,
revision/amendment/cancellation information, vertical bounds/reference, source,
retrieval time and feed limitations. Unlocated reports remain separately
reviewable as **Route intersection unknown**.

Overview automatically presents a nonmodal **Route advisory** card with a stable
bulletin label, phenomenon/severity, affected segment or resolved waypoint span,
reported vertical bounds, issuer/FIR and validity in UTC. Its footer states
**Geographic intersection · Altitude and passage-time match not evaluated**.
Unknown values are written explicitly. Use segment numbers when waypoint
association is ambiguous; do not guess the nearest named waypoint.

Show at most three pending cards, newest attention first, with route order then
stable identity breaking ties. Persist attention order: first detection assigns
it and an explicit Show again advances it; polling never changes it. Display the
total pending count and any additional count as passive text; Configuration
exposes the full list. Highlight the corresponding three polygons and affected
route portions with a steady outline and matching labels; other matching
polygons keep their normal appearance. No flashing, automatic camera movement,
focus change, clickable notice, close button, carousel or dashboard
acknowledgement control is added.

Move SIGMET-specific click/tap/keyboard report inspection to Configuration; the
existing general report chooser on Overview must not expose a second local
SIGMET dismissal path. METAR/TAF inspection is outside this change. Keep globe
navigation, existing unrelated controls, fullscreen behavior and camera intent.
Cards must fit desktop/fullscreen/mobile layouts without obscuring core status;
use concise summaries and full details on Configuration, with polite accessible
announcements only for new or changed notices.

## Route and intersection semantics

Use the entire route selected for Overview, rather than only its remaining
portion or every mission leg. Resolve the same authoritative geometry as
`OverviewPage.tsx`: the selected running/completed simulation's effective route
when its runtime/run identity is current, otherwise the ordinary active route.
Route-line visibility and camera position do not change this selection. Label
the route in Configuration and Overview status. Simulation geometry is
explicitly labeled; advisory eligibility still uses actual UTC, never replay
time.

The backend route adapter must share these selection rules and expose a context
key covering source kind, ordinary route identity or simulation runtime/run, and
a canonical digest of ordered coordinates. Renaming, time ticking, aircraft
progress and unrelated settings do not create new route contexts. Geometry edits
and new simulation runs do. Never trust a client-supplied route as the
authority. Copy the route under its existing state lock, release the lock before
geometry work, and revalidate identity before publishing.

Match the great-circle arcs between successive route coordinates against the
normalized geographic polygon areas, retaining holes and antimeridian splits.
Crossing or touching a boundary counts; a route entirely inside an area counts;
a route wholly inside a hole does not. Evaluate segments, not just route
vertices or bounding boxes. Return ordered entry/exit positions and segment
indices, including multiple disjoint spans. Deduplicate split polygon parts and
provider geometry variants of one canonical bulletin into one notice, preserving
their source details. Zero-length segments may be skipped; malformed or
ambiguous antipodal arcs produce an explicit incomplete result.

The implementation plan must name the numerical method, geographic error
tolerance and independent reference fixtures before coding. Approximation
ambiguity becomes unknown rather than a definitive nonintersection. Work or
output limits never silently discard a crossing or reduce the evaluated route.

Include only currently eligible, noncancelled bulletins using the existing
half-open validity interval `[valid_from, valid_to)` and original expiry. Future
validity is shown in Configuration but raises no current notice. Reevaluate at
validity boundaries even when feed identity is unchanged. Altitude and route
passage-time matching are explicitly not evaluated in this increment, even when
some route fields exist. Do not substitute aircraft altitude or the GFS selected
flight level, or compare MSL/AGL heights directly with pressure flight levels.

## Notice identity and lifecycle

Identify each notice by route context, canonical bulletin identity and a
semantic revision digest. Bulletin identity includes issuer/FIR, canonical
series and original validity interval, preserving the existing independent
series-reuse and cancellation rules. For unresolved identity, use a bounded
normalized-content fallback and label the uncertainty; never merge by series
alone. The digest covers issuance/revision, phenomenon/severity, validity,
vertical evidence, canonical geometry, amendment relation and normalized raw
bulletin text. Exclude retrieval time, feed instance, feature order and derived
freshness. Normalize whitespace and equivalent geometry ordering for stability.

| Event                                       | Required behavior                                                                                                                   |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Enable SIGMETs or first load                | Eligible intersections become pending unless already acknowledged for this route and revision.                                      |
| Clear advisory                              | Persist acknowledged state, then remove its card and attention highlight on every connected display. Keep its ordinary polygon.     |
| Show again                                  | Persist pending state and advance attention order for that exact notice so it is shown again.                                       |
| Same bulletin refreshed                     | Preserve acknowledgement and attention order, including across restart.                                                             |
| Substantive revision                        | Retire a superseded notice when lineage establishes replacement; raise the new revision as pending. Unknown lineage stays explicit. |
| Route context changes                       | Remove old cards/highlights immediately; evaluate the new route with its own acknowledgement scope.                                 |
| Expiry, cancellation or loss of eligibility | Remove the notice and attention highlight; cancellation/expiry also remove normal shading.                                          |
| Disable SIGMETs                             | Remove cards and all SIGMET drawings; preserve unexpired acknowledgement records.                                                   |
| Temporary unavailable feed or route         | Show unavailable state; do not infer resolution, erase acknowledgements or label an empty result safe.                              |

A stale but originally eligible snapshot may retain notices, labeled stale,
until the existing expiry. Failed refreshes never renew deadlines. A new
successful snapshot follows existing publication semantics; absence means no
report returned, not cancellation or clear weather. Keep the permanent
unknown/partial-coverage note, including when no polygons match. Expired notices
must disappear locally even while disconnected.

## Shared state and API

Add `GET /api/aviation-weather/v1/route-sigmets` with `Cache-Control: no-store`.
Return a strict versioned snapshot with generated UTC, settings revision,
notice-state revision, route context/name/source, admitted SIGMET instance,
original deadlines, coverage/omission metadata, evaluation status and reason,
matching entries, unresolved entries and explicit truncation/incomplete flags.
Each entry references the exact normalized feature identities and includes its
notice key, revision digest, attention order, acknowledgement and bounded
intersection spans. Reports and geometry reuse admitted immutable products; the
response must not duplicate raw bulletin bodies or full polygons.

The read reuses the existing shared acquisition lease when demand is needed; it
must not start a second poller or retain a lease without visible readers.
Configuration can be the sole visible reader. Do not add an independent weather
daemon. Cache geometry results by route context and SIGMET content, separating
time eligibility and acknowledgement so a clear or clock tick cannot rerun
geometry unnecessarily.

Add `PUT /api/aviation-weather/v1/route-sigmets/acknowledgement` accepting only
the context key, notice key, semantic digest and desired `acknowledged` boolean.
Validate against the current eligible notice under the notice-state lock;
unknown/stale identities return 409 and trigger a read. Repeated identical
writes are idempotent. Serialize different writes and return the confirmed state
revision. A late clear for an old revision cannot acknowledge its replacement.
Store failure returns a sanitized error and never reports success. No clear-all
or wildcard mutation is included.

Keep acknowledgement storage separate from source artifacts and persist it
atomically with a process-safe lock. Cap it at eight route contexts and 4,000
records, with a 2 MiB serialized limit; remove records at bulletin expiry and
evict least-recently-used inactive contexts when needed. Never evict a live
current-context acknowledgement to admit another record; reject the write with
explicit Configuration feedback instead. A revisited evicted context starts
pending, as documented. Missing storage starts empty; corrupt storage reports
unavailable without overwriting it or claiming a notice is acknowledged.

Both screens use one shared query owner per mounted query client with a
five-second visible, online poll; an unfocused but visible screen keeps polling.
Stop on hidden, offline or unmount, cancel obsolete requests and catch up
immediately on return. Use monotonically increasing confirmed revisions; bind
reports, geometry and notices to the same route and feed identities before
drawing. While mismatched or refreshing a changed route, suppress its cards and
attention highlights rather than showing an old match on a new line. In
intersecting-only mode, also suppress SIGMET polygons until a compatible
evaluation arrives; never temporarily show the unfiltered collection. Reject
obsolete read completions even when acknowledgement revisions tie but feed
generations differ. Successful writes update the local cache immediately; other
displays converge within one poll plus response and rendering time.
Suspended/offline displays catch up on resumption.

## Resource ownership and failure isolation

Geometry runs outside the API event loop, with one cancellable, reaped
task-owned worker and bounded queue, following the existing disposable-worker
pattern. Proposed caps: 20,000 source route points, 100,000 combined polygon
vertices, 500 advisories, 100,000 calculated spans and 8 MiB result data, under
a five-second wall limit with one-second termination grace. Over-limit, timeout
or uncertain results become incomplete/unavailable, never a successful
zero-match result. Revalidate source identity on completion; superseded work
cannot publish.

No extra source polling or unbounded history is permitted. Account for matching
results, scratch data and all highlights inside existing shared optional-weather
browser limits: 16 MiB encoded, 32 MiB decoded/geometry, 16 MiB GPU and four
operations. Reserve old-plus-candidate peaks. Reuse base geometry where
possible; admission failure leaves an explicit highlight-unavailable state while
retaining eligible textual notices. Release drawings, buffers, requests and
workers on supersession, disable, expiry, hidden/offline and unmount.
Notice-service failure must leave settings, unrelated weather, telemetry and the
core dashboard usable.

## Verification and handoff

Implementation acceptance must cover:

1. Independent geometry fixtures for thin crossings with both endpoints outside,
   containment, boundary touch, holes, disjoint spans, antimeridian, high
   latitude, degenerate routes, ambiguous arcs and resource limits;
   route/polygon rendering agrees with the reported spans within the declared
   tolerance.
2. Two independent browser contexts through production Nginx: Configuration
   controls filtering, first activation, new notices, Clear and Show again on an
   already mounted view-only Overview without reload, camera or focus change.
   Healthy controlled propagation must finish within eight seconds of save.
3. Stable refresh/restart acknowledgement; duplicate geometry variants; genuine
   amendments; reused series; cancellation of the correct original interval;
   validity boundaries without refresh; concurrent and stale writes; failed
   persistence; bounded retention; and confirmed-state recovery after errors.
4. Active-route edits/switches/deactivation and simulation start/completion/new
   run; stale or late responses; no wrong-route highlight; actual UTC weather
   despite a different replay clock; and explicit unevaluated altitude/time.
5. Partial/empty/truncated/unlocated data, stale/expired feeds, source failure,
   worker timeout, failed requests, hidden/offline recovery and no clear-route
   claim. Repeated source failures cannot extend validity or reopen cleared
   notices.
6. Desktop, fullscreen and mobile evidence with three notices plus overflow,
   readable telemetry/route/markers, steady identifiable highlights, keyboard
   controls on Configuration, and no SIGMET action controls on Overview. Verify
   shared allocation peaks, cancellation and cleanup alongside existing radar,
   METAR/TAF and GFS regressions.

Use focused backend/frontend tests, appropriate static/build checks, and
isolated exact-SHA production/browser acceptance. Label synthetic controls
separately from pinned real-source evidence. Record scoped runtime ownership
before checks, use wall limits and cleanup handlers, and verify all task
processes, listeners, containers, networks and disposable volumes are gone
afterwards. Existing GFS real-source and workstation-performance gaps in issue
290 remain separately unverified unless independently closed; they are not
SIGMET acceptance evidence.

After written-spec approval, prepare a separate implementation plan naming the
route adapter and locking, geometry method and tolerance, strict schemas,
persistence migration, query/renderer ownership, layout fixtures, commands and
resource ledger. Update operator/API documentation during implementation. This
spec-only change neither implements the feature nor closes issue 290.
