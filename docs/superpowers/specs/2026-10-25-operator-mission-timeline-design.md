# Persistent operator mission timeline

## Intent and agreed placement

Give the operator a complete running chronology of expected mission events,
including X-band outage and recovery estimates. The user chose to keep it
visible across the operator workspace, including Communications, Transport and
Issues. Before departure it uses scheduled times; during flight it uses the
existing route-aware ETA calculations where applicable.

## Approaches

1. **Persistent panel beside the workspace — selected.** Keeps events visible
   while operating calls and transports. Uses some horizontal space, so rows
   must be compact and event details expandable.
2. **Dedicated Timeline tab.** Gives the chronology more space but hides it
   during other operator tasks. The user chose the persistent approach.

## Proposed behavior

Extend the existing operator awareness column with a clearly titled **Mission
timeline**. Keep reported connected customers and the next customer requirement
available. Show active windows first, followed by a chronological upcoming list
with a clear Now marker. Earlier events are available in a collapsed Past
section in the same panel. The operator can scroll the timeline independently
without losing the workspace navigation or editor. Do not duplicate the existing
large Mission activity feed below Communications on the Now view.

Rows show a concise event name, leg name when relevant, UTC, and a relative time
such as “in 12 min.” Transport windows show both start and expected recovery,
with an active row emphasizing “recovery in …” once the start has passed. Sort
using current estimated times, rather than the original planned schedule. Label
timing **Scheduled**, **Live route ETA**, or **Timing unavailable**. Use dated
UTC when an event is on another day. Expanded details can expose the original
schedule, source freshness and transport explanation.

The timeline includes the existing event families: modeled X, Ka and Starshield
restrictions, customer communications continuity windows, PoP transition
advisories, call preparation and start requirements, and issue follow-ups.
Represent each transport window once with its start and recovery together. Known
mission leg route start/end times may be used as contextual anchors; they must
be labeled scheduled departure/arrival or estimated route arrival, never claimed
as observed takeoff or landing.

For this design, **complete** means the selected mission and its legs, including
known events outside the existing rolling 24-hour alert window. Current flight
ETAs apply only to the active leg. Other legs retain scheduled timing; do not
propagate current-leg delays across later legs without an existing supported
calculation. Show leg-specific unavailable information instead of silently
dropping a leg. Scheduled or elapsed estimates are not observed outage history.

On narrow screens keep a compact Mission timeline summary and direct expand
control available across views. Expanding it reveals the same full chronology
without discarding unsaved work. Desktop displays the panel expanded by default.

## Current implementation and data changes

`OperatorWorkspace` already polls `useOperatorEvents`, and `WorkspaceAwareness`
already provides a persistent column. Its primary next-event summary selects
only `call_start`; advisories are collapsed. The larger `OperatorEventFeed`
appears after Communications on Now. Existing event timestamps support
`planned_utc`, `live_route_eta`, and `live_unavailable`.

The backend event snapshot is designed for alerts: it filters future entries at
24 hours and bounds recent history. Production capture refreshes the active leg
and retires live publications for inactive legs. Saved plans for other legs are
not proof of current-input alignment. Simply relabeling or moving this feed
would not provide a complete mission timeline.

Add a read-only mission chronology projection using the existing mission
preparation, merged restriction windows, and route ETA logic. Reuse current
active-leg event evidence where available. Include planned events for the other
legs without reactivating their retired alert occurrences. Prepare or validate
scheduled model inputs through existing planning facilities; a preflight plan
must not require live position telemetry. A saved plan without validation is
explicitly last known. Missing input for one leg must not hide known events in
other legs. Keep expensive model preparation cached by input revision and
refresh active-leg boundary timing from current position/speed evidence.

Keep the alert feed's identity, horizon, ledger, acknowledgment, and cue
eligibility semantics intact. Timeline-only scheduled entries do not create
alerts or acknowledgment obligations. Where a row corresponds to an existing
operational event, its expanded details may expose the existing optional
acknowledgment and source navigation. Refresh timing without duplicating an
occurrence. Preserve mission, leg, source mode, replay and store isolation,
pinned pagination if needed, and cancellation when selection changes.

Drive relative times from backend snapshot UTC plus elapsed monotonic browser
time. Refresh the existing live calculation at the current visible-tab polling
cadence. When data becomes stale, retain the last known row with a clear stale
label and stop presenting an advancing countdown as current evidence. Unknown
live timing never silently falls back to planned UTC; the plan remains available
as a labeled reference in details.

## Constraints and non-goals

- Keep the customer-facing Overview as the existing distant-view map. This
  timeline belongs to Operator.
- Treat all predicted outages and recoveries as estimates. No acknowledgment or
  confidence gate is required to use a plan or the timeline.
- Preserve Starshield availability assumptions and the existing Ka/coordinated X
  fallback continuity rules. PoP uncertainty remains an advisory.
- Preserve open editor drafts, source links, local cue settings and optional
  alert acknowledgment behavior.
- Do not add a new transport prediction algorithm, flight-event detection,
  automatic transport changes, inter-leg rescheduling, or external
  notifications.

## Validation and delivery

Verify preflight scheduled windows without telemetry; delayed departure and
changing speed moving active-leg start/recovery estimates; active and passed
windows; unknown and stale timing; cross-midnight UTC; multiple mission legs;
events beyond 24 hours; mission/replay changes; and partial input failures.
Verify that chronological coverage does not generate new alerts for inactive
legs or rearm acknowledged occurrences.

Use focused backend and frontend tests for these contracts and rendered browser
checks at desktop and narrow widths for visibility, scrolling and draft
preservation. Use task-owned, time-limited runners and clean up their resources.
Push the feature branch and open a PR against `dev`; preserve its worktree while
the PR is open.

## Decisions left to implementation

The builder may choose the precise read-only API shape, cache placement,
pagination strategy, row components, compact-screen expansion mechanism and
accessible styling within the existing Python/React application. Those choices
must preserve the behavior and isolation described above. The full-mission
scope, contextual route anchors and collapsed Past presentation are proposals
made here, not additional user instructions.
