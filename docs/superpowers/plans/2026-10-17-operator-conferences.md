# Operator Conferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development if the user
> selects delegation. Steps use checkbox syntax for tracking. Native execution
> approved in PR #377 and conversation; acceptance and merge remain separate.

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

See the
[component file map](2026-10-17-operator-conferences-acceptance.md#component-file-map).

All test commands below have wall-clock limits. Record ownership before starting
processes; on timeout verify/reap the previous owned tree before retrying.
Backend commands run from backend/starlink-location with tracked Python 3.11 and
`uv run --with-requirements requirements.txt pytest`; frontend commands run from
frontend/mission-planner. Do not install dependencies or launch services during
plan review. Each task ends in its own commit after its tests pass.

### Task 1: Typed conference and participation contracts

Execute
[Task 1 steps](2026-10-17-operator-conferences-backend.md#task-1-typed-conference-and-participation-contracts).

### Task 2: Transition, relationship and audit integrity

Execute
[Task 2 steps](2026-10-17-operator-conferences-backend.md#task-2-transition-relationship-and-audit-integrity).

### Task 3: Captured commands and resilient frontend writes

**Files:** Modify frontend `types/operator.ts`, `services/operator.ts`,
`hooks/api/operatorReadSession.ts`, `hooks/api/useOperatorJournal.ts`; create
`components/operator/conferenceCommands.ts` and `.test.ts`; extend hook tests.

**Interfaces:** Export `ConferenceInput`, `ParticipationInput`, and expanded
OperatorInput/OperatorPayload. Define `ConferenceAction` as establish/verify/
interrupt/restore_connection/close. Export

```ts
conferenceCommand(record: SavedRecord, action: ConferenceAction, now: string): OperatorCommand
```

, `joinCommand(input: ParticipationInput, now: string): OperatorCommand`,

```ts
leaveCommand(record: SavedRecord, state: 'left' | 'interrupted', now: string): OperatorCommand
```

, and `resumeCommand(record: SavedRecord, now: string): OperatorCommand`.
Invalid operational preconditions throw a local actionable error before
submission; normal full-replacement editing still supports retrospective
corrections.

- [ ] Write `conferenceCommands.test.ts` cases asserting Establish/Restore clear
      verification, Verify leaves customers untouched, resume emits create with
      predecessor and new start, unknown-start Leave retains null times, and
      invalid quick-action transitions cannot submit. Call payload/lead values
      must remain byte-for-byte unchanged because these commands never update
      calls.
- [ ] Run

```sh
timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceCommands.test.ts
```

confirm new builder tests fail before implementation.

- [ ] Implement builders with captured UTC strings and explicit nulls.
      Generalize hook/read filter types to the two new record types; reuse
      pending key/epoch, current-state reread and store-bound drafts. Never
      regenerate now on retry.
- [ ] Extend hook tests with held create receipt, intervening second-client
      edit, retry after restart and epoch changes. Assert one record, original
      receipt, current reread and no false Saved on uncertain outcomes.
- [ ] Run

```sh
timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceCommands.test.ts src/hooks/api/useOperatorJournal.test.tsx src/services/operator.test.ts
```

require PASS. Commit `feat: add resilient conference operational commands`.

### Task 4: Supported modeled restriction snapshots

**Files:** Modify frontend `services/timeline.ts`; create
`components/operator/conferenceProtection.ts`, `.test.ts`,
`hooks/api/useOperatorProtection.ts`, and `.test.tsx`.

**Interfaces:** Add optional impacted_transports and call_capability_revision to
existing Timeline types. Export
`LegProtectionSource = { legId: string; timeline: Timeline | null }`,

```ts
ProtectionSnapshot = { asOf: string; coverage: 'available' | 'partial' | 'unknown'; items: ProtectionItem[]; limitations: string[] }
```

ProtectionItem carries legId, source kind/IDs/revision, start/end UTC,
classification, transport relevance and associated participation ID.

```ts
deriveProtection(records: SavedRecord[], sources: LegProtectionSource[], asOf: string, recordsComplete: boolean): ProtectionSnapshot
```

is pure.

```ts
useOperatorProtection(missionId: string, records: SavedRecord[], asOf: string, recordsComplete: boolean)
```

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

```sh
timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/conferenceProtection.test.ts src/hooks/api/useOperatorProtection.test.tsx
```

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

```sh
timeout --kill-after=10s 10m npm run test:unit -- src/components/operator
```

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

Execute
[Task 6's full steps and interfaces](2026-10-17-operator-conferences-acceptance.md#task-6-real-offline-integration-and-production-browser-evidence).

### Task 7: Operational documentation and final review

Execute
[Task 7's full steps and interfaces](2026-10-17-operator-conferences-acceptance.md#task-7-operational-documentation-and-final-review).

## Plan self-review

All specification sections map to Tasks 1–7: domain/time/provenance (1–3),
protection and exact source coverage (4), operational UX (5), real integrations
and failure/restart evidence (6), rollout/backout and delivery (7). Each Review
Focus item has an owning test step. Task 2 explicitly separates snapshot API
validation from operational button preconditions; Task 4 exports the snapshot
consumed by Task 5. No second store, generic action engine, routing schedule,
notification infrastructure or UI redesign is planned. Implementation has not
started; checkboxes are intentionally unchecked.
