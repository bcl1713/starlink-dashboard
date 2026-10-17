# Operator journal — Recovery, migration, and validation

Part of the [proposed #362 design](2026-10-17-operator-journal-design.md).
Status: for review; no product implementation authorized.

## WAL, durability, startup, and errors

On store initialization verify local writable volume and configure
`journal_mode=WAL`; every connection uses `foreign_keys=ON`, `synchronous=FULL`,
and bounded busy timeout. Transactions are short, connection scoped, and closed
in finally handlers. No worker shares a connection across threads. Multi-process
writers serialize through SQLite, with conditional version checks after writer
admission. Auto-checkpoint at 1000 pages; idle maintenance uses PASSIVE
checkpoint. Do not truncate WAL while readers are pinned. Bound snapshot
transactions by copying the required rows then releasing the read lock; ZIP
generation happens outside the transaction.

Startup takes a store migration lock, checks metadata/schema checksums, runs
`quick_check`, foreign-key checks and projection/link invariants, then marks
Operator ready. SQLite recovers committed WAL transactions; incomplete commands
leave no partial logical state. Do not replay successful commands or create
synthetic "recovered" operational events. A projection mismatch or corrupt JSON
fails readiness with a clear error. An offline repair can reconstruct pointers
and links from verified revision chains on a backup copy, with a report; runtime
must not silently discard damaged rows or rewrite history.

Read-only media, full disk, I/O errors, corrupt database, missing previously
initialized database, or unsupported schema disable Operator writes and
report 503. Busy does not imply corruption. A transient busy error can be
retried with the same key; persistent I/O/commit errors mark the store
unavailable until reopened and checked. Existing Overview/planning stays
available. Never fall back to an empty database, in-memory store, stale
"success," or automatic backup restore. Initialize a new store only during
explicit first enablement; a sibling durable store identity marker distinguishes
first use from a missing existing database. Enabling requires writing
marker/database durably before readiness; interrupted initialization fails
explicitly for administrator recovery, never resets state.

Process-crash recovery is testable. Actual power-loss durability also depends on
filesystem/device honoring synchronization; simulation is not proof of hardware
power-loss guarantees. Preserve this limit in acceptance evidence.

## Backup, retention, migration, and rollback

Use SQLite's online backup API to a same-volume temporary file, validate
integrity, fsync the result, atomically rename, and fsync its directory. Never
copy only the main database from a running WAL store. Take a backup before
migrations and on an explicit operator-settings backup action. Offer local
download/copy instructions; same-disk backup is recovery from logical damage,
not disk failure. No mandatory backup daemon. Record backup store ID, schema
version, last committed sequence, checksum, and UTC creation time without
logging content.

Default retain the latest three validated local backup sets; remove the oldest
only after a new one is durably published. Retain live records, all revisions,
and receipts without automatic time expiry in the MVP. At configurable capacity
(default 1 GiB database plus WAL, excluding backups), surface an Operator
settings advisory at 80%; at 100% reject new commands before mutation with
`503 capacity_exceeded`. Do not prune history or receipts to make space. Free
capacity/raise the configured bound or archive an entire disabled store
explicitly. Reserve headroom through deployment storage sizing; this limit
cannot guarantee the physical disk has space for a pending transaction.
Disk-full rollback tests remain mandatory.

Soft removal is not erasure. Current exports omit removed records; audit exports
and backups retain them. Document this in settings/export help. Physical purge
is an offline administrative whole-store action after export/backup and
retention decision, including its backup sets; per-record hard deletion is
outside MVP. No new uncertainty acknowledgment gates are introduced. Sensitive
details stay on the local volume and explicitly requested exports, never
repository fixtures.

Schema migrations are numbered forward-only, checksummed, and applied once under
an exclusive maintenance lock with Operator requests drained. Each supported
migration uses a transaction and updates schema metadata only on commit.
Validate the restored backup in a scratch store before destructive future
migrations. Newer unsupported versions fail closed rather than attempting a
downgrade.

First rollout is additive: existing mission/export schemas remain unchanged,
feature flag defaults off, and disabling it stops Operator writers and hides its
UI while preserving the database. Binary rollback can leave the disabled store
intact. Re-enable only with a binary supporting that schema. To restore a
backup, stop all Operator access, preserve the failed database and WAL set,
validate a backup copy, replace using the maintenance tool, and reopen/check
before enabling. Never claim backup restoration preserves post-backup entries:
compare exported history/high-water marks and reconcile explicitly. Retrying an
operation after a restore may encounter a lost receipt; clients must reset the
session and inspect saved state before resubmitting uncertain writes. The
restore tool rotates a separate API epoch in the identity marker; API clients
send that epoch on writes, so old clients receive `409 store_epoch_changed`, not
a duplicate replay.

## Simulation-first validation and evidence

All runtime tests operate locally without terminal hardware, actual mission
data, external services, or internet. Provisioned dependencies/images/browsers
are a setup prerequisite, not an acceptance-time network dependency. Use
deterministic UTC clocks, a multi-leg synthetic mission, synthetic Starshield
observations, modeled PoP transitions from the real #348 adapter, and an
unreachable optional provider. Never log real IPs, coordinates, calls, or raw
missions.

| Layer              | Required scenarios and assertions                                                                                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Models/unit        | UTC offsets and midnight crossing; naive rejection; unknown/approximate/ongoing times; actual versus planned; source freshness unknown/stale; caller cannot spoof observed provenance; strict payload and size checks                                                                                        |
| Store/contract     | One current row and one initial revision; correction once in current view; ordered full history; late 1430–1442Z call entered at 1600Z; 1545→1535 correction; remove/restore; no reminder eligibility from retrospective changes                                                                             |
| Transaction        | Inject failure after revision insertion, pointer update, links update, receipt insertion and before commit; all old state or all new state, never a mismatched projection; multi-record fixture action rolls back every record                                                                               |
| Retry/concurrency  | Two clients update same version: one commits, one 409; same key/same body yields one revision and original response; changed body/key conflict; lost response after commit; removed/moved association does not defeat receipt retry                                                                          |
| References         | Preflight without active leg; between-leg and postflight; wrong-leg correction; leg switch during edit; mission move invalidates old/new lists; deleted planning mission remains readable; dependency-blocked remove/type/move and restore                                                                   |
| Read/export        | Snapshot paging under concurrent edits/removal/move; current projection omits removed rows; audit retains all; H bounds all exports; independent capture revisions declared; frozen export unchanged after subsequent edits/restart                                                                          |
| Recovery           | Separate subprocess killed at barriers before/during/after commit, including committed WAL not checkpointed; reopen and verify either no command or complete command with receipt; repeat same key; truncate/corrupt disposable DB/WAL and require explicit failure or valid recovery, never silent row loss |
| Storage failure    | Disk-full/quota VFS or disposable constrained filesystem, read-only DB, busy writer, missing existing DB, corrupt payload/pointer, unsupported schema, bad migration checksum; no false success or empty-store fallback                                                                                      |
| Migration/backup   | Interrupted migration rolls back; online backup includes committed WAL; restore integrity and H; stale client epoch rejected; old binary refuses unsupported schema; flag-off rollback preserves files and baseline behavior                                                                                 |
| Integration        | Actual #348 predictions with synthetic routes/clock offline; #349 leg transitions and archive references unchanged; unavailable optional feeds do not prevent journal writes; no writes to flight/archive/Prometheus stores                                                                                  |
| Production browser | Two independent browser contexts, desktop 1920×1080 and mobile portrait 390×844/landscape 844×390; create late note/call observation, edit, view history, remove/restore, refresh/reconnect, conflict and failed-save recovery; no duplicate records or false confirmation                                   |

The #362 feature-gated editor is intentionally small: journal list, create/edit,
history, remove/restore, and explicit saved/pending/conflict/error status. It
lives in Operator, never Overview. It uses the same HTTP/service path as later
children. Typed call/conference/issue fixtures exercise the internal service
contracts now; complete call scheduling and conference lifecycle browser
journeys belong to #365/#366 and the epic's final gate, not a claimed #362
capability.

Run focused backend contracts first, then production-image Docker/Nginx browser
acceptance on the exact committed candidate with a task-specific Compose project
and private volumes. Capture sanitized desktop/mobile results, installed
versions, fault barriers/exit codes, DB integrity results, fixture export
contents and checksums, rollback exercise, and baseline Overview/export
comparisons. Preserve evidence in the repository's reports convention. Do not
claim aircraft readiness from these tests or substitute a development server for
production acceptance.

Every runner records command/session, PID/process group, Compose project,
volumes, and temporary paths before starting; uses an explicit wall-clock
timeout with termination grace; and cleans
children/contexts/containers/networks/private volumes on exit/signals. Verify
owned resources gone after each run, including forced termination, as required
by `docs/development/workflow.md` and `cloud-docker.md`.
