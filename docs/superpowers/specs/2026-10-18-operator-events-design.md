# Operator event feed and local alerts

Issue: [#368](https://github.com/bcl1713/starlink-dashboard/issues/368). Parent:
[#361](https://github.com/bcl1713/starlink-dashboard/issues/361). Status: review
clarifications approved in PR #379 comment 6244505182; native implementation
authorized by the user. Product acceptance, final review and merge remain
separate. Base: `origin/dev` at `30d628c8`. Branch: `feat/issue-368-events`.

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

The adapter consumes published snapshots or invokes the existing calculation
path with captured local inputs. The normal production adapter may materialize
the shared local #348 status publication under source admission; it does not
publish map POIs, write mission plans, call external providers, or advance the
telemetry/replay coordinator. It uses the same PoP producer as status. Inactive
legs retain saved planning timelines unless they previously supplied an active
operational occurrence that must retire. Live evidence applies only when its
mission, leg, source mode and lifecycle identity match. The production source
contract is detailed in the
[review follow-up plan](../plans/2026-10-18-operator-model-alerts.md).

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

Airborne transport restriction timing follows the
[live route ETA integration](2026-10-18-operator-live-eta-design.md). Planned
UTC is preflight/reference data; live display and alert thresholds share the
same refreshed ETA. This supersedes the former mission-UTC airborne time basis.

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
occurrence. Legacy models without boundary geometry reconcile uniquely
overlapping windows in the same family; ambiguous split/merge results supersede
predecessors and remain visual until two consistent fresh captures establish an
actionable candidate. Never merge by title alone. Source revisions are retained
as evidence, not notification generations.

Live route ETA refreshes preserve the geographic occurrence and acknowledgment;
new route/boundary geometry replaces it. For other modeled events, keep the
accepted notification anchor and severity in the ledger. Timing drift below five
minutes updates display without re-arming. A shift of at least five minutes must
persist for two consecutive fresh captures at least 15 seconds apart before a
replacement generation is accepted. Compare to the accepted anchor, not the
immediately previous refresh, so gradual drift is handled. A replacement is
cue-eligible only after the new threshold is crossed; moving an already due
window around does not repeatedly cue. Once retired, a generation cannot become
pending again. New route families obey catch-up and rate limits.

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

Continue with
[acknowledgment, timing and UX](2026-10-18-operator-events-delivery.md) and
[persistence and acceptance](2026-10-18-operator-events-acceptance.md).
