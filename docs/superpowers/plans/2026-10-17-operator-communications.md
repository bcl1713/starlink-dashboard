# Operator Communications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.
> Execution method awaits user selection.

**Goal:** Deliver scheduled communications requirements and retrospective call
corrections for issue #365.

**Architecture:** Extend the existing typed call record and gated records API.
Reuse SQLite revisions, receipts, references and projections; add a focused
Communications editor and deterministic preparation-time derivation within
Operator.

**Tech Stack:** Python/FastAPI/Pydantic/SQLite, React/TypeScript/TanStack Query,
pytest/Vitest/Playwright, production Docker/Nginx.

**Spec:**
[Approved design](../specs/2026-10-17-operator-communications-design.md),
including preparation-lead review clarification. Draft PR #375.

## Global Constraints

- Keep Operator disabled by default.
- Overview and Missions retain their behavior.
- Live alert delivery, ticking reminders, and unified feed remain #368.
- No read, backup or recovery operation writes a default into accepted history.
- Updates cannot convert record types.
- Every call PUT includes the field `payload.prep_lead_minutes`.
- Run all checks with a wall-clock limit and termination grace; record resource
  ownership before starting resources and verify teardown.
- Work in `.worktrees/issue-365`, branch `feat/operator-communications`, PR
  against `dev`.

## Review Focus

1. An old creation receipt replayed after a correction must not overwrite the
   current editor; Task 4 tests this.
2. Malformed numeric input (fractions, booleans, infinities, huge shifts) must
   fail without losing the draft; Tasks 1–3 test this.
3. A mission change during a pending save must not associate the receipt/draft
   with the new mission; Task 4 tests this.
4. Record ordering across pagination and identical start times must be stable
   and explicitly incomplete until loaded; Task 4 tests this.
5. Relinking a call with dependent participation must preserve reference
   integrity without mutating its conference; Task 1 tests this.

## File map and contract decisions

Backend changes stay in `app/operator/{payloads,api_models,models}.py` and
`app/api/operator.py`; existing service/commands/references/projections remain
the transactional foundation. Only change those modules when contract tests
demonstrate a missing guard. Add focused call tests under `tests/operator/`.

Frontend adds `components/operator/{callDraft,callTiming}.ts`, `CallEditor.tsx`,
`CallList.tsx`, and `OperatorCommunications.tsx`, with colocated tests. Extend
`types/operator.ts`, existing API/query hooks, `OperatorBrief.tsx`, and the
Operator page. Keep journal-specific input/types intact when broadening
commands.

Field names: `party: string | null`, `coordinator: string | null`,
`communications_kind: 'voice' | 'vtc' | 'other' | null`,
`prep_lead_minutes: number | null`. Party/coordinator max 200 characters; lead
is a strict integer from 0 to 10080 (one week). Retain existing title/note
bounds and conference ID validation. New call title derives from party or
“Unscheduled call” when absent. All API timestamps remain aware RFC 3339 UTC.

## Task 1: Typed public call writes and durable round-trips

**Files:** Modify
`backend/starlink-location/app/operator/{payloads,api_models,models}.py`,
`backend/starlink-location/app/api/operator.py`; add
`backend/starlink-location/tests/operator/test_call_api.py` and
`test_call_compatibility.py`; extend `test_public_type_races.py` if necessary.

**Interfaces:** Public create/update accept a discriminated union of existing
journal DTOs and new `CallCreate`/`CallUpdate`. Keep shared remove/restore DTOs.
`CallPayload` has the fields above with read defaults null. `CallCreate`
normalizes omitted lead before creating/hashing `CreateRecord`; `CallUpdate`
requires the lead key. All five statuses retain the wire spelling `cancelled`.

- [ ] Write API tests for each omitted/null/zero/positive lead table cell in the
      spec; assert planned POST omission yields 10, completed/cancelled omission
      yields null, missing PUT yields 422 and unchanged revision count.
- [ ] Add failing tests for scheduled creation without start, party/time quick
      creation, unknown duration, reversed actual/planned intervals, future
      actual time, invalid numeric/text fields, and mismatched payload/type.
- [ ] Run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements-dev.txt pytest tests/operator/test_call_api.py -q`
      from the backend; confirm failures are missing call contracts, not setup
      errors.
- [ ] Extend DTOs/payload fields and public writable types to calls and journal
      entries only. Normalize create defaults only at the boundary; enforce
      update type immutability inside the transaction, preserving receipt-first
      replay.
- [ ] Add compatibility tests seeding raw legacy JSON with no lead: API reads
      null; stored JSON, receipts and raw projection hashes remain unchanged.
      Correct to null and verify only a new revision changes. Assert omitted-key
      POST retry after correction returns original receipt once.
- [ ] Add concurrency/transition tests: one winner for two expected-version
      writes, remove/restore, all statuses, mission/leg correction, conference
      relink, participation dependency conflict, and unchanged shared
      conference. Assert history contains old/new planned times and projections
      contain corrected actual/party values.
- [ ] Run the focused tests plus existing operator tests with the bounded
      backend command; verify restart/recovery/backup and journal API regression
      coverage, then commit `feat: expose durable Operator call requirements`.

## Task 2: Frontend call contracts and deterministic timing

**Files:** Modify `frontend/mission-planner/src/types/operator.ts`; add
`src/components/operator/callTiming.ts`, `callDraft.ts` and their tests.

**Interfaces:** Export `CallPayload`, `CallInput` and broaden command
create/update bodies to `JournalInput | CallInput`. Use nullable/optional lead
on saved legacy payloads, required nullable lead on call writes. Export
`preparationAt(record: SavedRecord): string | null`,
`shiftCallTime(time: RecordTime, minutes: number): RecordTime`, and
`callDraft(record: SavedRecord | undefined, mode: 'planned' | 'retrospective', missionId: string): CallInput`.

- [ ] Write failing tests: planned draft lead 10; retrospective null;
      legacy/null/zero/positive edit round-trips retain values. Actual and
      planned times remain independent.
- [ ] Write `shiftCallTime` tests: +120 and -15 minutes across midnight,
      unchanged actual fields, known duration preserved, unknown planned end
      stays null; invalid/noninteger/out-of-range shift or unknown start
      produces a validation error, never an invented start/end. Limit shifts to
      ±525600 minutes and require resulting valid UTC timestamps.
- [ ] Write `preparationAt` tests: start 1600Z and lead 10 gives 1550Z, zero
      gives 1600Z, unknown lead/start and terminal/deleted records return null.
      Completed retrospective calls return null through correction/restore.
- [ ] Run bounded Vitest for these files and confirm intended failures;
      implement pure helpers with no local clock, implicit timezone, network or
      defaulting during edits.
- [ ] Run focused tests plus TypeScript build, then commit
      `feat: add deterministic call timing and draft contracts`.

## Task 3: Short call entry, rescheduling and audit actions

**Files:** Add
`src/components/operator/{CallEditor,CallList,OperatorCommunications}.tsx` and
colocated tests. Extend `JournalHistory.tsx`/`RevisionDetails.tsx` only where
new payload fields need display support.

**Interfaces:** `CallEditor` consumes a `CallInput` draft, `disabled: boolean`,
`onChange(draft: CallInput): void`, and `onSubmit(): void`; draft ownership
stays in `OperatorCommunications`. `CallList` consumes `ReadRecord[]`,
incomplete state, and selection/history callbacks.
`OperatorCommunications({missionId: string})` owns selected call/draft and uses
Task 4's store-bound query/mutation hook.

- [ ] Write failing editor tests for time/party-only save, UTC date/time fields,
      all statuses, explicit unknowns, optional detail disclosure, unknown
      duration and null lead, absolute and signed shifts, midnight crossing, and
      actual interval correction.
- [ ] Add tests for malformed numeric input, end-only actual interval
      validation, and required scheduled start. Keep invalid draft values
      visible with field errors; never silently coerce empty numeric inputs to
      zero.
- [ ] Implement editor and list with 44px minimum controls and responsive
      stacking. Provide Schedule call, Log unscheduled/completed call, explicit
      status reinstatement, history, remove and restore actions. Reuse
      mission/leg/between-leg association patterns; do not expose conference
      lifecycle editing.
- [ ] Test completed/removed records remain accessible; unrelated edits preserve
      lead and planned/actual separation; retained conference reference can be
      cleared or replaced without closing the conference. History shows
      timing/participant corrections.
- [ ] Run bounded focused Vitest and commit
      `feat: add Operator communications entry and corrections` once integrated
      with Task 4 interfaces. No runtime acceptance claim at this stage.

## Task 4: Store-bound synchronization and shell integration

**Files:** Modify `src/hooks/api/{operatorReadSession,useOperatorJournal}.ts`,
`src/services/operator.test.ts`, `src/pages/OperatorJournalPage.tsx`,
`src/components/operator/OperatorBrief.tsx`; add communications integration
tests and extend hook/brief tests.

**Interfaces:** Generalize
`operatorRecordsOptions(missionId, identity, recordType = 'journal_entry')` and
`useOperatorJournal(missionId, recordType = 'journal_entry')`; support
`recordType: 'journal_entry' | 'call'` and include it in query keys. Keep
default journal behavior. Task 3 consumes
`useOperatorJournal(missionId, 'call')` with existing
save/retry/reconcile/health/records semantics.

- [ ] Write failing hook tests for calls: no Saved before receipt, duplicate
      click, offline/uncertain retry with same key, explicit stale-version
      conflict, epoch change reconciliation, receipt replay followed by
      current-row reread, and mission switch during an outstanding save.
- [ ] Implement call query type partitioning and broad mutation types without
      changing journal reads. Refetch calls on focus/reconnect/explicit refresh
      and after local writes; preserve drafts and scope by mission/store
      identity. Do not add interval polling.
- [ ] Test two clients through the API/mock boundary: refresh sees remote
      changes but leaves local draft intact; stale save conflicts. Test multiple
      pages and identical planned starts with record-ID tie break, explicit
      incomplete warning, and load-more access.
- [ ] Add Communications navigation/section to Operator. Extend summary active
      statuses to tentative/scheduled/delayed, derive preparation UTC using
      `preparationAt`, retain separately visible overdue calls and exclude
      cancelled/completed/removed from preparation/next requirement. Derive
      due/upcoming at backend `as_of` and label snapshot semantics.
- [ ] Run bounded tests for operator hooks/components/pages/services, existing
      journal recovery/identity tests, lint and production build. Commit
      `feat: integrate synchronized call requirements in Operator`.

## Task 5: Exact-product synthetic acceptance and release evidence

**Files:** Extend
`tools/acceptance/operator-journal/{run,scenario,browser_control}.py`, add
`communications_probe.py`; extend
`tools/tests/test_operator_journal_acceptance.py` and fixtures tests. Add
browser journey at
`frontend/mission-planner/tests/e2e/operator-communications.spec.ts` and add it
to `frontend/mission-planner/playwright.operator-journal.config.ts`. Add report
at `docs/reports/2026-10-17-operator-communications/README.md` and sanitized
artifacts.

**Interfaces:** Extend the current runner's evidence contract with
`communications-proof.json` and fail qualification when required assertions are
absent. Reuse ownership, clock injection, synthetic fixture endpoints,
production image identity checks, failure probes, and cleanup; no parallel
deployment stack.

- [ ] Write failing harness tests requiring communications proof and wholly
      synthetic fixtures. Pin clock 1600Z and retrospective call 1430–1442Z;
      include shared conference, multiple legs, unknown-duration and midnight
      requirements, and unreachable optional provider.
- [ ] Implement browser journey at 1920×1080, 390×844 and 844×390: create,
      shift, cancel/reinstate, retrospective log/correct/relink/remove/restore,
      inspect history and projections; assert reminder recomputation and
      conference independence.
- [ ] Add two-client stale-edit conflict, held receipt/duplicate click, offline
      save/reconnect, app restart with no duplicate revision, and
      legacy/null/zero edit-round-trip scenarios. Verify existing Overview
      baselines, display controls and mission export hashes through existing
      probes.
- [ ] Run bounded harness tests and commit product plus acceptance code before
      exact-SHA qualification. Read cloud Docker skill references and
      `docs/development/cloud-docker.md`; preserve the actor's Docker
      context/socket and proxy/CA configuration.
- [ ] Record ownership; run
      `timeout --kill-after=30s 90m python3 tools/acceptance/operator-journal/run.py --candidate <full-HEAD-SHA> --project operator-365-<unique> --evidence /tmp/operator-365-<unique>`
      from repository root. A pass requires fresh production images, actual
      Nginx browser journeys, all proof files and verified teardown; on timeout
      verify owned process tree is gone before retry.
- [ ] Run `timeout --kill-after=10s 30m ./tools/verify backend`, `frontend`, and
      static with `ACCEPTANCE_POLICY_BASE_SHA` set to the exact merge base.
      Preserve versions/output and verify no test resources remain.
- [ ] Write sanitized report with exact product SHA, screenshots,
      contract/failure results, unchanged mission/Overview evidence,
      backup/downgrade instructions and cleanup proof. Commit evidence, push PR
      #375 updates, and require final-head CI. If product changes after
      acceptance, rerun exact-product acceptance; evidence-only commits must
      identify the tested ancestor precisely.
- [ ] Keep PR draft until implementation/review gates are satisfied. Do not
      claim aircraft validation or merge without authorization. Preserve open-PR
      worktree, stop task runtime resources immediately after checks, and remove
      feature worktree/branches only after merge.

## Self-review and handoff

Spec sections map to Tasks 1 (contract, storage, compatibility), 2 (timing), 3–4
(UX and synchronization), and 5 (acceptance/delivery). Review-focus cases are
assigned above. Implement Tasks 1–2 before UI integration; Tasks 3–4 share the
explicit hook/editor interfaces and are verified together before production
proof. Review the plan and choose inline or subagent-driven execution before
code changes.
