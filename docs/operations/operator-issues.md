# Operator issues and manual capabilities

The gated Operator workspace contains an exception board for one mission manager
or counterpart. Overview remains a passive customer display. Operator is
disabled by default; enable it using the existing local Operator settings.

## Record a problem

Choose a mission, open Issues, enter a short description and select Save issue.
Priority, affected capability, functional area, responsible party, follow-up,
relationships and notes are optional. An issue is mission-scoped by default and
remains visible across flight legs. Optional details support other scopes.

Open, Monitoring, Resolved and Reopened are separate states. Mitigation and
workaround are independent: a monitoring workaround does not mean the problem is
resolved. Resolve clears the current follow-up; Reopen does not resurrect an old
deadline. These actions do not close calls/conferences or change capability
assessments, transport routing or planning outages.

## Updates, corrections and audit

Add update / follow up opens a brief editor. Normal actions require no audit
explanation. Optional UTC action time supports retrospective entry; blank means
timing is unknown. Save feedback follows the backend receipt, with current-state
reread separate from acceptance.

Issue activity shows operational messages once. Correct this update replaces the
selected historical message at its corrected occurred UTC and labels it
Corrected and Entered later when appropriate. A correction after resolution does
not resolve the issue again or reopen it. Audit history preserves original text,
replacement, reported times, recording times, operator provenance and versions.

The normal `operations/activity.jsonl` remains revision-oriented, ordered by
acceptance sequence. Optional `issue_update` metadata carries root/replacement
identities and selection at the captured watermark. AAR consumers must select
`is_selected` messages and order them by `effective_at` for the operational
message timeline; the original/correction rows are not two independent messages.
Unknown effective times remain unknown. See the
[timeline contract](../superpowers/specs/2026-10-18-operator-issues-timeline.md).
Mission-package integration remains the separate export slice.

## Capability and redundancy

Manual capabilities have independent functional and redundancy statuses. Both
support Unknown; each has its own observation UTC and precision. Assessing
redundancy must not freshen a previous functional check. Recording time and
immutable history remain separate from observation time.

These are operator-reported assessments. Functional secure voice with
unavailable backup is valid. Neither a TV image, a conference status, modeled
satellite availability nor telemetry establishes aircraft readiness. Missing
assessments remain unknown. Duplicate names are separate records, not
automatically merged.

## Snapshot follow-ups and recovery

Follow-up UTC is optional and can be rescheduled or cleared. A compact Operator
summary and issue rows show the backend-derived state at the labeled UTC
snapshot. Refresh issues/summary after time advances; this is not live delivery.
Due and overdue cues are inactive for resolved/removed issues. Incomplete,
unavailable and stale snapshots cannot establish that there is nothing due. Live
reevaluation and notifications belong to the subsequent alert slice.

Unsent #367 drafts remain in this browser tab's session storage, scoped to
store, epoch, source, mission and record. An uncertain command retains its
frozen body and idempotency key together across reload. Retry reuses that exact
request. Older-epoch commands are quarantined; reread and reconcile explicitly.
Conflicts preserve the local draft and show the saved version; deliberately
discard it or review it before applying it to the current version. No automatic
overwrite. Storage failures are visible; keep the tab open if durable draft
storage fails. Do not put operational text in console logs or support
screenshots.

## Storage, retention and rollback

This slice extends typed payloads in the existing #362 SQLite store. It adds no
parallel database or SQL migration. Optional payload fields default when reading
legacy records and receipts. Relationship indexes and recovery use the existing
transactional link mechanism. A referenced record cannot be removed until its
issue relationship is deliberately cleared. Removal is a retained tombstone, not
secure erasure; retain the established local backup/record policy.

Take and verify a #362 backup before rollout. Disabling Operator preserves its
records. Older strict software is not guaranteed to read expanded payloads: for
backout, restore the pre-upgrade backup into a separate configured store, retain
the newer store securely and identify the later records excluded by that backup.
Never strip fields or rewrite immutable revisions/receipts in place.

Acceptance uses synthetic data, deterministic UTC, production Docker/Nginx and
desktop/mobile browsers. It establishes software behavior, not aircraft
readiness.
