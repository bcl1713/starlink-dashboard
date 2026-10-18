# Operator Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution or superpowers:subagent-driven-development if the user
> selects delegation. Execute task-by-task only after plan review and
> execution-method selection.

**Goal:** Deliver #367's fast exception board, independent manual capability
assessments and snapshot-derived follow-up without changing mission readiness.

**Architecture:** Extend #362 payloads, public journal APIs and immutable
revisions. Keep issue update lineage separate from lifecycle events. Reuse the
current Operator shell and owned production acceptance harness; no new
database/service.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, SQLite, React/TypeScript,
TanStack Query, Vitest, Playwright, Docker/Nginx; existing dependencies only.

**Spec:** [Design](../specs/2026-10-18-operator-issues-design.md),
[interaction/acceptance](../specs/2026-10-18-operator-issues-acceptance.md),
[timeline/projection](../specs/2026-10-18-operator-issues-timeline.md).

## Global constraints

- “A short description is the only user-entered field required to log an issue.”
- “Keep the existing Operator feature disabled by default.”
- “No aggregate aircraft-readiness score” and “No required explanatory note.”
- “Mission ZIP integration is still #370.” Live delivery remains #368.
- “Preserve that revision-oriented ordering and identity contract.”
- Keep all new data synthetic; no operational text in console/log/evidence.
- Work only in `.worktrees/issue-367`, branch `feat/operator-issues-367`, PR to
  dev.
- Every test/build has `timeout --kill-after=10s`; owned resources have cleanup.

## Review focus

- Correction of a correction must retain one message root (Task 2).
- A forged message correction must not alter a resolved issue's fields (Task 1).
- Lost receipt plus browser reload must not duplicate an accepted update (Task
  4).
- Partial history/pagination must not imply reconciled activity or no follow-ups
  (Task 5).
- Clearing a single assessment time must not refresh its other dimension (Task
  3).

## File map and verification convention

Backend paths below are relative to `backend/starlink-location`; frontend paths
are relative to `frontend/mission-planner`. Repository tool/docs paths are full.
Add focused modules rather than growing the journal page or command transaction.
All backend commands run in the backend directory, using
`timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest`.
All frontend commands run in the frontend directory, using
`timeout --kill-after=10s 10m npm run test:unit --` followed by named files. An
initial focused run must fail on the missing behavior, not an environment error;
the identical command must pass after implementation. Do not install product
dependencies or execute this plan until the user approves execution.

### Task 1: Public issue workflow and correction validation

**Files:** Modify
`app/operator/{payloads,models,api_models,commands,references}.py` and
`app/api/operator.py`. Create `app/operator/issue_actions.py` and
`tests/operator/test_issue_api.py`; extend `test_references.py`,
`test_recovery.py`.

**Interfaces:** Produce extended `IssuePayload`, public
`IssueCreate/IssueUpdate`,
`validate_issue_update(connection, current, command, clock) -> None` and
`issue_audit_reason(current, command) -> str | None`. Keep existing service
routes, receipt shape, optimistic version check and write transaction ownership.

- [ ] Write failing tests `test_description_only_issue`,
      `test_monitoring_workaround_is_not_resolved`,
      `test_correct_after_resolve_preserves_current_fields`, and
      `test_mixed_correction_and_status_edit_rejected`. Assert Open default,
      null optional fields, independent mitigation, current
      status/time/follow-up retained after correction, 422 for mixed edits, and
      no required audit_note.
- [ ] Run the backend command with `tests/operator/test_issue_api.py -q`; expect
      failure because issues are not publicly writable.
- [ ] Implement payload fields/defaults exactly as the spec; expose only issue
      writes in addition to existing public types. Validate correction targets
      in the same write transaction, earlier version/nonblank text, actual-time
      tolerance and current-field preservation. Add automatic action reasons and
      explicit same-mission typed links with reverse-reference protection.
- [ ] Extend tests for all four statuses, priorities, mitigation, optional
      party, naive/past/future timestamps, empty title, legacy payload/receipt,
      removal and restore, invalid correction targets, same-key retry, stale
      version and rejected cross-mission links. Resolved plus nonnull follow-up
      must fail validation.
- [ ] Run `tests/operator/test_issue_api.py`,
      `tests/operator/test_references.py` and
      `tests/operator/test_recovery.py -q` as backend arguments; expect all
      pass. Commit scoped files as
      `feat: add journal-backed Operator issue actions`.

### Task 2: Corrected issue activity and normal projection lineage

**Files:** Create `app/operator/issue_activity.py`,
`tests/operator/test_issue_activity.py`; modify
`app/operator/{projection_models,projections}.py` and `test_projections.py`.
Create `frontend/mission-planner/src/test/fixtures/issue-corrections.json` as
the shared golden case.

**Interfaces:** `derive_issue_updates` accepts `revisions: list[SavedRecord]`
and keyword-only `store_id: str`, returning `dict[int, IssueUpdate]`. maps
journal_seq to metadata at the caller's pinned H. `IssueUpdate` contains exactly
the timeline spec's nine fields. Optional `ActivityItem.issue_update` is omitted
when absent.

- [ ] Write `test_correction_after_resolution_without_audit` using the specified
      10:00/10:05/10:20/10:30 example. Assert all four JSONL revision rows
      remain, one selected message at 10:04, original root v2, correction v4,
      recorded 10:30, no status/time change on v4, and unchanged
      resolution/follow-up.
- [ ] Run `tests/operator/test_issue_activity.py -q`; expect missing metadata.
- [ ] Implement a two-pass pure fold: resolve strictly earlier correction roots,
      then annotate selection/supersession by acceptance sequence. Capture all
      rows at existing H before deriving metadata. Keep nonissue serialization
      unchanged; no new mission-package route or export worker.
- [ ] Add correction-of-correction and correction-of-root tests, unknown time,
      equal-time ordering, watermark before correction, audit on/off, restored
      records, idempotent replay and byte-identical nonissue projections. Load
      the golden fixture for frontend use; never generate a fixture from live
      records.
- [ ] Run `tests/operator/test_issue_activity.py`,
      `tests/operator/test_projections.py` and
      `tests/operator/test_projection_compatibility.py -q` as backend arguments;
      expect pass. Commit as
      `feat: preserve corrected issue update lineage in activity projections`.

### Task 3: Manual capability assessments and follow-up snapshots

**Files:** Create `app/operator/issue_followup.py`,
`tests/operator/test_issue_followup.py`, `test_capability_api.py`; modify
`app/operator/{payloads,models,api_models,read_metadata,references}.py`.

**Interfaces:** Produce `CapabilityAssessmentPayload` under journal_entry;
`derive_issue_followup` accepts `record: SavedRecord`, keyword-only UTC
`as_of: datetime` and `clock_regression: bool`; returns `IssueFollowup`.
Metadata has follow_up_at/state/as_of/record_id/version.

- [ ] Write `test_functional_with_unavailable_backup`,
      `test_one_dimension_does_not_freshen_other`,
      `test_unknown_time_and_both_unknown`, `test_followup_utc_boundaries`, and
      `test_resolve_clear_reopen_no_resurrection`. Assert the spec's precise
      enums and before/equal/after states, plus inactive removed/resolved
      records.
- [ ] Run `tests/operator/test_issue_followup.py` and
      `tests/operator/test_capability_api.py -q` as backend arguments; expect
      missing capability subtype/follow-up metadata.
- [ ] Implement the typed payload, independent dimension time/precision checks,
      no inference from sources, assessment link subtype validation, public
      subtype protection and pure backend follow-up derivation on
      list/detail/history reads. Inactive/unscheduled states take precedence
      over clock-dependent comparison; unknown clock applies only when an active
      scheduled comparison needs it.
- [ ] Add null precision/time, retrospective observation, duplicate capability
      labels, linked subtype mutation rejection, regressed clock and
      failed-source tests. Assert existing note editor/API payload shapes still
      work.
- [ ] Run these two test files plus `tests/operator/test_read_metadata.py -q`;
      expect pass. Commit as
      `feat: add manual capability and follow-up snapshots`.

### Task 4: Frontend contracts, honest mutations and durable drafts

**Files:** Modify `src/types/operator.ts`, `src/services/operator.ts`,
`src/hooks/api/{operatorReadSession,useOperatorJournal}.ts`. Create
`src/hooks/api/useOperatorIssueDraft.ts` and its `.test.tsx`; extend
`src/hooks/api/useOperatorJournal.test.tsx`, `src/services/operator.test.ts`.

**Interfaces:** Extend `OperatorInput`, `OperatorPayload`, `ReadRecord` and
query record type to issue/assessment support. Draft hook accepts
`{storeId, epoch, sourceMode, simulationRunId, missionId, recordId}` and returns
`{draft, setDraft, pending, setPending, clear, storageError}`. Pending retains
the exact frozen command/key/epoch until receipt reconciliation.

- [ ] Write `test_reload_restores_unsent_update`,
      `test_lost_receipt_reload_replays_one_command`,
      `test_epoch_change_quarantines_draft`, and
      `test_storage_failure_retains_memory`. Assert draft isolation, unchanged
      retry time/key and no false Saved indicator.
- [ ] Run unit tests for the new hook and existing journal hook; expect missing
      durable draft behavior. Implement sessionStorage with explicit keys above,
      no logging, visible storage failure, and quarantined old-epoch drafts.
- [ ] Extend narrow record-type unions and reuse receipt-first mutation/conflict
      paths. Do not silently merge status changes, discard local updates on
      refetch, or label old cached data as newly saved. Restrict new draft
      behavior to #367.
- [ ] Test mission/record switching, failed network, conflict reconciliation,
      accepted save cleanup, explicit discard and separate tab isolation. Run
      hook and service unit tests; expect pass. Commit as
      `feat: preserve Operator issue drafts and uncertain saves across reload`.

### Task 5: Issue board, assessments and corrected operational timeline

**Files:** Create `src/components/operator/OperatorIssues.tsx`,
`IssueEditor.tsx`, `CapabilityAssessments.tsx`, `IssueActivity.tsx`,
`issueActivity.ts` and focused tests beside them. Modify
`src/pages/OperatorJournalPage.tsx` and
`src/components/operator/OperatorBrief.tsx`.

**Interfaces:** `OperatorIssues({missionId}: {missionId: string})` owns issue
queries/editors; `CapabilityAssessments({missionId})` owns typed assessment
rows. `projectIssueActivity(revisions: SavedRecord[]): IssueActivityResult`
folds one complete history at H using the shared golden fixture.
IssueActivityResult has `updates` and `lifecycle`; unknown-time updates remain
separate. Reuse existing history service; incomplete pages keep an explicit
partial state.

- [ ] Write tests for description-only Save, optional details, one-tap Resolve,
      Monitoring/workaround independence, independent assessments, corrected
      text once at 10:04 after Resolve at 10:20, and original text visible only
      in audit.
- [ ] Run the new component and pure activity unit tests; expect missing views.
- [ ] Implement progressive details, optional UTC/relative follow-up controls,
      reschedule/clear, Add update and explicit historical correction. Relative
      times freeze at the shared snapshot. Use existing draft/mutation
      interfaces. Keep the resolved group's controls separate from tombstone
      restore.
- [ ] Add Issues navigation and persistent snapshot-derived follow-up summary
      throughout Operator. Load all mission scopes; no active-leg filtering or
      new timer/polling. Exclude typed assessments from generic journal editing.
- [ ] Test partial records/history, stale/unknown clock, duplicate capability
      names, no horizontal overflow semantics, missing optional links, conflict
      drafts and two-client refresh. Run new tests plus OperatorBrief and
      journal page suites; expect pass. Commit as
      `feat: add responsive Operator exception board`.

### Task 6: Synthetic production acceptance and regression evidence

**Files:** Create `tests/e2e/operator-issues.spec.ts`,
`tools/acceptance/operator-journal/issues_probe.py`,
`tools/tests/test_operator_issues_acceptance.py`; modify
`tools/acceptance/operator-journal/{run,scenario,backend_fixture}.py`,
`frontend/mission-planner/playwright.operator-journal.config.ts` and
`tools/acceptance/operator-journal/compose.yml` only as required for fixture
mounts. Create `docs/operations/operator-issues.md` and a sanitized task
evidence report.

**Interfaces:** Extend existing runner qualification with issues proof including
candidate SHA, viewport, UTC boundary steps, projection lineage and cleanup.
Reuse Owner admission/signal/cleanup; no parallel acceptance stack or new
daemon.

- [ ] Write harness tests requiring issues proof, all three viewports,
      post-resolve correction, offline/lost receipt/restart, spanning leg switch
      and cleanup; run `timeout --kill-after=10s 10m python3 -m pytest` with
      `tools/tests/test_operator_issues_acceptance.py -q`; expect missing proof.
- [ ] Implement the eight specification journeys with deterministic synthetic
      clock steps, two browser contexts and unreachable optional feed. Exercise
      actual #348/#349 contracts; inspect normal activity without audit, then
      with audit. Extend existing failure/restart probes rather than duplicating
      them.
- [ ] Run backend Operator suite, frontend unit suite/lint/build, harness tests
      and canonical static checks with explicit limits. Resolve regressions
      before committing an exact clean product candidate. Record commands and
      versions.
- [ ] After reading cloud Docker guidance, record ownership and run from root:
      `timeout --kill-after=10s 90m python3` with runner
      `tools/acceptance/operator-journal/run.py` and arguments
      `--candidate <full-clean-SHA>`,
      `--project starlink-issue367-<unique-run>`,
      `--evidence <new-private-evidence-directory>`. Expect checksPassed true
      and cleanup proof. Verify actor daemon processes/listeners/resources are
      gone.
- [ ] Preserve sanitized screenshots and results for 1920×1080, 390×844 and
      844×390; document backup/backout and no aircraft-readiness claim. Commit
      docs, push to PR #378 against dev, require final-head checks/review, and
      retain its worktree while open. Merge only when separately authorized.

## Self-review and execution handoff

All nine approved requirements map to Tasks 1–6; correction lineage maps to
Tasks 1, 2, 5 and 6. Review-focus cases have explicit owning tests. New
interfaces stay within the journal and Operator; no migration, notification
service, transport allocation, mission ZIP route or broad redesign is planned.

Plan status: approved for native execution in PR #378 comment 6243741682. Native
execution is recommended because payloads, correction validation and projections
share transaction contracts; sequential implementation avoids interface drift.
Implementation is underway; product review and merge remain separate gates.
