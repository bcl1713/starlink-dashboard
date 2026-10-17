# Operator conferences, participation and protected calls

Issue: #366. Parent: #361. Status: design direction approved with PR #377
source-coverage comments; revised specification and implementation plan prepared
for review. Product implementation and merge are not approved. Base: origin/dev
at 5955c99f82651a7bb432dca14be511b87664fe39. Branch: feat/operator-conferences.
Worktree: .worktrees/issue-366.

## Purpose and boundaries

Give the mission communications operator quick, auditable controls for reusable
ground conferences and customer participation on desktop and mobile. A
conference can support sequential or overlapping calls and remain established
between them. An established or verified conference does not establish customer
presence, call success, measured connectivity, or the transport carrying a call.

Use the existing gated Operator workspace, #362 journal and #365 communications
requirements. Keep Operator disabled by default. Preserve Overview's passive
10-foot display, Missions planning, existing exports and shared display
controls. No routing execution, routing approval, mutation blocking, external
services or mandatory acknowledgments are introduced. The unified event feed,
automated alerts, ticking reminders and notification delivery remain #368;
broader form, time-entry and navigation redesign remains #376. Transport
allocation workflows remain #369 and operations-package wiring remains #370.

## Architecture and alternatives

Extend existing conference and participation payloads and permit their public
writes through the existing records API. Reuse immutable full revisions, typed
same-mission links, UTC RecordTime, journal projections, receipts, expected
versions, store epochs and recovery. Do not add a second store or mission model.

A conference-centric record containing all calls and customers would couple
unrelated updates and obscure overlapping intervals. Free-text observations
alone would make lifecycle and overlap derivation unreliable. Separate typed
conference, call and participation records preserve independence and existing
concurrency.

A conference is a reusable resource. A call is a requirement with its existing
schedule and completion status. A participation record is one reported
connection interval; it may identify a call, a conference, or both. Neither
schedule timing nor elapsed wall time creates connection or completion events.

## Conference contract

Extend ConferencePayload additively with nullable fields. Historical omitted
fields read as unknown; reads never rewrite history or receipts.

| Field                     | Meaning                                                                   |
| ------------------------- | ------------------------------------------------------------------------- |
| status                    | unknown, preparing, established, interrupted or closed                    |
| coordinator               | Optional bounded ground coordinator description                           |
| verified_at               | Optional operator-reported verification UTC for the current configuration |
| intended_transport        | Starshield, Ka, X or null; planned intention                              |
| configured_transport      | Starshield, Ka, X or null; operator-reported configuration                |
| configuration_reported_at | Optional UTC of the configuration report                                  |

Use existing title/note bounds; quick creation supplies a generic title when
unnamed. No participant identity, call association, duration, schedule,
transport, coordinator or note is mandatory. A conference normally uses mission
scope so it survives leg switches; explicit existing leg/between-leg scopes
remain supported. Scope expresses association, never automatic expiration.

Conference RecordTime describes the latest reported lifecycle action, using an
instant when its time is known and unknown precision when unknown. Revisions
retain prior actions. verified_at is separate from status: Verify records that
the operator checked the conference, without marking any customer call
successful. All actual timestamps use existing clock acceptance validation.

| Action             | Saved effect                                                           |
| ------------------ | ---------------------------------------------------------------------- |
| Establish          | status established; clear prior verification on re-establishment       |
| Verify             | Set verified_at to reported action UTC; require established status     |
| Interrupt          | status interrupted; clear current verification                         |
| Restore connection | status established; clear verification until explicitly verified again |
| Close              | status closed; clear current verification                              |

Preparing is an explicit editable state. Establish may start from unknown,
preparing or closed. Restore connection requires interrupted status. A repeat
tap with the same idempotency key replays its receipt. Quick-action builders
reject invalid operational preconditions locally; a stale submitted snapshot
returns a version conflict without a revision. The full-replacement API
validates state/timestamp invariants and permits explicit retrospective
corrections; it does not infer an action opcode from an otherwise valid
correction. Repeating Establish on an already established conference is
unnecessary and disabled in the UI. Close is allowed from any nonclosed state.
Editing intended transport alone preserves verification; changing configured
transport clears it. Configuration reporting is optional and never sets measured
connectivity. Retrospective corrections can replace any current snapshot with a
valid state and explicitly supplied nullable verification; no historical
ordering is required to correct a mistaken entry.

Current state is the latest accepted snapshot, not a replay sorted by occurred
UTC. Backdating a correction does not silently reapply other revisions. History
shows occurrence time, acceptance time and revision order separately. An old
action that should not change current state can be recorded as an existing
journal note; there is no new historical event editor in this slice.

## Customer participation and interruptions

Extend ParticipationPayload with nullable participant description and a
connection state: unknown, connected, interrupted or left. Retain optional
call_id and conference_id and the existing requirement for at least one target.
Unknown customer identity is valid. Call-only participation allows Customer
Joined before a conference is established or selected; conference-only
participation supports an unscheduled or unidentified call. Linking both
requires targets in the same mission, but need not match the call's current
preferred conference: a call can move conferences, and historical intervals
retain their actual association.

Each record represents one uninterrupted reported interval. RecordTime holds
actual join and leave/interruption boundaries, independently of planned call
time. Customer Joined creates connected with known start/ongoing end by default,
using the shared clock. Retrospective entry may use approximate or entirely
unknown timing. Unknown timing requires the existing null-time/unknown-end
contract, while the explicit connected state can still report current presence.
No known duration or completed schedule is required. End-only input follows
existing validation; record the state with unknown times rather than inventing a
start.

Customer Left closes only the selected participation interval with state left.
Interrupt closes only the selected interval with state interrupted. When its
start is known, capture the end; otherwise retain unknown interval timing.
Restore connection creates a new connected interval for the same targets and
participant, leaving the interruption and gap intact. A new optional same-type
resumes_participation_id link identifies the interrupted predecessor; validate
same mission and compatible targets and prevent removal while referenced. It is
not required when entering independent retrospective intervals. Restore
connection is distinct from the journal tombstone action, labeled Restore
record. Audit text distinguishes Customer connection restored from Operator
record restored.

Multiple connected records are allowed, including unknown participants and
overlapping calls. Show each reported interval separately; do not merge
identities, deduce uninterrupted service, or infer that one customer's join
proves another's presence. A conference interruption never edits participation
records implicitly: show a conspicuous discrepancy / continuity unknown beside
customer reported connected, never an all-clear. The operator can interrupt
affected participation intervals explicitly. Similarly closing a conference
leaves customer reports visible with a discrepancy cue; it does not fabricate
leave times or require a confirmation dialog.

Completing, cancelling, rescheduling, removing, restoring or relinking a call
never mutates its conference or participation records. Active participation
beside a completed/cancelled call remains visible for correction. Closing
participation never completes its call. Existing dependency validation may
prevent removal of a referenced record; explain the dependency, never cascade
deletion. Leaving a customer or closing a conference is always a separate
deliberate action.

## Transport provenance

Display three separate concepts: intended transport, operator-reported
configuration, and measured connectivity. Null means unknown for the first two.
Configuration reports carry occurrence UTC and operator provenance. Preserve all
changes as revisions; there is no independently verified call-bearing transport
field or action.

Existing observed Starshield telemetry may be shown with source/freshness
labels, but cannot verify the transport carrying a particular call. X and Ka
remain modeled or manually reported. Conference verification is operator
reported, never an observed source-sync event. Service observations do not
automatically change conference, participation, configured transport or
call-success state.

## Protected-call advisories

A currently connected, nonremoved participation record is a protected customer
activity, even when schedule, identity or start time is unknown. Interrupted and
left intervals are historical and do not assert current connection. Completed or
cancelled call status does not suppress an outstanding connected report.
Multiple participations protect independently; conference-only participation is
labeled unassigned customer activity rather than inventing a call.

Within Communications, show a compact protection indicator and overlapping
supported modeled restrictions. Use the existing read-only
`GET /api/v2/missions/{mission_id}/legs/{leg_id}/timeline` from
`app/mission/routes_v2.py`, through `timelineService.getTimeline` in
`src/services/timeline.ts`. Its `MissionLegTimeline` payload supplies all
interval sources for this slice:

| Source                        | Interval and identity fields                                                                        | Supported interpretation                                                                                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `pop_forecast.transitions[]`  | `window_start_utc`, `window_end_utc`; `crossing.id` plus `pop_forecast.revision`                    | #348 modeled PoP advisory window; `crossing_utc` is a prediction, not an observed handover                                          |
| `call_continuity.intervals[]` | `start_utc`, `end_utc`; projection `revision`, `transition_ids`, `source_ids` and classification    | Existing modeled call consequence: advisory, x_fallback, planned_outage, existing_outage or unknown; ordinary intervals do not warn |
| `segments[]`                  | `start_time`, `end_time`, `id`; `x_state`, `ka_state`, `ku_state`, `reasons`, `impacted_transports` | Existing modeled degraded/offline transport availability; wire `ku_state` means Starshield, not measured call carriage              |

`created_at` describes when the saved timeline was computed, not a promise that
it matches current planning inputs. Preserve `call_capability_revision`,
forecast revision and source timestamps in the normalized snapshot. Missing
timelines, indeterminate forecasts, absent continuity, or unavailable revision
alignment yield partial/unknown coverage; they do not trigger timeline
generation or a planning mutation. Read all relevant mission legs and retain leg
identity; a failure in one leg cannot produce a mission-wide all-clear.
Adjacent/duplicate consequences from the same source are grouped, with source
references preserved. Display PoP advisories separately from the existing
computed outage/fallback classification; do not reimplement the planner's
fallback calculation.

No existing Operator plan-of-change source is consumed in #366. Intended and
configured transport fields are snapshots, not a future change schedule. Do not
infer routing changes from differences between successive snapshots, satellite
handoff recommendations, telemetry fluctuations, or SDR/OSPF state. Correlation
with operator-entered future transport changes is deferred to #369. Explicit UI
coverage copy: “Modeled restrictions only. Operator-planned transport changes
are not included.”

`GET /api/status` exposes the real #348 `pop_forecast`, `pop_advisories` and
`call_continuity` via `PopStatusService`, but describes the globally active
route. It is not a source for arbitrary selected-mission protection in this
slice; do not attach its intervals to another mission. The per-leg timeline uses
the same #348 forecast and continuity implementation with explicit mission/leg
association. Synthetic acceptance must exercise that real implementation and
assert that no operator-planned change is invented or presented as covered.

Use configured transport for relevance when known, otherwise intended transport.
With neither known, show relevant mission-level candidates as transport
relevance unknown, never as confirmed impact. Aggregate call-continuity
classifications remain call-level modeled consequences, not evidence that a
named transport carries the customer call.

Evaluate current and future intervals against the injected backend/read as_of.
The current protected horizon starts at as_of and ends at a still-future planned
call end when known; if that end has elapsed or is unknown, leave the horizon
open within the available model horizon. Label that bound as expected duration
and never assume it ends participation. Recompute on existing
refresh/save/reconnect paths; show the snapshot time and stale state. There is
no new timer, polling loop, alert queue or notification delivery. Historical
interval comparisons use reported actual bounds and explicitly mark unknown
boundaries as indeterminate.

Use half-open overlap semantics; touching boundaries alone are not overlap.
Group by source identity and interval so ordinary telemetry fluctuations do not
generate new warnings. A changed source appears in the next snapshot.
Optional-source failure yields unavailable/partial advisory coverage while
records and controls remain usable. Incomplete pagination cannot yield an
all-clear. A visible empty state says no overlaps found in the available
snapshot, never guaranteed safe.

PoP transition windows remain advisories, not outages. Unknown PoP/location or
handover timing does not establish loss. Assume Starshield available unless
explicitly disabled or deliberately marked down. Preserve the existing planning
rule: full-window outage applies only where Starshield is the sole usable
transport; usable Ka or coordinated concurrency-only X protects the plan. Show
the existing modeled consequence without relabeling it as observed customer
failure. No advisory blocks saving, approves a change, executes a change, or
demands acknowledgment. No warnings are generated from every raw telemetry
sample.

## API, concurrency and audit behavior

Extend the public create/update union and remove/restore allowance only with
conference and participation. Keep issue/risk/transport-report writes outside
this slice. Add the predecessor link to the existing link-index derivation and
recovery checks; rebuild that derived index transactionally for existing stores
if needed. No new durable table is expected. Preserve strict payload validation,
no-store responses, disabled-feature behavior and the existing LAN boundary.

Quick actions use the same full-replacement update contract with
expected_version, store epoch and UUID idempotency key. They do not introduce a
generic action engine. The current snapshot and immutable revision represent one
acknowledged action; lifecycle field differences and automatic reasons identify
it. Notes are optional. Defaults and clock values are captured once in the
command and reused on uncertain retry, rather than changing request content
under an existing key.

Joined and restored intervals are creates; Leave/Interrupt and conference
actions are single-record updates. Each quick action has one transactional
receipt; no multi-record mutation is hidden behind a tap. Stale edits return
explicit version conflicts, retain the user's intent and require reconciliation.
Do not automatically reapply a destructive action to a newly loaded state. An
uncertain response retains its key until reconciliation; a receipt is followed
by current-state reread because another client may already have edited the
record.

Reuse immutable corrections, remove/restore, history, backup and projections.
Missing legacy fields remain unknown, including in old receipts. Preserve #365
preparation lead omission/null/zero semantics when associating calls. A payload
extension cannot mutate raw historical JSON. Any concrete new storage migration
must be documented and reviewed before implementation departs from this design.

## Operator experience

Extend the current Communications section with conference cards and associated
participation rows. Keep common actions visible as short buttons: Establish,
Verify, Customer Joined, Customer Left, Interrupt, Restore connection and Close.
The target is explicit on each row; conference and customer controls are
visually separate. Show conference state, operator verification, customer state
and protection separately rather than a single success badge.

Default action time is shared UTC now, with optional correction/retrospective
entry through the existing editor conventions. Derive generic titles and retain
current mission context. Optional details expose coordinator, participant,
transport, notes and timing without blocking common taps. Normal actions need no
confirmation dialog or mandatory note. Pending buttons prevent duplicate taps;
Saved appears only after receipt. Preserve drafts on failure and show actionable
conflict, unknown, stale and unavailable states. Keep store-bound drafts and
existing refresh/focus/reconnect behavior; no claim of real-time cross-client
push.

Lists include all pages at a consistent journal watermark. Calls and conferences
may be associated with different legs in the same mission; selecting another leg
must not hide mission-level established conferences or active participation.
History exposes old/new values, reported versus recorded UTC, and
remove/restore. Responsive changes stay within the existing shell and
communications components; no #376 redesign is included.

## Synthetic verification and acceptance

Implementation acceptance must exercise real application paths, using only
synthetic missions, coordinates, parties and observations. Inject deterministic
UTC through the existing simulation clock. Optional providers may deliberately
fail; terminal hardware, aircraft, real itineraries and external services are
not required. Simulation demonstrates software behavior, not aircraft readiness.

| Scenario                  | Required assertions                                                                                                                                                                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared conference         | Two sequential calls reuse one established conference; idle interval remains established; completing/cancelling/rescheduling either call leaves conference revision unchanged                                                                                        |
| Overlap and joining order | Two overlapping calls retain separate intervals; join before establish and establish before join both work; verification never fabricates customer success                                                                                                           |
| Unknowns                  | Unknown identity, schedule, duration, actual timing and transport save without invented values; call-only and conference-only participation remain usable                                                                                                            |
| Interrupt/restore         | Customer restoration creates a new interval, preserves gap and predecessor; conference interruption/closure does not invent customer leave or continuity                                                                                                             |
| Corrections               | Backdated/approximate edits preserve occurrence/recorded separation, old revisions and current snapshot semantics; remove/restore and dependency conflicts remain explicit                                                                                           |
| Protection                | Supported timeline restrictions and real #348 predictions produce bounded contextual advisories; unsupported operator-planned changes remain explicitly uncovered; boundary touches, raw telemetry jitter and unrelated transport do not produce false impact claims |
| Planning rules            | Synthetic #348 positions/routes cover unknown location, transition timing, default Starshield availability, sole-transport outage and usable Ka/coordinated X fallback                                                                                               |
| Lifecycle                 | Exercise real #349 preflight, flight transitions, leg switch, on-blocks and completion; conferences survive, associations remain valid, archives and mission packages retain existing behavior                                                                       |
| Two clients/failures      | Duplicate writes replay; concurrent edits conflict; held/lost responses do not falsely show Saved; offline drafts, reconnect, failed optional sources and pagination retain honest state                                                                             |
| Restart/recovery          | Restart with an established conference and overlapping connected customers; recover identical current states, revisions, receipts, predecessor links and protection snapshot without duplicate events                                                                |

Backend unit/contract/integration tests cover payload defaults, action
validation, UTC tolerance and interval rules, typed links, projections, legacy
receipts, backup/recovery and deterministic advisory derivation. Frontend tests
cover quick actions, target separation, unknowns, accessible desktop/mobile
controls, optional fields, conflict/retry, stale snapshots and incomplete lists.
Extend the existing operator-journal acceptance harness and synthetic fixtures;
do not substitute mocked PoP or lifecycle outcomes for the required real
integration journeys.

Fresh exact-commit production Docker/Nginx browser runs cover 1920x1080 desktop,
390x844 portrait and 844x390 landscape, two clients, restart and failure
injection. Capture sanitized screenshots, machine-readable assertions, test/tool
versions, source clocks and interval inputs, existing export compatibility and
Overview layout/history behavior. Run applicable backend/frontend/static CI
gates on the final PR head. Design-only review does not claim any implementation
tests passed.

Before starting runtime resources record ownership and install exit/signal
cleanup. Use a task-specific Compose project and private disposable volumes,
wall-clock timeout plus termination grace for every test run. Stop and verify
processes, listeners, containers, networks and volumes after checks, preserving
only evidence and the open-PR worktree. Never prune shared resources.

## Compatibility, rollout and review gate

Keep the feature disabled by default. Extend JSON payloads additively without
rewriting historical records. Verify older fixtures and unchanged call/journal
contracts. Before upgrade preserve a store backup. Roll back by disabling
Operator; a binary downgrade with closed old models requires restoring the
pre-upgrade backup and preserving the newer store separately. Document any
required derived index migration and reversal explicitly.

This document is the review artifact. After specification approval, write the
implementation plan and obtain its required review before product changes. Work
stays on feat/operator-conferences in .worktrees/issue-366, based on origin/dev;
submit against dev. Do not merge as part of specification approval. Keep the
worktree for review, then remove task branches/worktree after authorized merge.
