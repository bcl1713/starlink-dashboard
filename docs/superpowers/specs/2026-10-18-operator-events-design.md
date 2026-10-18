# Operator event feed and local alerts

Issue: [#368](https://github.com/bcl1713/starlink-dashboard/issues/368). Parent:
[#361](https://github.com/bcl1713/starlink-dashboard/issues/361). Status: review
clarifications approved in PR #379 comment 6244505182; native implementation
authorized by the user. Product acceptance, final review and merge remain separate. Base: `origin/dev` at `30d628c8`. Branch: `feat/issue-368-events`.

## Purpose and boundaries

Give the communications mission manager one UTC timeline showing what is
happening now, what comes next, and what needs attention. Events exist
independently of notification delivery. Muting sound, disabling notifications,
acknowledging an alert, or using an unsupported device must never hide an
operational requirement.

Combine call preparation/start milestones, issue follow-ups, existing #348 PoP
continuity advisories and modeled transport restrictions. Reuse #366 conference
and participation records to highlight relevant restrictions during customer
activity. Preserve Scheduled, Operator-reported, Modeled and Observed
provenance; a modeled restriction never becomes a verified outage through
prominence or sound.

Keep the existing Operator gate disabled by default. No routing actions,
transport approval, mission-save acknowledgments, export changes, Overview
changes, broad layout redesign (#376), external notification infrastructure,
PWA, certificates, Web Push or native application. All runtime requests stay on
the existing LAN HTTP application. Unknown PoP or handover timing never means
service unavailable.

## Architecture and alternatives

Use a backend event projection with a small durable notification ledger in the
existing Operator SQLite database, and one page-level frontend feed/controller.
Reads derive events from a pinned operational-record snapshot plus explicitly
identified, independently captured planning/live snapshots. The feed states this
capture boundary; it does not claim a transaction across mission and telemetry
stores. Notification eligibility is a separate projection over current events.
Only notification occurrence state and acknowledgments require new persistence.

A frontend-only aggregator would make clock, revision reconciliation and shared
acknowledgment inconsistent between clients. Persisting every forecast result as
a journal event would create unbounded revision noise and duplicate predictions.
Neither is selected. There is no new prediction engine or external scheduler.

### Existing integration points

| Concern                      | Existing implementation to reuse                                                                    |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| UTC and simulation identity  | `app/operator/clock.py`, `runtime.py`, store identity and epoch headers                             |
| Records and history          | `service.py`, `queries.py`, immutable revisions and journal watermarks                              |
| Follow-up eligibility        | `issue_followup.py`; resolved/deleted and clock-regression rules                                    |
| Call preparation             | persisted `prep_lead_minutes`; creation default remains ten minutes                                 |
| Saved mission restrictions   | `mission/timeline_preparation.py`, existing timeline segments, `pop_forecast` and `call_continuity` |
| Live PoP forecast/advisories | `mission/pop_status.py` snapshot coordinator and `services/pop/live.py`                             |
| Prediction and continuity    | `mission/pop_forecast.py`, `mission/pop_continuity.py`, existing coverage/capability logic          |
| Protected activity           | conference/participation records and semantics in `components/operator/conferenceProtection.ts`     |
| Flight and leg lifecycle     | existing #349 flight-state and `services/telemetry_archive/coordinator.py` contracts                |
| Durability                   | Operator admission locks, transactions, capacity checks, backup and recovery                        |

The adapter consumes already published snapshots or invokes the existing pure
calculation path with captured local inputs. It must not publish map POIs, write
mission plans, call external providers, or advance the stateful live coordinator
merely because another browser requests the feed. Share the live publication
used by status; expose a read-only captured snapshot internally if needed. The
selected mission's inactive legs use saved planning timelines. Live evidence
applies only when its mission, leg, source mode and lifecycle identity match.

## Event contract and timeline

Add `GET /api/v2/operator/events?mission_id=...` under the existing gate.
Version 1 returns server `as_of` UTC, store identity/API epoch, source mode/run,
operational high-water mark, snapshot generation, source capture/revision
metadata, coverage (`available`, `partial`, `unknown`), and events. Every source
reports freshness, input alignment and reason independently; partial results
survive optional-source failure. Successful HTTP retrieval alone does not
establish source freshness.

Each event contains stable `event_id`, occurrence/generation identity, mission
and optional leg, kind, short title, due/start/end UTC where known, lifecycle
state, provenance, source references/revisions, source capture time,
freshness/confidence, transport relevance, protected participation/conference
references, significance, and separate notification state. Null timing remains
unknown, never a guessed due time. Source text and timestamps are escaped and
rendered locally.

Default horizon is the next 24 hours plus active windows and unresolved overdue
calls/follow-ups. Recent superseded/finished occurrences are available in a
compact history view for the previous 24 hours. Bound responses at 200 events
with stable snapshot pagination and explicit truncation/partial indicators. All
pages of one snapshot are pinned; a refresh replaces the snapshot atomically.
Order timed rows by effective UTC then event ID; show unknown-time rows
separately. Now, Next and Attention are views of this same chronology, not
separate event stores.

Canceled/completed calls, resolved issues and removed records leave the
actionable queue immediately after a fresh authoritative read. Their source
history remains inspectable. No notification is generated from historic
revisions or restored notification history. Restoring/reopening a source only
enables a new occurrence when its current timing satisfies the eligibility rules
below.

### Event kinds

| Kind                    | Source and time                                                      | Default cue                         |
| ----------------------- | -------------------------------------------------------------------- | ----------------------------------- |
| Call preparation        | scheduled/delayed call start minus persisted prep lead               | sound and vibration                 |
| Customer requirement    | scheduled/delayed call planned start                                 | sound and vibration                 |
| Issue follow-up         | unresolved current issue `follow_up_at`                              | vibration only, lower priority      |
| PoP window              | existing transition window start/end                                 | visual advisory only                |
| Significant restriction | existing degraded/offline segment or nonordinary continuity interval | sound and vibration when actionable |

Tentative calls remain visible but do not alert until scheduled/delayed. Unknown
prep lead produces no fabricated prep reminder; legacy absence uses the existing
contract's default only where that contract already defines ten minutes. This
slice does not rewrite saved call preparation settings.

A significant restriction means a modeled unavailable/degraded transport
interval or an existing nonordinary continuity classification. Normal handovers,
ordinary satellite transitions, raw telemetry fluctuations and unknown
observations do not alert. A PoP window alone stays visual; an independently
calculated significant continuity restriction may alert and includes its PoP
linkage. Related causes are combined into one card/cue when they describe the
same transport/time occurrence; source details remain inspectable. The existing
full-window planning outage rule applies only with Starshield as sole usable
transport, accounting for usable Ka and coordinated concurrency-only X fallback
through existing continuity logic.

## Stable identity and notification generations

Separate three concepts: operational event identity, source revision, and the
notification occurrence that can be acknowledged. Never key an alert solely by a
forecast revision, rendered label, rounded current time, or browser delivery
time.

Calls use store/mission/record ID plus milestone kind as event identity. A
changed planned start or prep lead creates a new occurrence generation for
affected milestones; text-only corrections do not. Issues use
store/mission/record ID plus follow-up kind; a changed follow-up UTC creates a
new generation. Cancellation, completion, resolution or removal retires pending
generations in the same source reconciliation transaction. Historical
acknowledgments stay attached to their old generations. Restoring an unchanged
obsolete generation does not re-arm it.

PoP source IDs currently include revision (`services/pop/forecast.py`). Derive
the Operator identity from mission/leg, effective route geometry identity,
catalog fingerprint, from/to PoP and ordered crossing occurrence along that
route. Use the existing crossing geometry/ordering, including repeated regional
re-entry; do not calculate different boundaries. Timing-only changes preserve
event identity. A route/catalog/lifecycle change supersedes its affected
prediction family.

Restriction families use leg, effective route/input geometry, transport,
existing source cause identities and ordered contiguous restriction occurrence.
Coalesce adjacent same-cause/classification segments before assigning an
occurrence. When source IDs change, reconcile only uniquely overlapping windows
in the same family; ambiguous split/merge results supersede predecessors and
remain visual until two consistent fresh captures establish an actionable
candidate. Never merge by title alone. Source revisions are retained as
evidence, not notification generations.

For modeled events, keep the accepted notification anchor and severity in the
ledger. Timing drift below five minutes updates display without re-arming. A
shift of at least five minutes must persist for two consecutive fresh captures
at least 15 seconds apart before a replacement generation is accepted. Compare
to the accepted anchor, not the immediately previous refresh, so gradual drift
is handled. A replacement is cue-eligible only after the new threshold is
crossed; moving an already due window around does not repeatedly cue. Once
retired, a generation cannot become pending again. New route families obey
catch-up and rate limits.

These are provisional software tuning defaults, not physically validated limits.
An injected `EventPolicy` controls `model_shift_seconds=300`,
`model_stable_captures=2`, `model_capture_spacing_seconds=15`, and
`model_escalation_captures=2`. Validate finite positive values and a capture
count of at least two. Load optional operator deployment overrides, with no new
controls on Overview. Deterministic tests exercise defaults and shorter
rapid-crossing settings; tuning cannot alter the underlying #348
prediction/window semantics.

Acknowledgment covers one occurrence and its severity tier. Prediction revision,
wording, confidence changes or increased protection prominence alone preserve
it. A genuine escalation from degraded to unavailable, or from
transport-specific restriction to the existing call-outage classification, can
create one higher-tier notification generation after two consistent fresh
captures. Downgrade/re-escalation to an already acknowledged tier does not
re-arm. A new explicit call/follow-up schedule can re-arm even if the prior
schedule was acknowledged.

## Protected customer activity

Every nonremoved participation with state `connected` is protection-relevant,
even when its conference is closed, interrupted, unknown, removed or missing.
Conference closure does not edit the customer observation. Preserve emphasis and
alert relevance; show the association/status discrepancy as continuity unknown.
Do not silently drop conference-only or call-only participation. A call-only
participation has unknown transport relevance unless an independent valid source
establishes it; a conference-only participation needs no call record to protect
it. Left/interrupted/unknown participation does not assert a currently connected
customer. Do not infer a connection from a call's planned start or an
established conference without connected participation.

For a valid established conference, match restrictions to configured transport
first; intended transport is separately labeled planned relevance. With no
transport report, relevance is unknown. A missing/removed/closed/interrupted
conference makes continuity and transport relevance unknown; retain potentially
relevant restrictions with that label rather than filtering them out using an
obsolete configured transport. Include existing call-continuity restrictions
where applicable. Show all affected active customer activities on one
restriction; multiple participations never multiply alerts. Planned call end may
bound future context but must not silently terminate an explicitly connected
observation. Show old connection observations with their age and uncertainty.
Protected activity increases ordering/emphasis, not evidence confidence, outage
classification or permission to act.

## Durable acknowledgment and concurrency

Add migration `002` with notification occurrence state and immutable
acknowledgment rows in the existing database. Occurrence rows hold source
family, accepted anchor, severity tiers, supersession state, minimal sanitized
snapshot, and first/last seen UTC; do not copy telemetry samples. Persist
creation, material schedule/severity changes and retirement, not each forecast
refresh. Event history uses existing source revisions plus these material
notification transitions.

Add `POST /api/v2/operator/events/acknowledge` accepting occurrence ID, severity
generation and snapshot token, with existing idempotency and store-epoch
headers. Validate according to the versioned capture protocol below; reject a
superseded generation with 409 and return refreshed identity. A unique database
constraint on `(store_id, occurrence_id, severity_generation)` ensures two
clients acknowledge once even with distinct request keys. A second
acknowledgment returns the existing durable result, without another
acknowledgment or journal revision. Reuse the command receipt machinery for
exact retries and incompatible key reuse.

### Versioned capture and acknowledgment authority

The snapshot token is server-issued and opaque, bound to store ID/API epoch,
mission/leg, source mode/run/lifecycle, event occurrence/severity generation,
reconciliation generation, source record versions, effective route/catalog/input
identities, and the relevant published model revisions/capture generations. Use
a server-side registry capped at 256 snapshots per runtime, evicting the oldest
issued first, with a two-minute real-monotonic TTL; restarts invalidate tokens,
not acknowledgment history. Expired/unknown tokens return 409 requiring a fresh
feed. Tokens grant no authority to mutate sources.

The feed pins Operator records at high-water H and each independently captured
immutable model publication at its own generation. There is no distributed
transaction and H never claims to pin mission/telemetry stores. Responses expose
all capture identities and times. Pagination uses the same pinned captures.

For a new acknowledgment:

1. Refresh/revalidate the relevant local source publication and its input
   identity outside SQLite. Recompute only via existing source logic when
   required.
2. Acquire the source-publication read guard, then Operator admission and an
   immediate SQLite write transaction, in that order. Re-read relevant Operator
   records and occurrence state inside the transaction. Unrelated journal writes
   need not invalidate a token; changed dependent record versions do.
3. Compare the token's modeled publication/input generations to the guarded
   current publications and verify freshness/alignment. A generation mismatch is
   409; missing, stale, unaligned or unguardable required evidence is 503.
   Return no acknowledgment receipt for either outcome. Scheduled-only events do
   not fail merely because an unrelated modeled feed is unavailable.
4. Reconcile affected generations, insert the uniquely constrained
   acknowledgment and its idempotent receipt, and commit while holding the
   publication guard. Release the SQLite/admission resources before the
   publication guard.

The guard serializes publication/invalidation of the adapter's local immutable
snapshots, not remote reality. All relevant local publishers and source-input
invalidation paths must participate: mark an input generation invalid before a
changed route/catalog/lifecycle/configuration becomes eligible, and publish its
replacement only with matching evidence. Where a source cannot provide this
revision/guard contract, show its events read-only with acknowledgment
unavailable and return 503 rather than promise cross-store atomicity.
Multi-process deployments must share the publication gate/generation state or
conservatively disable modeled acknowledgment; a process-local lock alone is
insufficient there.

A model change between refresh and guard acquisition causes 409. A pending
publication detected before commit aborts acknowledgment. A publisher arriving
while the guard is held waits; acknowledgment refers to the then-current
captured publication and commits before the replacement becomes authoritative.
Later publication reconciles the new generation and cannot acknowledge it
through the old row. This is serialization of local published evidence, not a
guarantee that an aircraft or independently stored input cannot change after
capture.

For calls/issues, source validation and occurrence retirement share the same
Operator transaction. For models, retirement is reconciled against guarded
publication generations; a response never knowingly advertises a superseded
pending generation. An old response already delivered to a browser remains
subject to the documented polling boundary. Exact replay of a committed request
returns its original receipt even after source changes, explicitly identifying
the acknowledged historical generation; it does not acknowledge the replacement.

Acknowledgment only records notification disposition. It never edits a call,
issue, participation or prediction and never hides the event. There is no
unacknowledge control in this slice. Failed/uncertain requests remain visibly
pending, with the same frozen retry request; no successful acknowledgment is
claimed until confirmed. Clients poll current acknowledgment state. A short race
may cue another device before the acknowledgment reaches it; exactly-once
physical sound is not promised.

Acknowledgments are shared across clients; notification delivery settings and
emission history are local. Separate clients may each cue an unacknowledged
event. Same-browser tabs elect one emitter using same-origin coordination with
expiring ownership; lack of coordination support is disclosed and disables
automatic cues in secondary tabs. No persistent delivery claim is treated as
physical delivery.

## Timing, catch-up and freshness

Backend injected `Clock` is authoritative for due status, reconciliation and
notification eligibility. Use its UTC wall time and the existing lifecycle/run
identity. Browser monotonic elapsed time can animate countdowns, but cannot
advance fake mission time or issue an eligible cue without a fresh server
snapshot.

One Operator-level controller polls every 15 seconds while visible; invalidate
on successful relevant mutations, focus and reconnect. One request may be in
flight; abort superseded mission/store requests and discard late results. Hidden
pages poll no faster than 60 seconds when the browser permits, with no delivery
promise. Stop all controller resources when leaving Operator. Do not add
per-editor polls. Cache existing source calculations by their input identities;
a feed read must not run expensive forecasts per client when inputs are
unchanged.

Notify prep and issue follow-up at due time, customer requirement two minutes
before start, and significant modeled restriction five minutes before interval
start. These are notification thresholds, separate from the event's displayed
UTC time. An eligible visible cue requires a successful snapshot at most 30 real
seconds old, current record identity, valid source freshness/alignment, and no
clock regression. Sources keep their existing stricter freshness rules; saved
plans with unknown alignment are labeled partial and cannot produce automatic
restriction cues. Explicitly disabled sources are labeled disabled, not stale or
all-clear.

On first open, refresh, reconnect, visibility return or restart, evaluate
current state, never replay a queue of notification delivery attempts. Catch-up
candidates are unacknowledged calls in prep through planned end (or start plus
15 minutes when end unknown), restrictions still active or starting within five
minutes, and follow-ups due within the preceding 15 minutes. Older unresolved
events remain in Attention without automatic cues. Any candidate also needs a
crossed threshold; future prep or follow-ups do not notify prematurely.

Emit at most one grouped catch-up cue, containing at most three highest-priority
candidates, with a count/link for the rest. Priority: customer requirement,
restriction affecting protected activity, call prep, other significant
restriction, issue follow-up; tie-break by UTC then stable ID. All actionable
rows remain individually visible and acknowledgeable. During continuous
operation coalesce threshold crossings over five seconds, enforce at least 30
seconds between cues, and one automatic cue per occurrence/severity per client.
Deferred candidates are reevaluated against current eligibility instead of
queued indefinitely.

Persist a bounded local emission cache per store/run/mission, retained for seven
days, so refresh does not replay already cued generations. Durable
acknowledgments survive restart; unseen currently actionable generations may
produce one catch-up cue after restart. Muted/disabled delivery does not mark
candidates acknowledged. Enabling delivery uses the same grouped catch-up
policy. Clock regression/seek suspends cues until a fresh consistent lifecycle
snapshot; a changed simulation run gets a separate namespace. Unchanged
occurrences in a rewound run are not replayed.

Missing/stale inputs retain last known rows with their as-of and unknown current
status. They cannot resolve an event, clear Attention, or claim no restrictions.
A fresh source snapshot may supersede or end a prediction; a missing one cannot.
If the store is unavailable, retain read-only last-known display and disable
shared acknowledgment; do not fall back to invented success or local durable
acknowledgments.

## Compact Operator experience

Replace the current snapshot Upcoming summary with a compact page-level strip:
Now, Next and Attention counts, nearest timed requirement, freshness and local
alert status. Keep it accessible while working in Communications, Issues,
Journal or Display Tools through a sticky strip and expandable feed drawer.
Desktop uses a small side drawer; mobile uses a dismissible sheet with
appropriate focus return, keyboard handling and scroll containment. No sheet
opens automatically on a cue. Do not obscure editor fields, save actions or
conflict messages. Opening the feed preserves editor drafts, mission context and
scroll position.

Rows show UTC/time remaining, concise purpose, provenance, modeled advisory
label, protection relevance and acknowledgment state. Source details expand on
demand; source links navigate within Operator without discarding dirty drafts.
Acknowledge is a separate action from opening/editing the source. An
acknowledged row remains visible. Use restrained live-region announcements for
grouped cues and status changes, without announcing every countdown/poll. Labels
and keyboard controls must work without color, motion, sound or vibration.

Local notification controls fit in one popover: in-app cues on/off, sound
on/off, vibration on/off, and a user-gesture Test/Enable sound action. In-app
cues default on; sound/vibration default requested for the high-priority types
in the table, with routine follow-ups vibration-only. No browser permission
prompt or vibration is triggered on page load. Persist preferences per browser;
never confuse requested settings with successful device output. Sound uses a
bundled/generated local tone; no remote audio. Handle suspended audio contexts,
rejected playback, missing vibration API and unsupported mobile browsers without
failing the feed.

Show concise states such as Sound needs interaction, Muted, Vibration
unavailable, Offline—last updated … UTC, and Background delivery not guaranteed.
Hidden-tab notifications and screen-off operation are explicitly best-effort.
Reopening the page does not imply notifications were delivered while it was
closed.

## Persistence, compatibility and backout

Generalize the current single-file migration validator to ordered
checksum-checked migrations without changing migration 001. Provide an explicit
maintenance upgrade command under exclusive admission: backup first, apply 002
transactionally, run integrity checks, then reopen. Normal service startup does
not silently migrate an existing store. An unupgraded store reports actionable
schema/upgrade status behind the Operator gate while baseline application
startup remains available.

Migration 002 adds tables/indexes/triggers only; preserve source records,
immutable journal sequences, command receipts and existing projections. New
acknowledgment receipts use the commands table but do not create operational
revisions. Include new tables and their constraints in validation, capacity
accounting, backup/restore, commit-crash recovery and namespace tests.
Notification metadata is local Operator state and is not added to mission
packages, JSONL projections or existing exports.

Keep minimal notification history for the store's lifetime under existing
private storage and capacity controls; no new automatic deletion policy. The UI
bounds its history window independently. If capacity is exceeded,
acknowledge/reconciliation writes fail explicitly without destroying source
history. Do not persist repeated poll timestamps or every source refresh.
Polling a steady feed must cause no writes.

Rollback: stop the task stack, preserve an upgraded-store backup, and restore
the pre-upgrade backup before running old code; old code intentionally rejects
schema 002. This rollback loses acknowledgments and other writes after that
backup, which must be stated in the maintenance instructions. Turning off
Operator stops its feed and alerts without rolling back the database or changing
other application behavior.

## Failure and race semantics

| Situation                                     | Required behavior                                                                                                                  |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Call moved while prep alert pending           | reconcile against the current Operator transaction before returning a fresh snapshot; obsolete generation cannot newly acknowledge |
| Cancel/complete/remove/resolve                | suppress automatic cues after authoritative reconciliation; preserve source history                                                |
| Two acknowledgments, different keys           | one durable acknowledgment; both receive its identity                                                                              |
| Lost acknowledgment response                  | retry same body/key; read back confirmed result                                                                                    |
| Source changes during acknowledgment          | validate pinned generations using the capture protocol; reject with 409/503, without a new acknowledgment                          |
| Feed result arrives after mission/run switch  | discard by request identity; never show or cue in new context                                                                      |
| Forecast refresh or aircraft movement         | update timing/revision in place; apply drift/stability rules without refresh noise                                                 |
| Prediction disappears due to unavailable data | last-known/unknown; no all-clear and no automatic cue                                                                              |
| Backend restart                               | retain occurrences/acknowledgments; bounded catch-up after fresh data                                                              |
| Browser storage unavailable                   | timeline/acknowledgment work; disclose session-only delivery dedup; no replay within the current session                           |
| Audio/vibration fails                         | retain visual cue and event; report output limitation, never mark acknowledged                                                     |
| Mid-transaction crash/disk failure            | atomic rollback or committed result; existing recovery and idempotency paths apply                                                 |

A cue already emitted before another client's cancellation/acknowledgment
reaches this client cannot be recalled. Every cue is checked against the latest
received eligible snapshot; the 15-second polling boundary is visible and
tested. There is no claim of instantaneous synchronization or exactly-once
physical delivery.

## Aircraft-free acceptance

Use wholly synthetic mission identities, routes, positions and operational
records in an isolated production Docker/Nginx project. Inject deterministic UTC
through the backend clock and the actual simulation/replay context, including
the observation freshness clock where existing #348 contracts distinguish it
from mission time. Do not substitute mocked prediction JSON for integration
acceptance. Unit tests may use contract fixtures; integration and browser
acceptance exercise the real local PoP catalog/geometry/timing/continuity and
#349 leg/archive lifecycle.

| Area                  | Required controls and evidence                                                                                                                                                                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contracts and clock   | versioned feed/ack schemas, stable ordering/pagination, unknown times, exact thresholds, UTC midnight, large forward jump, regression and new run                                                                                                              |
| Calls/issues          | ten-minute creation default, overlap, prep/start milestones, pending move, prep-lead edit, cancel/complete/remove/restore, issue resolve/reopen, overdue follow-up, text-only correction                                                                       |
| Identity              | same forecast revision refresh, timing drift and cumulative drift, accepted-anchor shift, repeated PoP re-entry, route/catalog change, split/merge ambiguity, severity downgrade/re-escalation                                                                 |
| Real #348 integration | actual synthetic route crossings and injected aircraft positions; full window bounds, normal PoP advisory, fallback-protected interval and sole-usable-Starshield restriction; unknown PoP is not outage                                                       |
| Protected calls       | overlapping connected participations, shared conference, configured/intended/unknown transport, closed/interrupted/missing conference with still-connected participation, call-only/conference-only participation, stale observations; one cue per restriction |
| Acknowledgment        | leaves event/source unchanged, same/different-key concurrent clients, lost response, schedule/severity replacement, obsolete generation rejection                                                                                                              |
| Catch-up              | first open, long disconnection, muted then enabled, hidden then visible, overdue history, at most one grouped cue, three-item cap, rate limit and local reload dedup                                                                                           |
| Sources               | stale/missing/mismatched snapshots, unreachable optional provider, explicit disabled source, incomplete pagination, late response after mission/leg switch; no false all-clear                                                                                 |
| Recovery              | real backend restart, two clients reconnect, backup/restore, migration rollback, storage-full/failure, commit crash; no duplicate durable acknowledgments                                                                                                      |
| UI                    | production browser desktop 1920×1080, mobile 390×844 and 844×390; access feed from all four work sections, preserve dirty drafts, keyboard/focus, long titles, no horizontal overflow                                                                          |
| Local delivery        | gesture requirement, enabled/muted/unsupported/rejected sound and vibration, hidden page throttling, close/unmount cleanup; no external requests                                                                                                               |
| Existing behavior     | real #349 synthetic leg switch/completion/archive, unchanged mission-package/export hashes, Overview layout/history/POIs and Missions workflows                                                                                                                |

Use two real browser contexts for concurrency. Capture request destinations and
run the synthetic product network without external access; the unavailable
provider must fail locally and cannot block the feed. Capture sanitized
desktop/mobile screenshots, event/ack examples, deterministic scenario results,
browser traces, backend/frontend tests, build/lint results, image SHA and exact
candidate commit. No real aircraft itinerary, terminal, phone number, IP address
or sensitive mission content belongs in fixtures, logs or captures.

Before any runtime check, record process/session ownership, Compose project,
networks, private volumes and temporary paths. Bound all test/build commands
with wall-clock timeout and termination grace. Resource-owning runners install
signal cleanup, close browser contexts, stop/reap workers and remove their
isolated stack. Verify owned processes, listeners, containers, networks and
disposable volumes are gone after checks, including failures. Preserve evidence
and the open-PR worktree. Synthetic acceptance establishes software behavior
only, not aircraft readiness.

## Delivery and review boundary

The written specification and plan were approved in PR #379 comment 6244505182,
and the user selected native execution. Implementation stays in the issue worktree
and draft PR #379 targets `dev`. Product review, applicable exact-head CI and fresh
production acceptance precede merge. Keep #369 allocation, #370 export and #376
layout consolidation separate.
