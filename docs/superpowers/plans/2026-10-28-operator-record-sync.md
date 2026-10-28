# Operator saved-record synchronization implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this
> plan task by task with test-driven development and one final independent
> review.

**Goal:** Synchronize saved Operator records across visible clients within the
five-second acceptance target while preserving local drafts and conflict safety.

**Architecture:** Identity-validated snapshot baselines feed bounded incremental
reads. One foreground query owner merges newer saved versions and refreshes
timeline/event projections without repeatedly reloading snapshot history.

**Tech stack:** FastAPI, SQLite, React, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-28-operator-record-sync-design.md`.

## Global constraints

- Preserve the approved Operator layout and tab-local drafts/base versions.
- Two-second foreground polling; five-second measured propagation target.
- No production writes/deployment; use disposable synthetic acceptance data.
- Keep existing pagination and expected-version/idempotent-write contracts.
- Every response used for synchronization must carry validated captured
  identity.
- Temporary service/test runners need recorded ownership, timeouts and teardown.

## Review focus

- Empty snapshots must prove identity before their watermark is used.
- Identity changes during bootstrap/batches must quarantine old data.
- Invalid checkpoints must rebaseline rather than retry obsolete state forever.
- New snapshot generations must never regress newer authoritative versions.
- Recovery with a dirty draft must preserve its input, target and base version.

### Task 1: Captured baseline identity and bounded incremental API

**Files:** Modify `backend/starlink-location/app/api/operator.py`,
`backend/starlink-location/app/operator/queries.py`,
`backend/starlink-location/app/operator/service.py`; create
`backend/starlink-location/tests/operator/test_record_sync.py`.

**Interfaces:** Records list returns captured `source` (mission plus health).
`GET /api/v2/operator/record-changes` accepts mission, `after_seq`, optional
cursor and limit; returns `items`, `H`, `cursor`, `as_of`, `source`.

- [ ] Write API tests for empty source-bound baselines, incremental latest
      revisions/tombstones, frozen multi-page batches, mission isolation,
      invalid watermarks/cursors and context changes. Assert no intermediate
      duplicates.
- [ ] Run new tests and verify failure for missing source/changes route.
- [ ] Implement captured identity and delta query using existing
      mission/sequence index, fixed high water and dedicated context-bound
      cursor validation.
- [ ] Run focused tests plus existing Operator API/pagination tests; expect
      pass.
- [ ] Commit backend contract and tests.

### Task 2: Workspace query synchronization and safe reset

**Files:** Create
`frontend/mission-planner/src/hooks/api/useWorkspaceRecords.ts` and its test;
modify services/types, `OperatorWorkspace.tsx`, `WorkspaceEditor.tsx`, and
scoped projection refresh behavior if necessary.

**Interfaces:** `workspaceRecordsOptions(missionId, identity)` validates source
for snapshots. `useWorkspaceRecords(missionId, identity)` returns the existing
infinite query controls plus merged saved items, synchronization failure and
quarantine state. Passive editor observers consume the same overlay/cache.

- [ ] Write failing tests for periodic remote updates, highest-version merging,
      cursor retention, hidden/resume/reconnect behavior, failure recovery and
      cleanup.
- [ ] Include source changes during bootstrap and paginated batches, empty
      baseline validation, invalid-checkpoint reset, late responses and
      dirty-draft input/target/base preservation.
- [ ] Implement one foreground polling owner, staged complete batches,
      generation-bound reset, source validation and scoped projection refreshes.
- [ ] Integrate merged reads into cards/counts/editor relationships and existing
      unavailable presentation without changing draft/write behavior.
- [ ] Run focused tests, frontend unit suite, lint and build; expect pass.
- [ ] Commit frontend behavior and tests.

### Task 3: Two-client production-path acceptance and review

**Files:** Add a focused Playwright sync spec/config using existing coherent
Operator synthetic fixture and an isolated production acceptance runner; add
evidence/walkthrough documentation.

**Interfaces:** Consume Task 1's real API and Task 2's rendered Operator UI.
Record save-completion-to-render latency and per-endpoint request counts.

- [ ] Test independent desktop/mobile contexts: bidirectional call saves,
      conference transitions, call reschedule/cancel, counts and timeline
      convergence.
- [ ] Test foreground recovery, offline/backend recovery, stale actions and
      dirty draft protection, independent edits, source isolation and remount
      cleanup.
- [ ] Commit candidate; run exact-commit production images through Nginx with
      synthetic data and five-second assertions. Preserve evidence and
      screenshots.
- [ ] Verify all task runtime resources are stopped/removed after checks.
- [ ] Obtain one independent whole-branch review, fix material findings with
      regression tests, push the branch and update PR #431 for implementation
      review.

## Execution record

User approved implementation after addressing the PR comment. Execute inline
under that authorization; no additional design/plan approval is needed.
