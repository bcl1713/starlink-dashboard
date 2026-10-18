# Issue update timeline and activity projection

Part of the [#367 design](2026-10-18-operator-issues-design.md). Incorporates
the
[conditional review in PR #378](https://github.com/bcl1713/starlink-dashboard/pull/378#issuecomment-6243627474).
Status: clarification for approved implementation planning, not execution or
merge.

## Immutable correction lineage

An operational update is identified by its original
`(store_id, record_id, version)`. `corrects_version` references an earlier
revision of the same issue that contains a nonblank update. It may reference the
original or an earlier correction; resolve the chain to the original root.
Require a strictly smaller version and reject missing, removed, cross-record or
empty-message targets. The replacement update must also be nonblank. Empty text
is not message deletion; corrections remain inspectable and existing
remove/restore semantics are unchanged.

Each correction supplies the complete replacement message and its corrected
occurred time (`corrected_update_at`, null when unknown). Apply existing UTC
future-time tolerance. Preserve current lifecycle, mitigation, follow-up,
associations, title, note and RecordTime exactly; only update text and
correction fields may differ. Enforce this on the backend, not only in the UI. A
request mixing historical correction with status edits is a validation error;
save those as separate deliberate actions. Automatic reason: “Issue update
corrected.” No required explanatory note. Later ordinary actions reset
correction fields to null and start with an empty update composer.

At pinned watermark H, the latest accepted correction in a root's chain supplies
its displayed text/time. Acceptance sequence, not occurred time, decides which
correction wins. Two clients still require the issue's current expected_version;
there is no independent last-write-wins message editor. Correcting any earlier
member keeps the same root, and never creates a second operational update.

## Normal timeline and audit

Fold complete issue revision history at one pinned H before chronological
sorting. Emit one update per root, using the selected replacement's effective
UTC, text, identity, operator provenance and backend recording time. Keep
original root identity, original occurred/recorded times, selected correction
identity and the correction chain accessible in details. Label corrected
messages “Corrected” and “Entered later” with the correction's recorded UTC.
Unknown effective times form a visibly unknown-time group, never a fabricated
chronology. Sort known times ascending, then original root journal_seq; sort
unknown times by root seq.

Keep lifecycle activity separate. The actual Resolve revision remains a Resolve
at its reported action time. A subsequent message correction is not a new
resolution, reopening or fresh operational update. The ordinary timeline does
not show the superseded message as another event. Full audit/history still shows
every original and replacement revision with its real acceptance sequence and
old/new values. Incomplete history cannot claim a fully reconciled timeline;
show partial/loading state until all pages at H are available.

## Normal operations/activity.jsonl contract

The #362 projection currently emits one ActivityItem per revision in journal_seq
order, with identity, time, recorded_at, changes and optional full audit
separately. Preserve that revision-oriented ordering and identity contract. Do
not silently remove old rows or reorder the JSONL by corrected occurrence time.

Add optional `issue_update` metadata only to issue revision rows containing an
update or correction. Omit it for other activity rows, preserving nonissue
projection bytes. It contains:

| Field               | Meaning                                                                |
| ------------------- | ---------------------------------------------------------------------- |
| `kind`              | `update` or `correction`; correction is not lifecycle activity         |
| `root_identity`     | Original update RevisionIdentity                                       |
| `corrects_identity` | Referenced prior RevisionIdentity, or null for original                |
| `selected_identity` | Winning revision identity at H for this root                           |
| `superseded_by`     | Next accepted correction identity in this lineage, or null             |
| `effective_at`      | This row's original or corrected update UTC, nullable                  |
| `text`              | This row's update text                                                 |
| `is_selected`       | True only for the selected root/replacement at H                       |
| `entered_later`     | True when effective UTC precedes recorded UTC; unknown if time unknown |

Consumers render operational updates by selecting `is_selected` rows, grouping
by `root_identity` and sorting by effective time as above. A selected correction
represents the original logical update; it is never a new status action.
Superseded rows remain explicit revision provenance, not independent operational
updates. Without audit.jsonl, a consumer can reconstruct replacement lineage and
original/corrected times, text and recording provenance from normal activity.
The correction row's normal `time` still describes unchanged current issue
state; `issue_update.effective_at` describes the historical message. Do not
conflate them. Its `changes` must contain no lifecycle/time/follow-up
differences. Frontend and projection tests share synthetic expected lineage, not
independently chosen rules.

Metadata is derived at H; a later capture can mark a formerly selected row
superseded without mutating any journal revision. Document this additive
activity contract extension and test old ActivityItem payloads with metadata
absent. Current-state serialization, full audit bytes, checksums and capture
invariants retain their existing meanings. Mission ZIP wiring remains deferred
to the separate export slice.

## Deterministic resolved-issue example and assertions

Use synthetic UTC on 2026-01-02. Version 1 opens an issue at 10:00. Version 2
reports “Backup unavailable” occurred 10:05, recorded 10:06. Version 3 resolves
at 10:20 with follow-up null. Version 4 at recorded 10:30 corrects version 2 to
“Backup intermittent,” occurred 10:04. Version 4 preserves version 3's
state/time.

At H covering version 4, normal UI displays “Backup intermittent” once at 10:04,
labeled Corrected / Entered later (10:30). Resolve remains once at 10:20; status
stays Resolved and follow-up inactive. Audit retains both messages. Normal
activity JSONL retains all four revision rows: version 2 is not selected and
points to version 4; version 4 selects root version 2, references version 2, and
carries effective 10:04 plus recorded 10:30. It has no status/time changes.

Test this with audit both disabled and enabled; a capture before version 4 must
still select the 10:05 version 2 message. Add version 5 correcting version 4,
then a correction targeting version 2: both retain one root and select the
latest accepted replacement. Also test unknown corrected time, same-time ties,
invalid targets, mixed status/correction rejection, two-client conflict, lost
receipt retry and restart without duplicate messages or lifecycle actions.
