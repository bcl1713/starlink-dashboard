# Operator communications requirements and call corrections

Issue: #365. Parent: #361. Status: design direction approved; written
specification awaiting review. Base: origin/dev at 03c78419.

## Purpose and scope

Give the single mission communications operator a short desktop/mobile flow for
planning customer calls, changing their schedule, and recording calls that
already happened. Preserve unknown details. Use the existing gated Operator
workspace and backend-owned SQLite journal from #362, shell from #363, and
display tools from #364. Keep Operator disabled by default.

This slice delivers requirements and call records, not conference lifecycle,
participation tracking, unified alerts, routing actions, or operations-package
ZIP wiring. Those remain #366–#370. Existing journal projections must include
these records and their corrections. Overview and Missions retain their
behavior.

## Architecture and alternatives

Extend the existing `call` record and public records API. Reuse transactions,
receipts, expected versions, mission reference locks, current links, recovery,
history, and projections. Separate planning and actual timing within the
existing `RecordTime`; do not create another event store or a parallel mission
model.

A separate requirements store would duplicate synchronization and audit
contracts. Representing everything as free-text call observations would lose
validated timing and reliable reminder derivation. Extending the typed call
record is preferred. Existing `call_observation` journal entries remain readable
and editable without automatic conversion.

## Call contract

Extend `CallPayload` additively with optional party/participant description,
optional ground coordinator, communications kind (`voice`, `vtc`, `other`, or
unknown), and preparation lead minutes. Notes and title reuse `PayloadBase`. Use
bounded text and nonnegative bounded integer validation. The editor derives a
title from the party for quick creation; it does not require a separate title.
Historical records without the new fields remain readable with unknown values.

Statuses are tentative, scheduled, delayed, cancelled, and completed. Retain the
existing serialized spelling `cancelled`; display “Canceled” in the UI. Status
changes are explicit and reversible edits, not time-triggered mutations.

The existing `time.planned_start_at` is scheduled UTC; `planned_end_at` is
optional and derives from optional duration. Null end means unknown duration,
not zero. Preparation lead defaults to ten minutes for newly planned
requirements, can be zero, and can explicitly be unknown. Do not infer a
historical lead value for old records. Tentative/delayed records may have
unknown planned timing; scheduled creation requires a planned start. Time and
party alone suffice in the quick flow.

### Preparation lead omission and round-trip contract

The serialized field is `payload.prep_lead_minutes`. Separate public
create/update DTO handling from the persisted/read model so a model default
cannot invent a historical value:

| Context                                   | Missing key                                          | Explicit `null`        | Explicit `0` or positive integer                          |
| ----------------------------------------- | ---------------------------------------------------- | ---------------------- | --------------------------------------------------------- |
| POST new tentative/scheduled/delayed call | Normalize to `10` before executing the command       | Unknown; retain `null` | Retain supplied value                                     |
| POST new completed/cancelled call         | Normalize to `null`                                  | Retain `null`          | Retain supplied value; status suppresses preparation cues |
| Stored legacy revision or receipt         | Interpret as unknown, never `10`                     | Unknown                | Retain supplied value                                     |
| PUT full call replacement                 | Reject with 422; require an explicit value or `null` | Save unknown           | Save supplied value                                       |

Use the nullable unknown default only in persisted/read models. Create defaults
belong exclusively at the public create boundary, before command hashing and
transaction execution. Retrying an omitted-key create must normalize identically
and replay its original receipt even after later corrections. Do not change the
existing receipt-hash/replay contract for journal entries.

API record reads expose a legacy missing lead as `null`; raw historical JSON,
original receipts and raw journal projections retain their original missing key.
No read, backup or recovery operation writes a default into accepted history. A
subsequent correction creates a new revision with explicit `null`, unless the
operator intentionally chooses a numeric lead. Remove/restore copies the
retained unknown semantics and never invokes create-time defaulting.

The new planned-call form starts at `10`; the retrospective form starts at
`null`. Edit initialization maps a missing lead to `null` and preserves explicit
`null` and zero (never use truthiness or `value ?? 10` to initialize an edit).
Every call PUT includes the field. Unrelated edits, schedule shifts, status
changes, and conference relinking preserve its value. Changing an existing
retrospective call to a planned status does not silently assign a lead; the
operator can select one.

Actual start/end use `occurred_at`/`ended_at` independently of planned values
and server `recorded_at`. Retain the existing precision/end-state validation and
acceptance-clock tolerance. Unscheduled completed calls may have entirely
unknown actual timing, or a known start with unknown end. End-only input is
rejected by the existing interval contract, with an actionable validation
message. UTC dates are explicit, including calls crossing midnight; never infer
the next day silently.

“Log unscheduled/completed call” creates a completed call with null planned
times and null preparation lead. Party, coordinator, conference reference, and
note are optional; use a generic title if the party is unknown. Completing a
previously scheduled call retains its planned timing for comparison. Planned and
actual times remain separately labeled in every editor, detail view, history,
and projection.

Retain optional `conference_id` and existing typed same-mission dependency
checks. An unavailable conference selector does not require an invented
reference. Editing, completion, relinking, removal, or restoration of a call
must never mutate a conference. Existing protection against removing a call
referenced by participation records remains; explain dependency conflicts rather
than cascading deletion.

## Public API and persistence

Expose typed call create/update through `/api/v2/operator/records`, alongside
the existing journal DTOs. Expand public writable types only to journal entries
and calls, including remove/restore. Keep conference/issue/transport writes
private. Updates cannot convert record types. Preserve strict input validation,
payload size bounds, no-store responses, sanitized errors, and disabled-feature
behavior.

All writes require the existing epoch and UUID idempotency key; updates and
remove/restore require expected version. Repeated identical requests return the
original receipt, changed payload with reused key conflicts, and stale versions
return an explicit conflict. Append complete immutable revisions
transactionally; never rewrite accepted history. Existing activity diffs capture
old/new planned times and payload fields. Audit reasons may be supplied but are
not mandatory administrative fields; reuse automatic reasons when omitted.

JSON payload extensions need no new SQLite table. Verify old revisions, receipt
replays, backups, and recovery against the expanded models. Do not rewrite old
revision JSON or receipts to populate defaults. Add migration only if
implementation finds a concrete storage requirement, and revise this
specification first.

Rollback: disable Operator and retain its database/backup. Older binaries with
closed payload models cannot safely read extended records; restore the
pre-upgrade backup before downgrading, preserving the newer store separately.
Document this limitation rather than claiming downgrade compatibility.

## Operator experience and synchronization

Add a Communications section within the existing responsive Operator shell. Show
multiple requirements ordered by planned UTC with unscheduled/unknown items
separate, plus access to completed and removed records. Offer “Schedule call”
and “Log unscheduled/completed call” with short primary fields and optional
details. Use existing mission/leg/between-leg scope controls and reference
validation.

Editing supports absolute UTC and signed minute/hour shifts, preserving known
duration when shifting a start. For unknown duration, shifting changes only the
planned start and leaves the planned end null. Cancel/reinstate uses an explicit
chosen status; reinstate must not silently mark a completed call scheduled.
Correct timing, participant, note, and association through normal revisions.
Reuse inspectable history and remove/restore controls for calls.

Extend the existing store-bound mutation/retry/reconciliation hook and command
types. Keep drafts through offline failures; show Saved only after receipt.
Disable duplicate submission during an in-flight save. Reuse the same key on an
uncertain retry; require reconciliation for conflicts or epoch changes. A
receipt can predate later edits, so reread current state as the journal already
does.

Refresh on reconnect, window focus, explicit refresh, and successful local
saves. Two clients see saved state on those refreshes; do not claim real-time
push. Retain stale/unavailable and partial-pagination indications, and ensure
lists and summaries do not silently treat the first page as complete. A remote
update never overwrites a local draft; stale saves receive a version conflict.

## Preparation and reminder derivation

Derive preparation time from the latest saved planned start minus the saved
lead. Only active planned calls (tentative, scheduled, delayed) with both known
values have a preparation time. Cancelled, completed, removed, and unscheduled
completed calls have none. Editing schedule/status/lead or restoring recomputes
the value; there is no stored timer to become stale or replay after restart.

Expose preparation UTC and snapshot-relative due/upcoming state using the
backend injected UTC clock/read `as_of`, with deterministic pure derivation.
Past planned starts remain attention items and never imply actual completion or
outage. Label snapshot timing honestly. Live alert delivery, ticking reminders,
and unified feed remain #368; no browser notification permission, external
notification service, or new recurring polling loop is introduced here.

## Verification and evidence

Use wholly synthetic missions, parties, positions, and conferences. No terminal,
aircraft, internet feed, or real contact details are required for simulation.

- Backend unit/contract/integration: quick creation, all statuses, unknown
  fields, interval/lead validation, hours/minutes reschedule, UTC midnight,
  multiple calls, reminders after edits, history before/after values, public
  type restrictions, duplicate and concurrent writes, restart/recovery, backup
  and projection reads.
- Backend preparation-lead contracts: cover every cell in the omission table,
  omitted-key POST replay after correction, legacy read without stored JSON or
  receipt changes, rejected omitted-key PUT with no new revision, and correction
  of a legacy call to explicit null. Verify remove/restore never defaults a
  lead.
- Deterministic retrospective case: clock at 1600Z, log 1430–1442Z; correct
  actual end and participant; verify current view, immutable history and
  projection; remove/restore and relink across valid scope/leg boundaries; no
  preparation or reminder is invented and a shared synthetic conference stays
  unchanged.
- Explicit timing assertions: shifting unknown-duration requirements by positive
  and negative hours/minutes leaves planned end null, including midnight
  crossings. Correcting and removing/restoring the retrospective case leaves
  both planned times and lead null, with no preparation/reminder before or after
  restart.
- Frontend tests: mobile quick entry, unknown duration, UTC input/shift
  controls, corrections, status actions, history, conflict reconciliation,
  uncertain retries, offline save errors, store changes, reconnect/focus refresh
  and pagination.
- Frontend edit-round-trip tests: legacy missing, explicit null, zero and a
  positive lead each survive edit/save/reopen and unrelated field/status
  changes; the PUT always includes the intended value. New planned entry alone
  defaults to ten; retrospective entry/correction/restore never acquires that
  default.
- Fresh exact-commit production Docker/Nginx browser acceptance: desktop
  1920×1080, mobile 390×844 and 844×390, two clients, deterministic clocks,
  restart, unavailable optional provider, failures and recovery. Capture
  sanitized views and machine-readable evidence. Verify unchanged Overview
  behavior and existing mission export contracts; inspect journal projections
  without claiming #370.
- Run required formatting/lint/backend/frontend/static checks on the final head.
  Record test versions and limitations; simulation does not prove aircraft
  readiness.

Use a task-specific Compose project and ownership manifest. Bound commands with
wall-clock timeouts and termination grace. Resource-owning runners clean up on
exit/signals. Verify task processes, listeners, containers, networks and private
volumes are gone after checks; preserve evidence and the open-PR worktree only.

## Delivery

Implement on `feat/operator-communications` in `.worktrees/issue-365`, based on
`origin/dev`. Push a PR against `dev` with verification evidence, compatibility
and rollback notes. Do not merge without the applicable review/check gates.
Remove the task worktree and feature branches after an authorized merge.
