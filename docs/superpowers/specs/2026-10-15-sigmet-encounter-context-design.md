# SIGMET encounter timing context

Status: Timing-only written spec approved by the user on 2026-10-15.
Implementation planning is authorized; product implementation awaits plan
review.

Base: `origin/dev` at `b373324d`. Branch: `feat/sigmet-encounter-context`.

## Intent and selected approach

Help operators interpret a geographic route intersection by showing when the
planned aircraft passes through it. The user confirmed that a planned-altitude
source will never be available. The supplied Leg 3 Rev 6 KML has 236 coordinate
tuples containing longitude and latitude only, ground-clamped display geometry,
and waypoint UTC times. Planned-altitude comparison is excluded permanently from
this feature, rather than treated as a future prerequisite.

Use an informational-first increment: enrich existing SIGMET attention without
changing notice eligibility, attention order, map filtering, acknowledgement, or
manual selection. Continue displaying the bulletin's reported vertical bounds
for operator interpretation. An automatic relevance filter would require
additional policy for uncertain plans, future-valid reports and partial
coverage. A browser-only calculation would duplicate route selection and could
diverge across displays. Select a backend calculation joined to the existing
shared route-SIGMET response.

Success means both screens show the same plan-bound evidence, missing data is
explicit, and timing edits update that evidence without reopening acknowledged
notices. No combined risk score or safe-route assertion.

## Existing integration points

- `services/aviation_weather/route_context.py` selects and copies the ordinary
  route or the selected running/completed simulation's effective route.
- `models/route.py` contains ordered route points, expected arrival times and
  heights documented as MSL meters.
- `models/route_sigmets.py` contains geographic segment fractions and bounded
  entry/exit spans, plus strict versioned snapshots.
- `services/aviation_weather/route_runtime.py` joins cached geometry to current
  weather eligibility and persistent notice state.
- Planning and timeline preparation can convert a flight level to meters for
  geometry. That conversion does not establish geometric MSL altitude.
- `models/aviation_weather.py` and normalization retain explicit vertical
  references, units and possibly missing bounds.

## Route evidence and calculation identity

Capture immutable timing evidence from the same selected route and effective
artifacts as its geometry under existing state-lock conventions. Do not resolve
a similarly named route or nearest waypoint. Preserve ordered point indices,
source kind, source revision and simulation runtime/run identity.

Keep the existing geographic context key and notice identity unchanged. Add a
separate encounter revision digest over ordered relevant timing values and their
provenance, applicable planning revision and calculation method version. Rename,
poll time and weather retrieval time do not affect it. Do not include encounter
data in the bulletin semantic digest.

Revalidate geometry identity and encounter revision before publishing a result.
A read must contain one coherent capture. Superseded reads must not overwrite a
newer plan revision; use an authoritative per-service observation generation,
not lexical digest ordering. Copy under locks, calculate after release, then
recheck. Never hold planning or route locks during geometry work or awaits.

## Timing calculation

Use the effective selected route point's expected UTC times. Use no live speed,
current aircraft position, observed departure adjustment, replay clock or total
route-duration estimate to fill missing values. Existing effective-plan timing
adjustments are accepted only where they are already materialized in the
selected route. Label all results Planned, including historical dates.

For a segment with finite geometry fractions f and ordered, timezone-aware
endpoint times t0 < t1, interpolate t(f) = t0 + f \* (t1 - t0). This is a
constant planned speed within that segment. Retain source precision when known;
round displayed times to minutes and expose exact UTC in details. Do not imply
that rounding changes interval comparisons. Missing, reversed or naive times
make that span's timing unknown. Do not extrapolate across gaps. Equal endpoint
times are unknown even for a boundary touch.

Compare each closed encounter interval [entry, exit] with the bulletin's
half-open validity [valid_from, valid_to). A boundary touch overlaps when
valid_from <= touch < valid_to. Otherwise overlap requires exit >= valid_from
and entry < valid_to. Validity at encounter time is separate from eligibility at
actual UTC: future reports still do not raise new attention in this increment.

Aggregate across spans: any overlap yields overlap; all known nonoverlaps yield
no-overlap; otherwise unknown. Preserve partial/unknown counts even when a known
span overlaps. A displayed overall entry/exit range must be labeled a summary
when multiple disjoint intervals exist; details list each interval.

## Altitude scope and current-aircraft telemetry

There is no planned-altitude source and none will be added or inferred. Do not
calculate vertical overlap, introduce an altitude status, or use absent altitude
to block timing calculations or suppress attention. Retain existing display of
SIGMET vertical bounds, including unknown references and missing bounds.

Current aircraft altitude during an active mission describes the aircraft now,
not its altitude at a future intersection. It must not filter route advisories
or be substituted into planned encounter calculations. A separate future live
situational-awareness feature could show a clearly labeled current-altitude
comparison with source/reference/freshness checks, but it is outside this
change. No current-altitude wiring, new telemetry polling or altitude editor is
included.

## Response and presentation

Introduce `route-sigmets-v2` and migrate the backend and all tracked consumers
atomically; do not add fields to v1's strict contract. Preserve existing
acknowledgement/selection request and confirmation contracts. Document the read
schema change and update fixtures and acceptance tooling.

Each geographic entry gains bounded encounter evidence aligned one-for-one with
its existing spans: entry/exit UTC or null and time status/reason. The snapshot
includes encounter revision, method version and plan/source provenance. Unknown
fields must have machine-readable reasons: missing-timing, invalid-timing,
ambiguous-association, and unavailable-plan as applicable. Calculated fields
must be finite, typed and validated. No raw documents or duplicate polygons.

Selected-only reports have no manufactured spans: present Encounter unavailable
— no route intersection. Mixed geographic/manual entries use geographic spans.

Overview keeps its three-card paging and matching highlights. Replace the
unevaluated footer with concise timing text, for example:

- Planned passage 14:20–14:32 UTC · Time overlap
- Planned passage unavailable · Missing waypoint times

Include the date when passage is not on the current UTC date or crosses
midnight. Use explicit No time overlap for known nonmatches, with neutral
styling; retain the notice. Never use green safe/clear styling.

Configuration expanded details show per-span times, bulletin validity, reported
vertical bounds/references, source provenance, method assumptions and unknown
reasons. Both views retain feed freshness, simulation labeling and coverage
limitations. No extra per-poll announcements, camera changes or new controls.

## Caching, failures and bounds

Reuse cached geographic spans on timing edits. Cache encounter results by
geographic result identity, encounter revision and bulletin validity; maintain a
bounded cache alongside existing route service ownership. Preserve existing
point/advisory/span/result caps and weather allocation limits. Count added
evidence against the 8 MiB result cap and browser admission budgets. An
over-limit response is explicitly incomplete/unavailable, never truncated.

Encounter calculation is bounded linear work over admitted points and spans.
Keep it outside the API event loop using existing owned execution patterns;
reuse shutdown/cancellation handling and introduce no independent poller.
Operational encounter failure leaves geographic notices usable with an explicit
unknown/unavailable result where safely representable. Existing feed expiry,
local expiration and cancellation behavior stay authoritative.

## Verification and acceptance

Use independent numeric fixtures for fractional timing, midnight/date changes,
validity start/end and zero-length touch boundaries, disjoint spans, missing and
reversed times, mixed known/unknown spans and historical simulation dates.

Verify that the supplied altitude-free route can produce timing evidence and
that no height, flight-level inference or live-altitude dependency is
introduced. Keep reported SIGMET vertical bounds visible. Include an explicit
regression that changing current aircraft altitude cannot hide, acknowledge or
alter timing classification of a geographic notice.

Exercise plan edits with unchanged geometry: evidence updates, geometry cache
reuse, acknowledgement stability, two-screen convergence, out-of-order reads,
route changes, simulation run changes and unavailable plan evidence. Validate
strict v2 decoding, output bounds and explicit selected-only unknowns.

Run focused backend/frontend checks, applicable static/build checks and an
isolated exact-commit production Nginx/browser journey with independent
contexts. Capture desktop/mobile cards and expanded details, partial evidence
and no nonmatch suppression. Label synthetic inputs separately from dated
real-source replay. These checks do not establish current upstream availability
or target workstation WebGL performance.

Record task resource ownership before starting checks. Bound all runners with
wall-clock termination and cleanup handlers. Stop and verify owned processes,
listeners, Compose containers/networks and disposable volumes after checks;
preserve evidence and the open-PR worktree only.

## Next stage

After user review of this written spec, use Superpowers writing-plans to name
the exact evidence adapters, locks, migrations, numerical fixtures, commands and
resource ledger. The implementation plan needs its own review and execution
choice before product changes. This spec does not implement the feature.
