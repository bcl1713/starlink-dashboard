# Operator journal maintenance

Operator is disabled by default. Its database, immutable revisions and command
receipts live separately from mission/planning storage. Disabling Operator
preserves its files. A binary that does not support the stored schema refuses
to open it; disabling the feature is the safe binary rollback path.

Run these commands from `backend/starlink-location` with the application's
Python environment. Every command requires an explicit root and mode. Simulation
also requires `--run RUN_ID` and uses `ROOT/simulation/RUN_ID/`.

```sh
python -m app.operator initialize --root data/operator --mode live
python -m app.operator check --root data/operator --mode live
python -m app.operator backup --root data/operator --mode live
python -m app.operator restore --root data/operator --mode live --manifest PATH
```

`initialize` is explicit first enablement. `check`, `backup`, and runtime startup
never create a missing replacement database. An interrupted initialization marker
requires administrator recovery. `check` returns JSON health and a nonzero exit
status when unavailable. It takes exclusive maintenance admission for WAL,
integrity, schema, complete typed revision/receipt and derived-link checks.
Concurrent access produces a bounded, retryable `store_busy`; it is not evidence
of corruption. Internal maintenance scans and the SQLite online-backup loop have
two-second deadlines. Large stores may therefore require maintenance tuning in a
future release; a timeout never silently skips validation.

Backups use SQLite's online backup API, including committed WAL changes. Use
`backup --directory PATH` to choose a destination; the default is the store's
`backups/` directory. A database checksum and validated snapshot metadata are
published through a durable manifest after syncing the snapshot. The manifest
contains the store ID, schema version, source mode/run, UTC creation time, and
last committed sequence `H` from that backup snapshot. Only after publication
does retention remove older sets, keeping the latest three by publication order
(configurable with `OPERATOR_BACKUP_COUNT`). Keep the manifest and its named
database together when copying or downloading a set. Copy them to another device
for protection from disk failure; same-disk backups cannot provide that.

Stop Operator access before restore. The tool rejects restore while any
cooperating Operator transaction is active and prevents new transactions during
replacement. It validates the backup and store/mode/run identity first, preserves
the old database, WAL, shared-memory file and identity in a private
`preserved-UUID/` directory, then installs the whole backup. It never automatically
chooses or restores a backup. Restore requires the existing identity marker and a
matching backup; it is not an import into a new root or a cross-mode conversion.
An interrupted replacement leaves a non-ready marker for explicit recovery.
Do not open or alter the preserved SQLite files while investigating; work on a
copy so SQLite recovery cannot change the evidence.

Restore rotates the durable API epoch. Old client writes and cached store handles
receive `store_epoch_changed`. Restart the Operator runtime, reset clients, inspect
saved state, and reconcile uncertain writes before resubmitting. Receipts and
entries newer than the backup may be lost. `restore-report.json` records
`restored_H`, the previous `H` when readable, backup time and the preserved set.
An unreadable previous high-water mark is `null`, never a claim of zero loss.

Capacity includes database plus WAL, excluding backups. Operator settings can
surface the 80% advisory from `capacity_status`; at the configured limit
(`OPERATOR_CAPACITY_BYTES`, default 1 GiB), new writes fail with
`capacity_exceeded`. Existing receipt retries and reads remain available. Raise
the limit or free space; no automatic expiry removes records, revisions or
receipts. The configured bound does not reserve physical free space. Full,
read-only or failed media rolls back the command and disables the affected store
until reopened and checked. Passive checkpoints leave WAL frames pinned by
readers intact.

Soft removal is not erasure. Current-state exports omit removed records; default
activity retains their changes/removals, while requested audit exports and
backups retain original bodies. Per-record hard deletion is not supported. An
administrative whole-store purge, including backup sets, is an offline retention
decision after export/backup; this CLI intentionally has no purge command.

Process-kill tests verify atomic old-or-complete commands and exact receipt
retries, including committed uncheckpointed WAL. Conservative WAL preflight
rejects malformed headers, partial frames and invalid frame checksums before
SQLite can discard them. This is not proof of hardware power-loss durability:
filesystem/device synchronization still matters. Arbitrary external removal or
replacement with a structurally valid older database/WAL cannot be detected by a
SQLite-only journal; compare external exported history when investigating such
damage. No secondary commit journal or automatic history reconstruction exists.
Only schema migration 1 is currently supported. Initial migration is
transactional; future schema upgrades must add validated pre-migration backups
under the same exclusive maintenance admission.
