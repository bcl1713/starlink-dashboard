# Operator airborne restriction timing — PR #379 review revision

The October 18 review correction supersedes acceptance of planned UTC for
in-flight transport alerts. The requested integration extends existing timing
wiring within #368; it does not change transport modeling or mission exports.

## Existing calculations and narrow adapter

`TimelineArtifacts` already contains the effective route and its
`RouteTemporalProjector`. Map merged capability/continuity interval boundaries
back through `distance_for_timestamp` and `sample_at_distance`. Store the
resulting route segment, coordinates and progress alongside the immutable
planned model. Do not offset a mission clock or predict different geographic
restrictions.

Preflight uses the existing planned UTC. Once in flight, capture current fresh
position/speed with the existing input admission gate. Use the same unique route
projection and `ETACalculator._calculate_route_aware_eta_estimated` used by #348
for each future boundary. This preserves the existing current-segment speed
blending and remaining-route semantics, including off-route projection. Passed
boundaries classify an interval as active/ended at capture time; they do not
claim an observed outage or invent a historical crossing time.

Both the displayed event UTC and five-minute notification threshold consume the
refreshed boundary times. Label these as **Live route ETA** and keep original
planned UTC in source details. Unknown/ambiguous progress or unavailable live
speed yields unknown timing and an explicit source reason; no planned UTC is
silently substituted. Current useful estimates need no extra confidence gate.
The actual #348 live PoP producer remains authoritative for airborne PoP
windows; remove the redundant planned PoP windows from the airborne model
projection.

## Identity, history and admission

Cache the expensive planned transport calculation by existing immutable input
revision. Refresh boundary ETAs on each capture without rebuilding that model.
Bind publication and acknowledgment validation to the exact position/speed
sample as well as route/config/catalog/leg/lifecycle input identity. Revalidate
under the existing repository gate through ledger commit. Passage of backend
clock time alone is not a new input revision; stale sample evidence remains
rejected.

Restriction identity includes route geometry, cause, ordered occurrence and
boundary geometry. ETA changes, including large departure delays, retain the
same occurrence and optional acknowledgment. A new route or changed geographic
restriction replaces the occurrence; existing severity escalation rules remain.
No durable event is added for each ETA refresh. Preserve the accepted immutable
history, shared acknowledgment uniqueness and prohibition on resurrecting
retired notifications. Scheduled calls/follow-ups keep their existing
rescheduling rules.

## Acceptance

Use deterministic UTC backend tests with real route/catalog/coverage
preparation: late and early departure, varied speed, deviation/rejoin, Ka
boundary, source change races, acknowledgment across a large ETA move/restart,
and passed windows. Production Docker/Nginx browsers at desktop/mobile sizes
must demonstrate an originally overdue planned X boundary becoming a future live
estimate after a 45-minute delay; changing speed moves its displayed UTC and
five-minute cue threshold together. Verify one actual oscillator attempt,
movement out of the window, route revision and explicit unavailable live timing.
Keep existing multiclient, restart/backup, partial input and #348/#349
acceptance checks.
