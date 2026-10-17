# Operator journal — API, projection, and editor task details

Part of the [implementation plan](2026-10-17-operator-journal.md). Paths follow
its backend/frontend convention. All preceding task interfaces are
prerequisites.

## Task 5: Gated API and lifecycle

**Files:** Create `app/api/operator.py`, `app/operator/api_models.py`,
`app/operator/runtime.py`; modify `main.py` startup/shutdown and router
registration; tests `tests/operator/test_api.py`, `test_runtime.py`.

**Interfaces:**

```python
OperatorRuntime.start(settings: OperatorSettings, *, clock: Clock) -> OperatorRuntime
```

`.service -> OperatorService | None`, `.health() -> StoreHealth`,
`.close() -> None`. `api_models.py` maps public DTOs to Task 1 commands and
back; internal-only fixture types cannot enter through HTTP. Router prefix
`/api/v2/operator` implements every approved endpoint. Each mutation reads
`Idempotency-Key` and `X-Operator-Store-Epoch`; returns Task 1 receipt status
and saved body, with replay header. Actor comes from the existing LAN-boundary
attribution plus unverified optional label, never trusted request identity
headers.

- [ ] Write `test_api.py::test_saved_then_replayed`: initialize via fixture,
      create returns 201/v1, PUT 200/v2, duplicate returns original body with
      `Idempotency-Replayed: true`, stale version returns 409/current_version.
      Reject missing key/epoch/version (422), spoofed source/internal payload
      (422), absent record (404), >64 KiB body (422), key-body mismatch (409).
- [ ] Add API assertions for omitted/blank audit notes saving without prompts,
      generated versus supplied reasons, cursor bounds and history ordering.
      Inject commit-ack failure, retry same key; assert no duplicate record.
      Busy yields 503 plus `Retry-After: 1`; commit-uncertain retains retryable
      status.
- [ ] Write `test_runtime.py::test_disabled_and_unhealthy_isolation`: disabled
      returns 404 for Operator endpoints, creates no store or threads; enabled
      but uninitialized/corrupt returns 503 with `enabled=true` in health and no
      success. Healthy health includes enabled/store ID/epoch/readiness; all
      errors sanitize SQL/paths/content. Baseline status/config/Missions still
      work; shutdown closes all Operator connections. A mode switch never opens
      live data as simulation.
- [ ] Run both files; expect missing router/runtime. Implement using Task 3
      service and Task 4 checks; startup opens initialized stores only, optional
      failure stays isolated. Add CORS exposed replay/ETag headers if used by
      clients; do not weaken existing restrictions or change flight/archive
      lifecycle.
- [ ] Rerun both plus existing `tests/integration/test_flight_events_api.py` and
      `tests/unit/test_main_pop_startup.py`; expect pass. Commit
      `feat: expose gated Operator journal API`.

## Task 6: Deterministic current/activity/audit projection

**Files:** Create `app/operator/projection_models.py`, `projections.py`; tests
`tests/operator/test_projections.py`, `test_projection_membership.py`.

**Interfaces:**

```python
capture_projection(store: OperatorStore, *, mission_id: str, include_audit: bool = False) -> ProjectionBundle
```

captures one read snapshot H. `ProjectionBundle` (in `projection_models.py`)
contains `high_water`, manifest, canonical bytes for `operations/current.json`,
`operations/activity.jsonl`, and optional `operations/audit.jsonl`, plus
checksums and source-mode/store/epoch IDs. `ActivityItem` carries the approved
revision identity, command/sequence, operation, time/provenance, reason/origin,
association, and structured before/after fields. This function does not open
ZIPs, queue jobs, query Prometheus, or register routes.

- [ ] Write `test_projections.py::test_default_activity_without_audit`: create
      synthetic call, schedule shift/cancellation, issue open/resolve, late
      report, end correction 1545→1535, remove/restore. Assert one active
      current row per ID, one activity item per revision, before/after
      schedule/status/time values, recorded versus actual times, generated
      reason labels and explicit source mode; no audit file unless requested.
      Removed records retain activity only.
- [ ] Add `test_recording_order_and_text_policy`: clock regression/unknown
      actual time cannot backdate system knowledge; acceptance sequence orders
      activity. A note edit names changed fields and that revision's title; full
      old note body appears only in explicit audit. Activity's retrospective
      flag follows revision origin, never a guess that modeled ETA equals prior
      system knowledge.
- [ ] Write `test_projection_membership.py::test_move_and_concurrent_snapshot`:
      mission A→B move produces same-identity move-out/in boundary, before/after
      IDs, no later B edits in A activity. At pinned H, concurrent edit/removal
      does not mix versions across files; repeated projection bytes/checksums
      match after restart with unchanged inputs. Include no-leg
      preflight/between/postflight.
- [ ] Run both files; expect missing projection function. Implement SQL snapshot
      and typed deterministic diffs, release read transaction before
      serialization. Latest-per-ID at H precedes current mission/deleted
      filters; activity includes predecessor membership for move-out. Preserve
      full historical content only in labeled audit. Declare capture points
      without asserting cross-database atomicity.
- [ ] Rerun both files and Task 3 query tests; expect pass. Update
      `docs/operations/operator-journal.md` with current/activity/audit
      retention and #370 preparation handoff. Commit
      `feat: project Operator activity and audit snapshots`.

## Task 7: Small responsive Operator editor

**Files:** Create frontend `src/types/operator.ts`, `src/services/operator.ts`,
`src/hooks/api/useOperatorJournal.ts`, `src/pages/OperatorJournalPage.tsx`,
`src/components/operator/JournalEditor.tsx`, `JournalHistory.tsx`,
`JournalList.tsx`; modify `src/App.tsx`; tests `src/services/operator.test.ts`,
`src/hooks/api/useOperatorJournal.test.tsx`,
`src/pages/OperatorJournalPage.test.tsx`,
`src/components/operator/JournalEditor.test.tsx`.

**Interfaces:** TS DTOs mirror public schema-v1 API types, not internal fixture
commands. `getOperatorHealth(): Promise<OperatorHealth>`;
`readOperatorRecords(filters, cursor?): Promise<RecordPage>`;
`saveOperatorCommand(command, key, epoch): Promise<CommandReceipt>` and
`readOperatorHistory(id, cursor?): Promise<HistoryPage>` use existing HTTP
style. `useOperatorJournal(missionId: string)` owns read invalidation and
mutation state. `OperatorJournalPage` lives at `/operator`; query-selected
mission and explicit scope/leg, no requirement for an active route. UI never
silently follows active leg while editing an existing record.

- [ ] Write service/hook tests: a lost acknowledgment preserves the exact key
      and body for retry, failed save preserves draft, successful replay fetches
      latest state, conflict shows latest version without auto-overwriting
      draft. Epoch mismatch prevents old write replay and requires
      reread/reconciliation.
- [ ] Write page/editor tests: one corrected row, separately accessible history,
      create/update/remove/restore with no reason prompt; optional audit note
      labeled optional. UTC with unknown/approximate times, explicit
      mission/between-leg scope, no uncertainty acknowledgment. Health 404 hides
      navigation; enabled unavailable store shows error/read-only draft rather
      than a false empty list. Remount/refetch maintains saved state; mobile
      uses labeled controls and existing responsive styling, no horizontal
      overflow in the acceptance sizes.
- [ ] Run `npm run test:unit --` followed by the four files above; expect
      missing interfaces. Implement API client and journal hook, then focused
      components and route/nav gate. Keep uncertain save request in component
      state until resolved; unsaved drafts need not survive full browser
      closure, saved records must. Do not add the full #363 shell or modify
      Overview display content.
- [ ] Rerun those files plus `src/App.fullscreen.test.tsx`; expect pass. Run
      `npm run build` and scoped lint/format checks; commit
      `feat: add gated responsive Operator journal editor`.
