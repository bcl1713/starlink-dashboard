# Operator issues, capability assessments and follow-up

Issue: #367. Parent: #361. Status: specification and native implementation plan
approved for execution in PR #378 comment 6243741682. Timeline/projection
clarification incorporated. Merge requires separate product review and
acceptance evidence. Design direction and the nine requirements were approved on
2026-10-18. Base: `origin/dev` at `86199429`. Branch:
`feat/operator-issues-367`. Worktree: `.worktrees/issue-367`.

## Purpose and scope

Give the mission communications manager an exception board that is fast enough
to use while working on a problem. A short description is the only user-entered
field required to log an issue in the selected mission. All other issue details
are optional. Mission context is inherited from Operator, not another ticket
field. There are no required assignments, audit explanations, acknowledgments,
or readiness approvals.

Distinguish an unresolved problem, its mitigation, a reported customer
capability, and reported redundancy. None is an aircraft-ready declaration. A
functional secure-voice service can have unavailable backup, while an issue is
Monitoring with a workaround. These are independent facts.

Keep the existing Operator feature disabled by default. Preserve Overview as a
passive 10-foot map, Missions planning, display controls, communications
workflows, flight lifecycle and mission package behavior. No new inventory,
dependency graph, task assignment service, transport allocation, notification
delivery, mission export integration or broad UI redesign. Those remain in the
separate notification, allocation, export and UI consolidation slices.

## Existing contracts and approach

Reuse `app/operator` and `/api/v2/operator/records`: SQLite current pointers,
immutable full revisions, UTC timestamps, pinned journal watermarks, store
epochs, optimistic concurrency, idempotent receipts, remove/restore, backup and
recovery. `IssuePayload` already exists internally with Open and Resolved, but
is excluded from the public create/update union and writable-type allowance.
Extend it and expose issue writes through those existing gates.

For capability assessments, add a typed `capability_assessment` subtype under
the existing `journal_entry` record type. It is a first-class validated payload,
not text parsed out of a note. This avoids a new SQLite record-type migration or
parallel issue database. Frontend editors discriminate by payload subtype and
never load an assessment into the generic note editor. Existing note and call
observation payloads retain their current shape and behavior.

Alternatives considered: embedding assessments in issues would require a problem
to record a functional capability and couple resolution to readiness; a separate
database or equipment/capability catalog would add unnecessary ownership and
migration complexity. A typed entry reuses the journal while keeping assessments
independent from issues.

## Issue contract

Retain `record_type: issue`, `entry_type: issue`, the existing title/note
fields, and schema version 1. The description uses `title` (nonblank, maximum
200 characters); optional longer detail uses `note` (maximum 8,000). Extend the
payload:

| Field               | Values and semantics                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `status`            | `open`, `monitoring`, `resolved`, `reopened`; default `open`                                |
| `priority`          | `low`, `normal`, `high`, `urgent`, or null; default null                                    |
| `mitigation`        | `none_reported`, `mitigated`, `workaround`, or `unknown`; default `unknown`                 |
| `functional_area`   | Optional free text, maximum 200 characters                                                  |
| `responsible_party` | Optional free text, maximum 200 characters; no user directory, score or assignment workflow |
| `follow_up_at`      | Optional aware UTC timestamp; null means no scheduled follow-up                             |
| `update_text`       | Optional update for this revision, maximum 8,000 characters; default empty                  |
| `capability_id`     | Optional assessment record ID in the same mission                                           |
| `call_id`           | Optional call record ID in the same mission                                                 |
| `conference_id`     | Optional conference record ID in the same mission                                           |
| `transport`         | Optional `Starshield`, `Ka`, or `X`; context only                                           |

One optional reference of each kind is sufficient for this slice. A capability
assessment can exist without an issue; an issue can exist without any reference.
Optional null text values are distinct from invented default responsibility.
Blank optional text normalizes to null; title validation remains genuine input
validation. Existing payloads missing new fields decode with the listed
defaults.

An issue is mission-scoped by default so it stays visible across flight legs.
Explicit preflight, leg, between-leg and postflight scope remains available in
details using existing scope/leg validation. The board always loads all scopes
for the selected mission; selecting the next leg does not hide an open issue or
change its original association. No leg transition mutates issue status.

## Lifecycle, updates and corrections

Quick actions are Open to Monitoring, Resolve from any active state, and Reopen
from Resolved. Reopen writes `reopened`; Monitoring can return to Open, and a
Reopened issue can move to Monitoring or Resolved. A newly created retrospective
record may describe any supported state. The explicit editor permits correction
of any supported state without requiring traversal of intermediate states.

Mitigation is independent: Monitoring does not imply mitigated, and a workaround
does not resolve an issue. Resolving does not set customer capability, restore
redundancy, close a call/conference or clear a transport failure. Reopening does
not manufacture a new outage or change a capability assessment.

Every action creates one immutable revision through a full replacement and
`expected_version`. Automatic reasons identify issue creation, update,
monitoring, resolution, reopening, mitigation and follow-up changes, including
compound edits. Routine actions need no explanatory audit note. An optional
explanation remains available. Timestamped updates are the `update_text` on
successive revisions, not an unbounded mutable array. A new action starts with
an empty update composer; it does not copy the preceding revision's update as a
new message. The immutable previous message remains in history.

Use each revision's `RecordTime.occurred_at` for the reported effective time of
that action or update, and backend `recorded_at` for acceptance. Quick actions
capture shared UTC now once; retrospective entry allows exact, approximate or
unknown time under the existing RecordTime rules. History distinguishes the
initial problem time from later action times. No separate onset field or
fabricated duration is introduced.

Correcting a previous update appends a replacement revision with an optional
`corrects_version` positive integer identifying an existing nonremoved revision
of this same issue. Normal activity shows the corrected message once; audit
history retains the original alongside its correction. For message-only
historical corrections, the command preserves all current issue fields and
current effective RecordTime; optional `corrected_update_at` supplies the
corrected historical message time, including null for unknown. The UI obtains
current state before submitting and uses its version. These two optional fields
default to null; `corrected_update_at` is valid only with `corrects_version`.
Historical message correction does not replay old issue state or silently reopen
a resolved problem. Correcting current status or details is an ordinary explicit
replacement revision, not historical event replay. No mandatory correction
explanation is added.

The
[issue timeline and projection contract](2026-10-18-operator-issues-timeline.md)
defines correction lineage, chronological display and additive #362 activity
metadata. It is part of this specification, including the resolved-issue
synthetic example and tests. Mission-package wiring remains #370.

## Capability and redundancy assessments

A `journal_entry` with `entry_type: capability_assessment` represents one named
customer capability in a mission. Its title is the operator's capability label
(for example, Synthetic secure voice); no mandatory catalog is introduced.
Payload fields, in addition to PayloadBase, are:

| Field                    | Values and semantics                                                  |
| ------------------------ | --------------------------------------------------------------------- |
| `functional_status`      | `unknown`, `functional`, `degraded`, `unavailable`; default `unknown` |
| `redundancy_status`      | `unknown`, `available`, `degraded`, `unavailable`; default `unknown`  |
| `functional_observed_at` | Nullable UTC time of the functional assessment                        |
| `redundancy_observed_at` | Nullable UTC time of the redundancy assessment                        |

The two observation times are separate because updating backup availability must
not freshen an older functional check. Changing one dimension captures its time
once or explicitly retains unknown time; the other dimension and its time remain
unchanged. A combined assessment can set both. `RecordTime` describes the
action; dimension times describe the manual observations. Backend recording time
and operator-reported provenance remain immutable revision metadata. Observation
times obey the same future-time tolerance as existing actual times, but may be
retrospective, approximate through RecordTime, or unknown. Each dimension's
precision is represented by nullable companion fields
`functional_time_precision` and `redundancy_time_precision`, with values
`exact`, `approximate`, `unknown`; omitted/null defaults to `unknown`. Unknown
precision requires a null dimension time; known precision requires its dimension
time.

Display “Operator reported” beside both statuses, their observation times and
recording time. Unknown timing does not invalidate a manually reported status.
No aggregate aircraft-readiness score, verified-health label, automatic expiry
to unavailable, or inferred backup availability. No assessment means “No manual
assessment recorded,” not failure. Old assessments retain their values with
age/as-of context; age does not prove failure.

The stable record ID is the capability identity. Subsequent assessments update
that record with concurrency checks and revision history; the board offers
existing capability rows before creating another. Renaming does not break links.
Duplicate labels remain separate, visibly distinct records; do not merge or
choose a winner by label. No mission-wide readiness rollup is derived from them.
Corrections append revisions and preserve previous observations. Historical
notes that should not replace current assessments use ordinary journal notes;
there is no new historical assessment event editor in this slice.

## Follow-up derivation and #368 boundary

Follow-up is an optional request to check the issue again, not a deadline
proving an outage. It can be set, rescheduled or cleared independently of status
and mitigation. Permit past times so overdue follow-ups and retrospective
records can be represented. Resolve atomically clears `follow_up_at` in its
replacement; the earlier requested time remains in history. Reopen defaults to
no follow-up and never resurrects a discarded deadline without explicit input.
Public writes with Resolved plus a nonnull follow-up return field validation
rather than save inconsistent state. Legacy resolved data is suppressed
defensively on read.

Derive at a backend-supplied `as_of`, without persisted timer events:

| Condition                               | Follow-up state |
| --------------------------------------- | --------------- |
| Removed or Resolved                     | `inactive`      |
| Active with null follow-up              | `unscheduled`   |
| `as_of < follow_up_at`                  | `upcoming`      |
| `as_of == follow_up_at`                 | `due`           |
| `as_of > follow_up_at`                  | `overdue`       |
| Clock/snapshot unavailable or regressed | `unknown`       |

“Due now” is the equality boundary, not an invented grace period. The UI groups
Due and Overdue as “Follow-up due,” showing “Overdue” with elapsed UTC duration
when applicable. Derived metadata includes `follow_up_at`, `state`, `as_of`,
`record_id` and `version`, attached to issue reads and consistent across detail,
list and history envelopes. History derivation is labeled “at snapshot,” not a
claim that an alert was delivered at that historical time. The pure backend
derivation is the reusable contract for #368; TypeScript consumes its values.

Keep a compact outstanding-follow-up summary visible throughout Operator,
including while working in Communications, Displays or Journal. Link to the
issue; do not open a modal or interrupt work. Refresh using existing save,
refresh, focus and reconnect paths. Show “As of … UTC” and refresh guidance;
there is no new polling loop, notification timer, delivery receipt, sound, push,
badge delivery guarantee or alert acknowledgment. A due time that passes while
the page is idle appears after the next snapshot refresh. #368 owns live
reevaluation and delivery. Partial pagination, failed reads and stale snapshots
must be explicit rather than displaying “nothing due.”

## Associations and validation

Reuse `derive_links`, `current_links`, transactional dependency checks and
recovery index validation for issue-to-call, issue-to-conference and
issue-to-capability. Capability links validate both `journal_entry` type and
`capability_assessment` subtype. Targets must exist, be nonremoved and belong to
the same mission; leg associations need not match because issues can span legs.
Invalid optional links return actionable field/dependency errors; the user can
clear the link and save. No link is necessary to create an issue.

Existing reverse-reference protection applies: referenced records cannot be
removed or moved to an incompatible mission/subtype while referenced. Explain
which issue retains the link and allow unlinking there. No cascade deletion,
implicit unlink, conference closure, capability update or transport action.
Restoring a record revalidates its links. Removed issue links do not block
target removal, matching current tombstone behavior. Transport is a small
optional enum, not a referenced equipment object. No automatic relationship
inferred from telemetry or shared labels.

## Interaction, acceptance and review

The companion
[interaction and acceptance contract](2026-10-18-operator-issues-acceptance.md)
is part of this specification and covers mobile actions, drafts, concurrency,
rollout/backout and the mandatory synthetic production acceptance matrix. Review
both documents before implementation.
