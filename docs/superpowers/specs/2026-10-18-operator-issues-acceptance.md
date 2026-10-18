# Operator issues interaction and acceptance contract

Part of the proposed
[issue #367 specification](2026-10-18-operator-issues-design.md). Status:
conditionally approved for planning in PR #378; the timeline contract
incorporates the review clarification. No implementation execution or merge
approval.

## Mobile and desktop interaction

Extend the existing Operator shell with Issues, without a shell redesign.
Opening Issues shows unresolved records first, follow-ups ordered by UTC then
priority, and a collapsed Resolved group. Open, Monitoring and Reopened remain
visibly different. Within equal follow-up times, priority orders Urgent, High,
Normal, Low, then unspecified; final tie-break is record ID. Unscheduled active
issues follow scheduled ones. History and removed records remain accessible.

Quick entry is a visible description input and Save. With a mission selected,
typing and saving requires no additional field interaction. Priority,
mitigation, relationships, responsibility, timing and notes live under optional
details. There is no required operator identity. Existing mission/scope context
is shown.

Each issue exposes Add update, Follow up, Monitoring/Return to open, and
Resolve; Resolved exposes Reopen. Adding an update takes one composer and Save.
Follow up offers UTC date/time, a short relative preset and Clear, then Save.
Capture a relative preset against shared snapshot time once; visibly label the
resulting UTC time, including date across midnight. Resolve/Reopen is a single
deliberate tap with pending feedback, no mandatory confirmation or note.
Workaround and mitigation controls are optional and independent of lifecycle
controls.

Capability rows show two labeled statuses, independent observation times and a
brief optional note. Assessing one dimension must not require entering the
other. Provide accessible labels, touch targets, keyboard operation and a narrow
layout with wrapping; verify portrait and landscape without horizontal page
overflow.

Preserve drafts and entered updates across failed requests, refresh/reconnect
and section navigation, using existing store-bound draft conventions. Scope
draft identity to store/source/mission/record, never display another mission's
draft. Browser reload recovery must retain unsent text through the existing
draft storage mechanism, extending in-memory-only paths with store-bound session
storage where necessary. Draft storage is local operator data, not telemetry or
logs. Changing store identity quarantines drafts rather than silently submitting
them. Do not discard an unsaved update when another client refreshes the saved
record.

## Mutation, recovery and compatibility

Use the existing UUID idempotency key and store epoch. Freeze the full request,
captured action times and key for uncertain retries. Saved appears only after
receipt acknowledgment; reread current state because another client may have
edited afterward. A lost acknowledgment can replay the same receipt without a
duplicate update. Version conflicts show saved versus local intent, preserve the
draft, and require explicit reconciliation; no silent last-write-wins or
automatic application of Resolve to newly changed state.

Public writes add only issues and the assessment journal subtype. Risk and
transport-report write gates remain closed. Preserve strict unions, request
limits, no-store headers, input sanitization and existing LAN boundary. Optional
external feed failure cannot prevent journal editing; local storage failure
cannot falsely confirm a save. #348 modeled predictions and #349 lifecycle
provide context only, never write assessments or resolve problems.

No SQL schema change is planned: existing payload JSON and issue record type
hold these fields, and current_links already stores typed relationship strings.
Do not edit migration 001 or historical JSON. New optional payload fields
default when reading legacy records and receipts. Recovery uses the new
typed-link derivation; preexisting stores cannot have public issue links or
assessment subtypes from this slice, so no backfill is required. Test internal
legacy issue fixtures and receipts as well as new public writes. An unexpected
durable-schema need requires an explicit specification amendment before
implementation.

Payload expansion is forward-compatible for this application version, not a
promise that older strict readers can open newly written payloads. Before
rollout, take and verify a #362 backup. Disabling Operator stops access without
deleting records. To run old software against a writable Operator store, restore
the verified pre-upgrade backup into a separate configured store and retain the
newer store for recovery; never strip fields or rewrite journal/receipts in
place. Document post-backup records excluded by that rollback and preserve them
securely.

Reuse existing local record retention, backup, removal and draft boundaries; no
new retention scheduler or export path. Tombstones preserve history and are not
secure erasure. Keep records/drafts out of application logs and repository
fixtures; retain only synthetic sanitized evidence. Existing projections may
contain the new typed records through generic journal behavior, but production
mission-package wiring is explicitly #370. Baseline export fixtures remain
unchanged.

## Aircraft-free acceptance and evidence

Use the existing isolated production Docker/Nginx acceptance runner and #362
synthetic clock/mission fixtures. No aircraft, terminal, actual itineraries,
external notifications or live provider is required. Include a deliberately
unreachable optional feed and exercise real #348/#349 interfaces using synthetic
positions, times and leg transitions rather than replacing their public
contracts.

Required backend contract/unit/integration controls:

- Description-only creation; all optional null/default cases; strict enums,
  lengths, timestamp precision, malformed/naive/future actual times and past
  follow-ups. Legacy issue revisions/receipts still read and replay.
- Open, Monitoring, Resolved and Reopened; mitigation/workaround independence;
  automatic reasons; timestamped updates; retrospective correction of an older
  message while current state remains Resolved; no mandatory audit note.
- Both capability dimensions Unknown; functional service with unavailable
  backup; one-dimension update retaining the other's time/status; independent
  duplicate labels; immutable correction history and no readiness inference.
- Frozen UTC boundary tests before/equal/after follow-up; clearing/rescheduling;
  resolve suppression/clearing, reopen without deadline resurrection, unknown
  clock and pagination/error states. No timer-generated durable events.
- Correct an update after resolution using the linked timeline contract: one
  operational update at corrected UTC, entered-later labeling, unchanged
  resolution/follow-up, retained superseded text in audit, deterministic
  correction chains, pinned-watermark behavior and normal activity lineage
  without requiring audit export.
- Optional typed relationships, cross-mission rejection, removed/missing
  targets, reverse-reference checks, restore and index-recovery consistency.
- Same-key retry after lost acknowledgment, changed-content idempotency
  conflict, two-client version conflict, store epoch change, rollback on failed
  write, process crash/restart, backup/restore and recovery without duplicate
  revisions.

Required production browser journeys at 1920×1080, 390×844 and 844×390:

1. Log a synthetic preflight failure using only description. Record functional
   secure voice with unavailable redundancy and another assessment left Unknown.
2. Add a workaround update, move to Monitoring, set follow-up, switch to another
   Operator section and refresh at deterministic due/overdue boundaries. Check
   the passive summary and return link; no live-delivery claim.
3. Advance through two synthetic flight legs. The unresolved problem and
   manually reported statuses remain intact; modeled availability changes do not
   edit them.
4. Reschedule and clear follow-up; resolve, reopen and set a fresh follow-up;
   inspect original times, recorded times and immutable history. Correct an old
   update without accidentally replacing current state.
5. Two desktop/mobile clients edit the same issue and assessment. Demonstrate
   conflict preservation, explicit reconciliation and consistent rereads.
6. Drop a mutation response after commit, retry, disconnect/reconnect, navigate
   with an unsent draft and reload. Verify honest pending/failure feedback,
   retained drafts, one receipt and no duplicate update.
7. Restart backend and test store recovery/failure. Saved issues, assessments,
   relationships and deadlines survive; unavailable storage never yields Saved.
8. Compare existing Overview behavior, communications, flight lifecycle and
   baseline mission exports against controls. No new readiness declaration or
   changes to planning outage assumptions appear.

Record software versions, exact clean candidate SHA, commands/results, desktop
and mobile sanitized screenshots, deterministic clock steps, failure injection,
store/revision consistency and rollback instructions in a task report. Synthetic
acceptance establishes software behavior only. Preserve evidence with the PR to
`dev`; keep the worktree while review is open. No claim of aircraft validation.

Before resource-owning runs, record command/session, PID/process group, Compose
project, private volumes and temporary paths. Use wall-clock timeout plus forced
termination grace and exit/signal cleanup handlers. Stop and verify all owned
processes, listeners, containers, networks and disposable volumes immediately
after checks, including failures; preserve shared runtime/credentials and other
tasks. This specification preparation starts no runtime resources.

## Review and next stage

The written-spec review in PR #378 permits implementation planning, with the
timeline/projection clarification incorporated in the companion contract. Review
the resulting implementation plan and select its execution method before
implementation. This document itself authorizes no product changes, dependency
installs, deployment, merge or live notification work.
