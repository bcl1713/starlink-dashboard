# Mission-leg simulation speed controls

**Issue:** [262](https://github.com/bcl1713/starlink-dashboard/issues/262)

**Status:** Written spec approved by the user on 2026-10-05, including hiding
network telemetry panels. The plan and Native execution were subsequently
approved; implementation and acceptance are in progress.

**Base:** `origin/dev` at `d0666918f54666687a5a713f77e68b23214cc8d6`. Work
proceeds in `.worktrees/262-simulation-speed` on `feat/262-simulation-speed`;
PRs target `dev`.

## Intent and approved decisions

Operators need to demonstrate, test, and review a complete simulated mission leg
without waiting for its normal elapsed duration. They can select either a fixed
real-time multiplier or a desired elapsed runtime before starting the leg.

The user approved these decisions:

- An explicitly paced run starts immediately at planned departure, honoring the
  leg's departure adjustment. A target of 120 seconds covers the flight itself.
- One backend-owned simulation clock drives route movement, mission events, and
  mission timing/ETA displays. Planned aircraft speeds retain their meaning.
- Every required event is processed in order, including events crossed between
  published updates. Completion leaves the aircraft at the final waypoint in the
  normal post-arrival state.
- Real acquisition time remains the authority for telemetry freshness.
- Explicit pacing requires valid timed-leg data. Omitting pacing preserves the
  existing activation and simulation behavior.
- Controls offer multiplier and target-runtime modes, preview their effects, and
  show confirmed run state in Missions and Overview.
- The initial supported multiplier range is 0.1× through 1000×, inclusive.
  Target runtime must be at least one second and derive a supported multiplier.
- Pacing belongs to one run. Deactivation cancels it; restart requires starting
  a new run. Mid-run speed changes and pause/resume are deferred.
- During a running paced simulation, Overview hides latency, upload, download,
  packet-loss, and obstruction cards plus their network-status header. A compact
  simulation-status panel replaces them. Normal panels return after completion
  or cancellation.

Explicit pacing includes a selected 1× run. Ordinary activation and live
operation keep their current behavior.

## Current implementation and alternatives

`app/mission/routes_v2.py` owns global leg activation and failure compensation.
`SimulationCoordinator` and `PositionSimulator` advance distance using wall-time
deltas; flight-state and ETA services separately read wall time. Completion can
loop, and `KMLRouteFollower` wraps progress exactly equal to one back to zero.
Timeline generation supplies adjusted/effective routes, timed positions, sorted
events, transport states, and POIs. Startup clears persisted active-leg flags.

1. **Shared clock, selected:** preserves speed, event, and mission-time
   semantics.
2. **Multiply speed:** distorts aircraft speed, ETAs, and events.
3. **Increase update frequency:** adds work while leaving clock inconsistency.

## Run inputs and preview

Add **Simulate leg…** beside the existing **Activate** action in Mission detail.
Show it only when the service confirms simulation mode. While mode is loading,
unknown, or unavailable, paced start is disabled with explanatory feedback.
Ordinary Activate keeps its existing request and behavior.

The dialog has one mode selector:

- **Multiplier:** presets 1×, 2×, and 10× plus a custom numeric value; initial
  value is 1×.
- **Target runtime:** numeric elapsed seconds; initial value is 120.

Only the selected input participates in submission. Display the planned flight
duration, effective multiplier, expected real elapsed runtime, planned departure
and arrival, and the fact that replay starts immediately. Label simulated and
real durations explicitly. Retain the draft and show inline errors after failed
validation or activation. Support keyboard submission, focus management, dialog
description, and accessible field errors.

The backend supplies authoritative preview data from the same effective route
and event schedule used at start. A preview does not activate a route, write
mission flags, modify clocks, or reset handoff state. On start, validate the
current plan again. If it changed since the preview, return a conflict and
require a refreshed preview rather than starting a different run silently.

## Timing and validation

Let `D` be the valid flight duration in simulated seconds, `M` the multiplier,
and `R` the requested elapsed runtime in real seconds:

```text
multiplier mode:    expected real runtime = D / M
target-runtime mode: effective multiplier = D / R
simulation time = planned departure + min(D, monotonic elapsed × M)
```

For a 1200-second leg, 10× and a target runtime of 120 seconds are equivalent.
Rates below 1× deliberately slow the replay.

Use the leg's effective planned route and mission window, with adjusted
departure applied once. Include a feasible selected manual-route splice when it
is already part of the generated plan. Do not replay the base route while
displaying events from a different derived route. Validate finite coordinates,
usable route geometry, positive duration, timezone-normalized timestamps, and
ordered usable timing anchors. Missing timing, contradictory or decreasing
anchors, invalid geometry, or an unavailable effective plan prevent paced start
with a clear explanation. Do not infer a flight duration from random speed.

Inputs form a closed, mutually exclusive schema: multiplier mode carries only
its multiplier; target-runtime mode carries only its runtime. Reject unknown
modes/fields, both values together, booleans, malformed numeric inputs, NaN,
infinity, zero, negatives, out-of-range multipliers, and runtimes below one
second. Derived values must be finite and satisfy the multiplier range. Do not
round before validating or silently clamp a requested value. Round only labels;
retain the effective precision for the run.

Return field-specific validation failures before changing mission, route,
flight, or run state. Attempts to apply pacing in live mode are rejected by the
backend, regardless of whether the caller bypassed the UI. Existing bodyless
activation remains supported.

## Backend ownership and public boundaries

One runtime owner per application process maintains the immutable accepted plan,
monotonic start, run identity, mode, effective rate, event cursor, and published
snapshot. It shares the existing coordinator lifecycle. Polling endpoints read
snapshots; browser count never creates additional replay producers.

Extend the existing activation request with an optional simulation-run object.
Introduce a read-only preview operation for a selected leg and a read-only run
status operation. The implementation plan will specify exact wire types and
endpoint names within the existing mission/simulation API conventions. Their
required semantics are:

- Preview returns normalized pacing, valid mission window and duration,
  supported limits, and an opaque identity for the effective plan.
- Paced activation carries that preview identity and validates it against the
  current plan. The success response includes the confirmed run snapshot.
- Status includes runtime incarnation, monotonically increasing revision, run
  identity, mission/leg identity, selected mode and requested value, effective
  multiplier, flight duration, target/expected real runtime, simulation time,
  real snapshot time, progress, phase, processed-event count, and any error.
- Status distinguishes idle, running, completed, cancelled, and failed. It
  exposes the most recent terminal run until another activation or restart.
- Validation uses 422, unavailable startup/runtime uses 503, and incompatible
  mode or changed-plan conflicts use 409. Preserve existing not-found behavior.

Prepare and validate the replay before activation side effects. Install it only
when the existing activation transaction succeeds. Extend compensation to
restore the prior run, route, and flight state if downstream installation fails;
a failed start must not leave a half-active replay. Serialize activation,
cancellation, switching, and snapshot publication with the existing global
active-leg lifecycle boundary without holding a synchronous lock across
asynchronous network work.

## Movement, events, and final arrival

For paced runs, advance position through the effective timed route at simulation
time. Use planned timing anchors and the timeline's interpolation semantics; use
its documented duration-based interpolation where intermediate anchors are
absent. Aircraft speed is distance per simulated second. GPS-derived speed
calculations therefore use simulated intervals while observation timestamps stay
real. At explicit timed segments, preserve their planned speeds.

At each update, consume every unprocessed canonical event up to the target
simulation time, ordered by timestamp and the existing deterministic tie order.
Process departure-boundary events once at start and arrival-boundary events once
at completion. Preserve the timeline rules for simultaneous transport changes,
transition buffers, AAR windows, outages, and generated POIs. Expose canonical
events from timeline preparation rather than reconstructing an incomplete event
list from the final segment labels. Process work is bounded by the accepted
schedule and advances its cursor; it does not repeat all previous events per
poll or retain an ever-growing log.

Event processing and active-X handoff state belong to the run generation.
Repeated reads cannot commit or replay events, and restarting the same leg
clears that run's previous handoff commitments. When accelerated progress
crosses multiple transitions, commit each in order even if no intermediate
browser frame exists.

Clamp final simulation time to planned arrival, publish progress exactly 100%,
and sample the final coordinate without modulo wrapping. Apply final events,
record simulated arrival, and enter POST_ARRIVAL exactly once. Keep the
completed leg active for review and hold the final position until cancellation
or another activation. Explicit paced replay is one traversal regardless of the
ordinary simulator's loop/reverse setting.

## Two time domains and consumer integration

Preserve real UTC acquisition/observation timestamps for telemetry, history
storage, source-age tests, status freshness, HTTP snapshots, and error
detection. Do not replace Prometheus timestamps with planned mission dates. A
failed update cannot stamp retained telemetry as freshly acquired.

Carry simulation time separately in run context. Paced flight phase, time since
departure, planned/estimated event arrival times, ETA durations, countdowns,
urgency thresholds, and mission-related clock displays use that context. ETAs
remain simulated seconds; real completion estimates are separately labeled in
the simulation-status panel. Any backend or frontend operation that compares a
planned timestamp with “now” must use the appropriate domain explicitly.
Continue validating position freshness against real time before presenting
current location-dependent information.

The four Overview timezone clocks show simulation time during the running replay
and label it as simulated. Their locations/timezones stay configured as before.
On completion they return to real operational time; terminal mission arrival and
elapsed-flight values remain tied to the completed simulated flight.

Frontend clock interpolation uses a confirmed backend sample plus local
monotonic elapsed time and effective multiplier, capped at planned arrival. It
never declares completion before the backend confirms it. If the accepted sample
is older than ten real seconds or refresh fails, retain the confirmed
mode/layout, mark status stale, and stop extrapolating; do not invent progress.
Resume from a fresh confirmed snapshot. Clock corrections cannot reverse a
running replay or dispatch events twice.

Retain the shared Overview history request because it also feeds aircraft trail
data. Hiding network graphs does not disable that trail or create extra polling.
Mission time and real history timestamps are labeled according to their domains.
ADS-B remains an independent real-world source; its observation ages keep real
time. Network metric generation/storage and communication-link presentation
retain their current contracts; this request hides panels in Overview.

## Status presentation and panel visibility

Missions and Overview consume confirmed backend run state. Visible consumers
refresh shared run status once per second with foreground/network-recovery
catch-up. Two independent visible windows converge within one polling interval
plus response/rendering time; browser acceptance permits three seconds on the
controlled host. Browser/OS suspension catches up on resume. Do not duplicate
queries for individual controls, graphs, or status fields.

During `running`, unmount the entire five-card metric rail and its network
header. Replace it with a compact panel showing selected pacing mode, effective
rate, simulated progress, expected real completion, and clearly labeled
simulated time. Preserve globe/camera intent, follow selection, route/trail,
mission POIs, events, satellite presentation, and timing panels. Avoid reserving
empty graph slots or restarting the Canvas when visibility changes. Check
desktop, responsive, and native-fullscreen layouts.

Return the ordinary metric rail when completed/cancelled/failed/idle is
confirmed. Retain a compact terminal result separately so the final run is still
reviewable. A stale status request must not cause a running layout to flicker
back to graphs. Reject obsolete responses by incarnation, run identity, and
revision; a delayed old response cannot re-hide graphs after a newer terminal
result. Handle a new service incarnation by confirming current state rather than
comparing unrelated revision numbers.

## Lifecycle and runtime accuracy

Successful activation of another leg or the ordinary path replaces the prior
paced run. Failed activation retains it. Deactivation, owning leg/mission
deletion, service shutdown, and switching away from simulation release its
resources. Reject edits that would alter a running replay's effective plan with
a conflict instructing the operator to stop and restart; do not mix two plan
generations. After a terminal run, normal editing is allowed and cannot resume
it.

Run settings and event cursors are ephemeral. Service restart uses the existing
startup reconciliation and reports idle; it never automatically replays
persisted active flags. Retain at most one current/terminal run snapshot per
runtime owner. History retention continues to obey existing bounds. Clean up
replay timers and tasks without affecting independent telemetry or ADS-B
services.

Use monotonic real elapsed time rather than accumulated sleep intervals. Healthy
paced updates publish at least once per real second; deadline-aware scheduling
must publish final completion without adding an intentional whole update period.
Do not multiply acquisition or browser refresh frequency by the multiplier. The
controlled 120-second run must publish final completion within one real second
of its deadline after successful activation. Record actual timing.

Scheduler delay or overload can make publication late even though simulated time
is clamped correctly. Process all crossed events before reporting completed,
show/report actual elapsed completion and lateness, and never claim the runtime
target was achieved when it was missed. Processing errors terminate the run as
failed with safe feedback and last confirmed context; they cannot silently skip
events or mark a partially processed leg completed. Acceptance must demonstrate
the claimed supported limits on the representative host; failing that evidence
requires revisiting the limits before claiming readiness.

## Verification and documentation

The required
[acceptance contract](2026-10-05-mission-leg-simulation-speed-acceptance.md)
defines deterministic tests, real 120-second browser acceptance, cross-window
panel visibility/restoration, production-path evidence, and documentation.
Review it together with this design. This delivery runs documentation checks; it
claims no implemented product behavior or product acceptance.

## Review gates and exclusions

Review and approve this written spec before invoking the implementation-planning
workflow. Review the resulting plan and select its execution method before
product code or product dependency setup begins.

Deferred: mid-run speed changes, pause/resume, persisted/resumed runs, simulated
network realism, live telemetry acceleration, ordinary simulation completion
redesign, changed telemetry/history acquisition semantics, provider contact,
production deployment, automatic merge, and unrelated Overview maintenance.
