# Operator Conferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development if the user
> selects delegation. Steps use checkbox syntax for tracking. Execution method
> and this plan require user review before implementation.

**Goal:** Deliver #366 reusable conferences, independent customer participation
and supported modeled restriction advisories.

**Architecture:** Extend #362's existing typed records, immutable revisions and
public API. Keep conference, call and participation independent. Read existing
mission-leg timelines for contextual advisories; never infer routing or build a
transport-change scheduler.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLite backend,
React/TypeScript/TanStack Query frontend, pytest/Vitest/Playwright and
production Docker/Nginx acceptance. No new runtime dependency.

**Spec:**
[Operator conferences design](../specs/2026-10-17-operator-conferences-design.md),
including PR #377 source-coverage clarification.

## Global Constraints

- Keep Operator disabled by default.
- No routing execution, routing approval, mutation blocking, external services
  or mandatory acknowledgments are introduced.
- No known duration or completed schedule is required.
- Completing, cancelling, rescheduling, removing, restoring or relinking a call
  never mutates its conference or participation records.
- Unified event feed, automated alerts and notifications remain #368; broader UI
  redesign remains #376; transport allocation remains #369; operations-package
  wiring remains #370.
- UTC occurrence and acceptance times stay separate. Preserve accepted JSON,
  receipts, immutable revisions, epoch guards and expected versions.
- Normal actions need no confirmation dialog or mandatory note.
- Fresh browser acceptance covers 1920x1080, 390x844 and 844x390, wholly
  synthetic data and real #348/#349 integrations.
- Work only in .worktrees/issue-366 on feat/operator-conferences. Primary
  checkout stays on dev. PR #377 targets dev; merge is not authorized by plan
  approval.

## Review Focus

1. Unknown start with a reported connected customer must still protect activity;
   Leave must not invent a start (Tasks 1, 3, 5).
2. Restoring a connection after a retrospective correction must preserve the gap
   and distinguish Restore record (Tasks 2, 3, 5).
3. Partial multi-leg reads or a global status route belonging to another mission
   must never produce all-clear coverage (Tasks 4, 6).
4. A conference closed/interrupted alongside connected customers must show
   continuity unknown on desktop and both mobile orientations (Tasks 5, 6).
5. A lost create response followed by a second client's edit must not duplicate
   participation or overwrite that edit (Tasks 2, 3, 6).

## Execution and file map

Backend contracts: `app/operator/payloads.py`, `api_models.py`, `references.py`,
`commands.py`, `time_models.py`, and `app/api/operator.py`, all beneath
`backend/starlink-location/`. New `app/operator/conference_actions.py` owns
transition validation and automatic audit descriptions without a generic action
engine. Existing recovery/projection modules remain the persistence mechanism.

Frontend types and transport: `src/types/operator.ts`,
`src/services/operator.ts`, `src/services/timeline.ts`,
`src/hooks/api/operatorReadSession.ts` and `useOperatorJournal.ts`, beneath
`frontend/mission-planner/`. New `components/operator/conferenceCommands.ts`
constructs captured commands; `conferenceProtection.ts` contains pure timeline
normalization/overlap logic; `hooks/api/useOperatorProtection.ts` reads
mission-scoped snapshots. `OperatorConferences.tsx`, `ConferenceEditor.tsx`,
`ParticipationEditor.tsx`, `ConferenceCard.tsx` and `ParticipationRow.tsx` keep
each UI responsibility small. Integrate them through existing
`OperatorCommunications.tsx` and history views.

Acceptance extends the existing `tools/acceptance/operator-journal/`
owner/runner, fixtures and probes, with `conferences_probe.py` and
`tests/e2e/operator-conferences.spec.ts`. Documentation goes in
`docs/operations/operator-conferences.md` and a task evidence report directory.

All test commands below have wall-clock limits. Record ownership before starting
processes; on timeout verify/reap the previous owned tree before retrying.
Backend commands run from backend/starlink-location with tracked Python 3.11 and
`uv run --with-requirements requirements.txt pytest`; frontend commands run from
frontend/mission-planner. Do not install dependencies or launch services during
plan review. Each task ends in its own commit after its tests pass.

### Task 1: Typed conference and participation contracts

**Files:** Modify backend `app/operator/payloads.py`, `api_models.py`,
`time_models.py`, `app/api/operator.py`; create
`tests/operator/test_conference_api.py` and `test_participation_api.py`.

**Interfaces:** Produce `ConferencePayload`, `ParticipationPayload`,
`ConferenceCreate`, `ConferenceUpdate`, `ParticipationCreate`,
`ParticipationUpdate` in existing public unions. Conference status is nullable
with unknown interpretation; fields and enums match the spec. Participation adds
nullable `participant`, nullable `state` (unknown/connected/interrupted/left),
and nullable UUID `resumes_participation_id`. Existing target requirement
remains.

- [ ] Write `test_conference_unknown_defaults_do_not_rewrite_history`,
      `test_public_conference_and_participation_roundtrip` and
      `test_connected_unknown_time_can_leave_without_invented_start`. Assert old
      missing fields decode unknown; raw revision/receipt JSON is unchanged;
      unknown identity/duration/schedule saves; end-only is rejected; future
      actual timestamps respect the existing 60-second tolerance. Use existing
      api_helpers.create and record_data/service/api fixtures.
- [ ] Run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/operator/test_conference_api.py tests/operator/test_participation_api.py -q`;
      confirm failures concern new contracts/public type restrictions.
- [ ] Add nullable persisted payload fields; add public DTOs and expand the
      writable set only to journal_entry/call/conference/participation. Validate
      verified_at and configuration_reported_at with existing UTC parser and
      acceptance-clock tolerance. Keep issue/risk/transport-report private.
- [ ] Run the same focused command plus existing `test_call_api.py`,
      `test_api.py`, `test_models.py`, and `test_public_type_races.py`; require
      PASS.
- [ ] Commit `feat: expose typed conference and participation records`.

### Task 2: Transition, relationship and audit integrity

**Files:** Create backend `app/operator/conference_actions.py`; modify
`commands.py`, `references.py`; test in new `test_conference_actions.py` and
existing `test_references.py`, `test_recovery.py`, `test_projections.py`.

**Interfaces:**
`validate_conference_update(current: SavedRecord | None, replacement: RecordInput, clock: Clock) -> None`
enforces invariant timestamp and state combinations on every write.
`conference_audit_reason(current: SavedRecord | None, replacement: RecordInput) -> str | None`
supplies precise automatic reasons after the existing receipt/version guards.
Full-replacement corrections remain valid: these helpers cannot distinguish an
explicit historical correction from an operational command; UI builders in Task
3 guard action-specific preconditions. The API validates content, not an
invented action opcode.

- [ ] Write `test_verification_requires_established_conference`,
      `test_configuration_change_clears_verification`,
      `test_resume_link_rejects_cycles_and_wrong_targets`,
      `test_call_completion_does_not_mutate_conference`, and
      `test_retry_after_remote_edit_replays_original_receipt`. Assert audit
      reasons distinguish connection restoration and tombstone restoration;
      stale versions leave all revisions unchanged. Configuration changes
      carrying stale verification are rejected; valid replacements explicitly
      clear it. Backdated corrections become latest snapshots and preserve prior
      revisions.
- [ ] Run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/operator/test_conference_actions.py tests/operator/test_references.py -q`;
      require relevant new failures.
- [ ] Integrate helpers after receipt/version checks inside the transaction.
      Extend derive_links for resumes_participation_id with explicit expected
      type participation; preserve existing call/conference link semantics.
      Require an interrupted predecessor, identical nullable call/conference
      targets, same mission and no cycle. Evaluate incoming links on corrections
      too; reject an incompatible predecessor correction with
      dependency_conflict rather than silently breaking restoration history.
      Protect referenced predecessors from removal. Unknown identities need not
      match strings.
- [ ] Preserve raw history and receipts. Existing databases cannot contain the
      new predecessor field, so absent legacy fields derive no new links: verify
      recovery with old fixtures without adding a speculative migration. Test
      new predecessor index survives backup/restore, recovery and projections;
      if that premise fails, revise spec before storage changes.
- [ ] Run
      `timeout --kill-after=10s 15m uv run --with-requirements requirements.txt pytest tests/operator -q`;
      require PASS. Commit
      `feat: preserve conference lifecycle and participation audit integrity`.

### Task 3: Captured commands and resilient frontend writes

**Files:** Modify frontend `types/operator.ts`, `services/operator.ts`,
`hooks/api/operatorReadSession.ts`, `hooks/api/useOperatorJournal.ts`; create
`components/operator/conferenceCommands.ts` and `.test.ts`; extend hook tests.

**Interfaces:** Export `ConferenceInput`, `ParticipationInput`, and expanded
OperatorInput/OperatorPayload. Define `ConferenceAction` as establish/verify/
interrupt/restore_connection/close. Export
`conferenceCommand(record: SavedRecord, action: ConferenceAction, now: string): OperatorCommand`,
`joinCommand(input: ParticipationInput, now: string): OperatorCommand`,
`leaveCommand(record: SavedRecord, state: 'left' | 'interrupted', now: string): OperatorCommand`,
and `resumeCommand(record: SavedRecord, now: string): OperatorCommand`. Invalid
operational preconditions throw a local actionable error before submission;
normal full-replacement editing still supports retrospective corrections.

- [ ] Write `conferenceCommands.test.ts` cases asserting Establish/Restore clear
      verification, Verify leaves customers untouched, resume emits create with
      predecessor and new start, unknown-start Leave retains null times, and
      invalid quick-action transitions cannot submit. Call payload/lead values
      must remain byte-for-byte unchanged because these commands never update
      calls.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceCommands.test.ts`;
      confirm new builder tests fail before implementation.
- [ ] Implement builders with captured UTC strings and explicit nulls.
      Generalize hook/read filter types to the two new record types; reuse
      pending key/epoch, current-state reread and store-bound drafts. Never
      regenerate now on retry.
- [ ] Extend hook tests with held create receipt, intervening second-client
      edit, retry after restart and epoch changes. Assert one record, original
      receipt, current reread and no false Saved on uncertain outcomes.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceCommands.test.ts src/hooks/api/useOperatorJournal.test.tsx src/services/operator.test.ts`;
      require PASS. Commit
      `feat: add resilient conference operational commands`.

### Task 4: Supported modeled restriction snapshots

**Files:** Modify frontend `services/timeline.ts`; create
`components/operator/conferenceProtection.ts`, `.test.ts`,
`hooks/api/useOperatorProtection.ts`, and `.test.tsx`.

**Interfaces:** Add optional impacted_transports and call_capability_revision to
existing Timeline types. Export
`LegProtectionSource = { legId: string; timeline: Timeline | null }`,
`ProtectionSnapshot = { asOf: string; coverage: 'available' | 'partial' | 'unknown'; items: ProtectionItem[]; limitations: string[] }`.
ProtectionItem carries legId, source kind/IDs/revision, start/end UTC,
classification, transport relevance and associated participation ID.
`deriveProtection(records: SavedRecord[], sources: LegProtectionSource[], asOf: string, recordsComplete: boolean): ProtectionSnapshot`
is pure.
`useOperatorProtection(missionId: string, records: SavedRecord[], asOf: string, recordsComplete: boolean)`
returns snapshot plus loading/error/refetch.

- [ ] Write tests for half-open boundaries, elapsed planned end, unknown-start
      connected records, overlapping customers, absent transport, source
      duplication, malformed/missing bounds, partial legs, cancelled calls still
      connected, and timeline belonging to another leg. Assert snapshot coverage
      cannot be available with incomplete records; unknown state fields never
      default to available.
- [ ] Add `does_not_invent_operator_transport_change`: changing configured or
      intended transport between two snapshots adds no scheduled routing event;
      coverage copy explicitly excludes operator-planned changes. Assert real
      wire fields from the spec's source table are consumed and ordinary
      continuity does not warn. Existing computed x_fallback/advisory is never
      promoted to outage.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceProtection.test.ts src/hooks/api/useOperatorProtection.test.tsx`;
      require meaningful failures.
- [ ] Implement normalization from per-leg GET timelines only. Read mission legs
      via missionsApi.get; never generate preview, mutate plans or use
      /api/status for selected-mission protection. Explicitly retain source
      computation UTC and unknown freshness/revision alignment; request success
      alone cannot prove fresh planning inputs. Reuse refresh/focus/reconnect
      conventions with no interval. Group source-identical duplicates without
      hiding separate transport consequences.
- [ ] Run the same tests; require PASS. Commit
      `feat: show supported modeled restrictions for protected calls`.

### Task 5: Conference and customer operational UI

**Files:** Create the five UI components listed in the file map with colocated
`.test.tsx` files. Modify `OperatorCommunications.tsx`, `RevisionDetails.tsx`,
`JournalList.tsx`, `JournalHistory.tsx`; extend Communications/history tests.

**Interfaces:** `OperatorConferences({ missionId, onDirty })` owns the new
record hooks and shared snapshot.
`ConferenceCard({ record, participations, onAction })` and
`ParticipationRow({ record, conference, onAction })` display distinct states.
Editors accept input drafts/onChange/onSave and optional existing records using
the same store-bound pending/reconciliation pattern as CallEditor. Narrow
payload unions by entry_type; never cast another record type to a call.

- [ ] Write tests named `joins_before_establish_without_schedule`,
      `conference_close_keeps_customer_connected_with_discrepancy`,
      `restore_connection_and_restore_record_have_distinct_labels`,
      `actions_need_no_note_or_confirmation`, and
      `mission_level_active_records_survive_leg_navigation`. Assert
      role-accessible buttons, visible continuity unknown, separate
      verification/customer labels, optional identity/transport, unscheduled
      records and independent overlapping rows.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator`;
      verify the new cases fail first.
- [ ] Implement compact existing-shell cards/rows, captured command actions,
      optional-details editors and history values. Use Restore connection for a
      new interval and Restore record only for tombstones, including audit
      descriptions. Show discrepancy conspicuously when conference
      closed/interrupted and customer remains connected; no green success
      inference. Keep protection coverage limits visible and keep all controls
      usable when the optional model fails.
- [ ] Fetch all record pages before complete summary claims; preserve pinned
      watermark semantics and mission-level visibility. Refresh related reads
      after acknowledgment; never overwrite an open dirty draft from another
      client's save.
- [ ] Run `timeout --kill-after=10s 15m npm run test:unit`,
      `timeout --kill-after=10s 10m npm run lint` and
      `timeout --kill-after=10s 10m npm run build`; require PASS. Commit
      `feat: add independent conference and customer controls`.

### Task 6: Real offline integration and production browser evidence

**Files:** Extend
`tools/acceptance/operator-journal/{run.py,seed.py,scenario.py,backend_fixture.py,projection_probe.py,export_probe.py}`;
create `conferences_probe.py`, frontend `tests/e2e/operator-conferences.spec.ts`
and `tools/tests/test_operator_conferences_acceptance.py`. Extend existing
operator harness tests/config to run the new journey.

**Interfaces:** `conferences_probe.main() -> None` follows the existing
communications probe convention: read OPERATOR_ACCEPTANCE_ROOT, open the
existing synthetic store, assert projections and print one JSON result. Register
it through qualify's existing probe(module, destination) helper as
conferences-projections.json. The runner invokes it with the same synthetic
clock/store identity. Existing ownership.Owner and browser_control own all
runtime resources; avoid a second runner lifecycle.

- [ ] Add failing harness tests asserting the new journey/probe are invoked and
      source coverage assertions cannot be omitted. Add real backend integration
      tests for timeline generation through the existing #348
      forecast/continuity code and #349 flight event/archive APIs; fixed UTC
      inputs produce deterministic transitions, default Starshield, Ka and
      coordinated X fallback outcomes.
- [ ] Run
      `timeout --kill-after=10s 10m python -m pytest tools/tests/test_operator_conferences_acceptance.py -q`;
      confirm failure before runner wiring.
- [ ] Implement synthetic journeys: reuse conference for two calls with idle
      interval, overlapping calls, both joining orders, unknown
      participant/timing, interruption/new interval, correction, independent
      close/completion, conspicuous discrepancy, two-client conflict, held
      response/offline retry, restart and backup/recovery. Assert unsupported
      operator-entered change remains uncovered.
- [ ] Exercise real preflight/leg activation, synthetic flight transition,
      on-blocks and multi-leg archive/package paths. Inject an unreachable
      optional provider and verify controls survive. Keep baseline Overview
      visibility, history/layout and existing export compatibility assertions.
- [ ] Run focused harness tests and backend integration tests with 10-minute
      limits; require PASS. Commit product/harness changes before exact-SHA
      acceptance.
- [ ] Read cloud Docker runtime instructions and verify actor Docker context
      without clearing DOCKER_HOST. Record ownership then run from repository
      root:
      `timeout --kill-after=10s 60m python tools/acceptance/operator-journal/run.py --candidate "$(git rev-parse HEAD)" --project starlink-issue366 --evidence docs/reports/2026-10-17-operator-conferences/raw`.
      Require successful fresh production-image/Nginx desktop/mobile assertions,
      screenshot capture and machine-readable evidence. No success claim on
      timeout.
- [ ] Verify task processes/listeners/containers/networks/private volumes are
      gone using the runner's scoped host verification. Preserve sanitized
      evidence, not raw contacts/coordinates. Commit
      `test: verify conference workflows in offline production simulation` after
      report preparation in Task 7.

### Task 7: Operational documentation and final review

**Files:** Create `docs/operations/operator-conferences.md` and
`docs/reports/2026-10-17-operator-conferences/README.md`; update
`docs/operations/operator-communications.md` and the specification status only
when execution is approved/completed.

**Interfaces:** Document API payload examples, one-tap workflow, separate
statuses, source/time/coverage table, correction and retry behavior,
retention/export boundary, backup and rollback. No new export or retention
policy is invented.

- [ ] Write synthetic examples for conference reuse, unknown connected customer,
      interruption/new interval and Restore record. State no independent
      call-bearing transport verification, no operator-change correlation before
      #369, and no automatic alerts before #368. Explain saved timeline age and
      partial coverage.
- [ ] Record production candidate SHA, test/tool versions, screenshot links,
      negative/source-coverage assertions and cleanup evidence. Describe
      additive JSON compatibility and pre-upgrade-backup downgrade requirement;
      no untested aircraft readiness claim.
- [ ] Run documented canonical backend/frontend/static checks from
      `docs/contributing/quality-gates.md`, all with explicit wall-clock limits;
      rerun affected checks for fixes. Run Prettier/Markdown checks and
      `git diff --check`. Require all applicable CI gates on final PR head; if
      only documentation changes after acceptance, identify exact tested product
      SHA.
- [ ] Commit documentation/evidence and push feat/operator-conferences. Update
      PR #377 description to the final implemented scope with evidence and
      rollback; request review without merging. Keep the open-PR worktree and
      stop all task runtime resources. Do not close #366 on specification or
      plan approval alone.

## Plan self-review

All specification sections map to Tasks 1–7: domain/time/provenance (1–3),
protection and exact source coverage (4), operational UX (5), real integrations
and failure/restart evidence (6), rollout/backout and delivery (7). Each Review
Focus item has an owning test step. Task 2 explicitly separates snapshot API
validation from operational button preconditions; Task 4 exports the snapshot
consumed by Task 5. No second store, generic action engine, routing schedule,
notification infrastructure or UI redesign is planned. Implementation has not
started; checkboxes are intentionally unchecked.
