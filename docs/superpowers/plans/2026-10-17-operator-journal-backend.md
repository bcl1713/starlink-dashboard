# Operator journal — backend task details

Part of the [implementation plan](2026-10-17-operator-journal.md). Read its
global constraints and approved specification before execution. No
implementation yet.

## Task 1: Typed contracts and injected clock

**Files:** Create `app/operator/__init__.py`, `models.py`, `payloads.py`,
`clock.py`, `errors.py`; tests `tests/operator/conftest.py`, `test_models.py`.

**Interfaces:** `Clock.now() -> datetime`, `Clock.monotonic() -> float`
(protocol), `SystemClock`, and test `FakeClock`. In `models.py`, define strict
schema-v1 `RecordInput` (editable type/mission/leg/scope/time/payload),
`CreateRecord`, `UpdateRecord`, `RemoveRecord`, `RestoreRecord`, and their
discriminated union `OperatorCommand`; update/remove/restore include
`record_id`, `expected_version`, optional `audit_note`. Define `SavedRecord`
(full revision), `CommandReceipt` (command ID, HTTP status, saved records,
canonical response), `RecordFilter`, `RecordPage` (items, cursor, H, as_of),
`HistoryPage`, `StoreHealth`, `SourceProvenance`, `Actor` (unverified display
label and backend attribution).

```python
OperatorError(code, *, retryable=False, fields=None, current_version=None, record_ids=None)
```

is a typed exception, not a string-parsing convention. `payloads.py` owns the
closed payload union; no arbitrary JSON event plugin.

- [ ] Write `test_models.py::test_utc_and_unknown_times` asserting offset inputs
      normalize to fixed-microsecond Z, naive time fails, unknown actual/source
      time stays null, end-before-start and actual now+61s fail, midnight
      intervals pass.
- [ ] Add `test_strict_payload_and_origin` asserting unknown fields,
      201-character titles, 8001-character notes and spoofed observed provenance
      fail. Assert planned-only times pass; a future planned time is not an
      actual occurrence.
- [ ] Run `tests/operator/test_models.py -q`; expect missing contracts, then
      implement the interfaces above using Pydantic and the spec's interval
      rules. Service clock-dependent checks accept a supplied `Clock`, never
      `datetime.now` hidden in validators. Define payloads for journal note/call
      observation and internal synthetic
      call/conference/participation/issue/risk/transport fixtures.
- [ ] Rerun the same selection; expect all assertions pass. Commit
      `feat: define Operator record contracts and clock`.

## Task 2: SQLite schema, identity, and connection ownership

**Files:** Create `app/operator/schema.py`, `store.py`, `settings.py`,
`migrations/001_initial.sql`; tests `tests/operator/test_schema.py`,
`test_store_lifecycle.py`.

**Interfaces:** `OperatorSettings.from_env() -> OperatorSettings` includes
enabled, root, mode/run ID, 1 GiB capacity, backup count 3.

```python
OperatorStore.open(settings, *, initialize: bool, clock: Clock) -> OperatorStore
```

`store.connect()` yields a bounded, connection-local transaction context;
`store.health() -> StoreHealth`; `store.close() -> None`. `initialize=True` is
explicit first enablement only.
`apply_migrations(connection, *, clock: Clock) -> None` owns checksum
validation.

- [ ] Write `test_schema.py::test_revision_and_receipt_immutability`: create a
      linked revision/pointer/receipt fixture; UPDATE/DELETE history/receipt
      fails, pointer skips and invalid predecessor fail; `foreign_key_check` is
      empty.
- [ ] Write `test_store_lifecycle.py::test_explicit_initialization_and_mode`:
      assert WAL/FULL/FKs/1000-page checkpoint/2000ms busy timeout, private
      modes, persisted store ID and simulation mode; mode/run mismatch, missing
      initialized database, bad checksum and unsupported version fail closed,
      never auto-create.
- [ ] Run both files; expect missing store. Implement schema from the approved
      document including `reason_origin`, immutable triggers, metadata and
      durable sibling identity/epoch marker. First enablement publishes
      marker/database durably; interrupted initialization requires maintenance,
      not reset.
- [ ] Rerun both files; expect pass. Test two separate connections rather than
      mocking SQLite concurrency. Commit
      `feat: add durable Operator SQLite store`.

## Task 3: Atomic mutations, dependencies, and stable reads

**Files:** Create `app/operator/commands.py`, `queries.py`, `references.py`,
`service.py`; tests `tests/operator/test_commands.py`, `test_concurrency.py`,
`test_queries.py`, `test_references.py`.

**Interfaces:**

```python
OperatorService(store, *, clock: Clock, actor: Actor, references: MissionReferences)
```

exposes
`execute(command: OperatorCommand, *, key: str, epoch: str) -> CommandReceipt`,
`get(record_id: str) -> SavedRecord`,
`list(filters: RecordFilter, *, limit=50, cursor=None) -> RecordPage`,
`history(record_id: str, *, limit=50, cursor=None) -> HistoryPage`,
`journal(mission_id: str, *, limit=50, cursor=None) -> HistoryPage`.
`MissionReferences.locked(mission_ids: list[str])` acquires canonical global
then sorted mission locks with 2-second waits;
`validate(mission_id, leg_id, scope, payload) -> None` calls real mission
storage. No independent mission mirror.

```python
commands.execute_in_transaction(connection, command, *, key, request_hash, clock, actor) -> CommandReceipt
```

is internal; router never calls it directly. Its persistence helper

```python
_persist_changes(connection, changes: list[SavedRecord], receipt: CommandReceipt) -> None
```

writes complete revisions, pointers/links and receipt on the caller's open
transaction. Normal commands supply one change; the atomic multi-record test
supplies two directly, without adding a public batch API or a generic production
event framework.

- [ ] Add `test_commands.py::test_late_entry_correct_remove_restore`: fake
      1600Z, report 1430–1442Z; correct an end 1545→1535; assert one current
      row, versions 1–4 through remove/restore, retained originals and new
      acceptance times. Add no-audit-note and blank-note cases producing
      automatic reasons, supplied note producing operator origin, 1001-character
      note rejected.
- [ ] Add `test_concurrency.py::test_same_version_and_receipt_retry`: two actual
      writer connections submit different keys at version 1; one succeeds, one
      conflicts. Exact duplicate key returns identical saved response even after
      a newer edit/missing mission; changed canonical body conflicts. Epoch
      mismatch is checked before receipt lookup. No duplicate versions or side
      effects.
- [ ] Add `test_commands.py::test_atomic_failure_barriers`: inject a test-only
      hook after revision, pointer, links and receipt writes; each exception
      leaves all previous state, including for a two-record internal fixture
      command.
- [ ] Add reference tests: wrong-leg correction leaves prior audit, no active
      leg needed, cross-mission linked move/type/removal conflicts, removed
      children do not block parent removal, restore revalidates missing targets.
      Missing planning missions remain readable and can be reassociated/removed.
- [ ] Add `test_queries.py::test_snapshot_pages_during_move`: capture H, edit,
      move and remove records between pages; enumerate exactly the H projection
      once per ID. Limit 201 and filter-mismatched/invalid cursors fail; null
      actual times and clock regression never alter sequence order.
- [ ] Run the four files; expect missing service. Implement receipt-first retry,
      BEGIN IMMEDIATE with version checks, dependency validation, full revision,
      pointer/link changes, and receipt, one commit. New writes validate mission
      references under locks; removal from missing mission must not require it
      to exist. Generate reasons server-side; no externally initiated adapter
      claims. Build H queries by latest revision at/below H, then filter.
      Include epoch in cursors so restored stores cannot accept obsolete
      pagination snapshots.
- [ ] Rerun these files; assert pass and DB invariants. Commit
      `feat: make Operator state and history transactional`.

## Task 4: Recovery, backup, retention, and migration rollback

**Files:** Create `app/operator/maintenance.py`, `backup.py`, `recovery.py`,
`__main__.py`; tests `tests/operator/test_recovery.py`, `test_backup.py`,
`test_capacity.py`, `crash_worker.py`.

**Interfaces:** `verify_store(store: OperatorStore) -> StoreHealth` performs
quick, FK, projection and typed payload/link checks.
`backup_store(store, *, directory: Path) -> Path` returns a validated published
backup manifest.
`restore_store(settings, *, manifest: Path, clock: Clock) -> StoreHealth` is
offline maintenance only. CLI `python -m app.operator` supports explicit
`initialize`, `check`, `backup`, `restore`; commands require `--root` and
`--mode`, and restore requires `--manifest`. No destructive per-record purge
command.

- [ ] Write `test_recovery.py::test_killed_writer_atomicity` using a spawned
      worker and synchronization pipe: terminate at each Task 3 barrier and just
      after COMMIT before acknowledgment; reopen, verify old-or-complete state
      and exact receipt retry. Include committed uncheckpointed WAL. Reap each
      worker.
- [ ] Write `test_explicit_corruption_failure`: corrupt/truncate disposable
      DB/WAL, invalid JSON or link index; recovery either validates the intact
      transaction chain or refuses readiness. Never drop damaged records or
      replay successful commands. Bounded busy is retryable, corruption is not.
- [ ] Write `test_backup.py::test_backup_restore_epoch`: online backup includes
      committed WAL, passes integrity/checksum, keeps latest three published
      sets; interrupted backup cannot delete the last good set. Restore an older
      backup with newer receipts present in original; preserve damaged
      store/WAL, rotate epoch durably, reject old clients, expose backup
      H/data-loss boundary.
- [ ] Add capacity tests at 80% advisory/100% reject with a small configured
      limit; inject SQLITE_FULL/READONLY/IOERR and actual subprocess-constrained
      storage in acceptance. Test interrupted transactional migration and marker
      publication, unsupported-schema rollback/flag-off preserving files.
- [ ] Run the three test files; expect missing maintenance. Implement bounded
      startup checks, typed error health, PASSIVE checkpoints, online backup
      API, fsync/rename/directory fsync, exclusive offline restore/migration
      locks. No auto-restore or in-memory fallback; retention never expires
      revisions/receipts.
- [ ] Rerun these files and Tasks 1–3; expect pass. Document CLI restore limits
      in `docs/operations/operator-journal.md`. Commit
      `feat: add Operator journal recovery and backup maintenance`.
