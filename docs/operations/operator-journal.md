# Operator journal maintenance

Operator is disabled by default. Its database, immutable revisions and command
receipts live separately from mission/planning storage. Disabling Operator
preserves its files. A binary that does not support the stored schema refuses to
open it; disabling the feature is the safe binary rollback path.

Compose forwards `OPERATOR_ENABLED` with a default of `false` and retains the
store in the independent `operator_data` volume mounted at `/app/data/operator`.
Container recreation preserves that volume; removing it removes its retained
history and receipts. The image and entrypoint give only the mount root to
`appuser` with mode `0700`, without recursively changing retained history.
Initialize the chosen namespace explicitly before enabling the API. Startup only
opens existing initialized stores; failure leaves status, configuration,
Overview and Missions available.

Runtime uses the actual coordinator mode, regardless of `OPERATOR_SOURCE_MODE`.
Simulation uses the actual managed run ID when present; otherwise an explicitly
configured `OPERATOR_SIMULATION_RUN_ID` selects an offline/demo namespace. With
neither, enabled simulation reports unavailable and touches no Operator files.
Disabled simulation needs no run ID and opens no Operator files. A run/mode
change closes the previous handle and checks the new namespace under a request
gate; old epochs fail rather than writing into the replacement namespace.

Run these commands from `backend/starlink-location` with the application's
Python environment. Every command requires an explicit root and mode. Simulation
also requires `--run RUN_ID` and uses `ROOT/simulation/RUN_ID/`.

```sh
python -m app.operator initialize --root data/operator --mode live
python -m app.operator check --root data/operator --mode live
python -m app.operator backup --root data/operator --mode live
python -m app.operator restore --root data/operator --mode live --manifest PATH
```

`initialize` is explicit first enablement. `check`, `backup`, and runtime
startup never create a missing replacement database. An interrupted
initialization marker requires administrator recovery. `check` returns JSON
health and a nonzero exit status when unavailable. It takes exclusive
maintenance admission for WAL, integrity, schema, complete typed
revision/receipt and derived-link checks. Concurrent access produces a bounded,
retryable `store_busy`; it is not evidence of corruption. Internal maintenance
scans and the SQLite online-backup loop have two-second deadlines. Large stores
may therefore require maintenance tuning in a future release; a timeout never
silently skips validation.

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
replacement. It validates the backup and store/mode/run identity first,
preserves the old database, WAL, shared-memory file and identity in a private
`preserved-UUID/` directory, then installs the whole backup. It never
automatically chooses or restores a backup. Restore requires the existing
identity marker and a matching backup; it is not an import into a new root or a
cross-mode conversion. An interrupted replacement leaves a non-ready marker for
explicit recovery. Do not open or alter the preserved SQLite files while
investigating; work on a copy so SQLite recovery cannot change the evidence.

Restore rotates the durable API epoch. Old client writes and cached store
handles receive `store_epoch_changed`. Restart the Operator runtime, reset
clients, inspect saved state, and reconcile uncertain writes before
resubmitting. Receipts and entries newer than the backup may be lost.
`restore-report.json` records `restored_H`, the previous `H` when readable,
backup time and the preserved set. An unreadable previous high-water mark is
`null`, never a claim of zero loss.

Capacity includes database plus WAL, excluding backups. Operator settings can
surface the 80% advisory from `capacity_status`; at the configured limit
(`OPERATOR_CAPACITY_BYTES`, default 1 GiB), new writes fail with
`capacity_exceeded`. Existing receipt retries and reads remain available. Raise
the limit or free space; no automatic expiry removes records, revisions or
receipts. The configured bound does not reserve physical free space. Full,
read-only or failed media rolls back the command and disables the affected store
until reopened and checked. A non-busy I/O failure during write commit returns
`commit_outcome_unknown` with retryable status: it may already be saved. Reopen
and check before retrying the identical command/key; the receipt returns its
original saved result if commit completed. A busy commit with successful
rollback remains `store_busy` and does not poison readiness. Passive checkpoints
leave WAL frames pinned by readers intact.

Soft removal is not erasure. Current-state exports omit removed records; default
activity retains their changes/removals, while requested audit exports and
backups retain original bodies. Per-record hard deletion is not supported. An
administrative whole-store purge, including backup sets, is an offline retention
decision after export/backup; this CLI intentionally has no purge command.

The internal `capture_projection(store, mission_id=..., include_audit=False)`
contract returns canonical UTF-8 `operations/current.json` and
`operations/activity.jsonl` bytes with SHA-256 checksums. Current contains one
latest active record per ID. Activity contains one item per accepted revision,
ordered by acceptance sequence even when actual or recording clocks go
backwards. It keeps reported versus recorded times, typed before/after changes,
removal and restoration, generated descriptions, reason attribution and
revision-local titles. Changed note fields are named without copying historical
note bodies. Request `operations/audit.jsonl` explicitly for original full-state
revisions. No automatic retention limit erases any of these revisions from the
store.

Call status is `tentative`, `scheduled`, `delayed`, `completed` or `cancelled`;
issue status is `open` or `resolved` (and may return to `open`). Calls and
journal entries support public editing; conference and issue editing remain
private. See [communications workflows](operator-communications.md). Older
payloads parse with their model defaults, but projections and recovery preserve
persisted historical content and receipt bytes. Missing old statuses stay absent
in audit and become null before-values when first introduced; a default is not
evidence of historical knowledge.

All Operator files share one pinned high-water sequence H. Mission moves include
the same revision identity at both boundaries, with before/after associations;
later edits in the new mission do not leak into the old mission. Mission-only,
preflight, between-leg and postflight records remain at the mission root.
Serialization and planning association resolution run after the read transaction
closes. Missing planning references retain their Operator IDs and appear in the
manifest. Planning association labels are derived and unpinned, with null
capture revision/time; no cross-store atomic capture is claimed. The Operator
capture timestamp is the retained `recorded_at` at H, explicitly labeled as
revision time, not a fresh wall-clock preparation timestamp.

Normal mission ZIP preparation persists these frozen bytes, checksums and
manifest with its existing job before acknowledgment and reuses them after
restart. The outer archive records actual component capture intervals and
planning/telemetry revision boundaries. No additional export route or workflow
is required. Ordinary mission-plan imports ignore archival journal members and
never restore them into the destination Operator database. See
[Mission ZIP journal archive](mission-journal-archive.md) for the complete
package, independent validation and rollback contract.

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

## Production acceptance and backout

The isolated acceptance command uses the existing production Dockerfiles and
Nginx from an archive of a clean, full committed HEAD:

```sh
timeout --kill-after=10s 60m python tools/acceptance/operator-journal/run.py \
  --candidate "$(git rev-parse HEAD)" \
  --project starlink-operator-362-final \
  --evidence /tmp/starlink-operator-362-final-evidence
```

Choose a new evidence directory and an unused private project for each run.
Provision Node 22.22.2, the locked frontend dependencies and Playwright Chromium
before running; acceptance never downloads runtime dependencies. Preserve the
actor's Docker context/socket. The runner records ownership before allocation,
checks OCI revision labels, uses an internal Docker network and closes all
project containers, private volumes, process groups and the loopback listener.
When rootless Docker suppresses published ports on an internal network, a
task-owned loopback byte relay reaches port 80 inside the production Nginx
container through Docker exec. It preserves network isolation and HTTP bytes;
the evidence records the origin, Nginx header, relay process and teardown. Only
acceptance fixtures are mounted; application code and the browser bundle come
from the production images. Synthetic simulation uses a fixed 1600Z clock.
Separate synthetic operational-format telemetry probes are explicitly labeled.

Mobile recovery covers an actual backend 503 caused by unwritable SQLite files.
It retains the draft, restores media access, reopens the backend and retries the
original key/body/epoch. A different test loses a browser acknowledgment after
the backend commits. Both inspect SQLite to verify exactly one receipt and
revision. Disposable stores additionally cover process termination around
commit, committed WAL, physical ENOSPC, read-only media, missing database,
unsupported schema and backup epoch rotation. These tests do not establish
hardware power-loss or aircraft readiness.

For first enablement, initialize the intended namespace, run `check`, take a
backup, and then enable Operator. There is no in-place schema upgrade beyond
migration 1. If a newer binary fails to open a store, disable Operator and
retain the entire independent volume before reverting the binary. Do not
initialize a replacement store to silence an error. Restore only an explicitly
selected, validated backup with access stopped; preserve its original manifest
and the restore report. Restart and reconcile clients against the new epoch.
Disabling Operator is the backout path that preserves all existing revisions and
receipts.

The acceptance report distinguishes the tested product SHA from later evidence
commits. Required CI still applies to the final pull-request head. Projection
artifacts remain foundation contracts; normal mission-package preparation now
includes their complete archival snapshot through issue #370.

## Operator workspace shell

The gated `/operator` workspace keeps the existing journal and adds read-only
mission summaries: the earliest future active call, next recorded risk and open
issues. Active calls include tentative, scheduled and delayed requirements.
Overdue active calls stay separately visible under Attention needed, so an
unconfirmed earlier call cannot obscure a future commitment. It reads the
existing schema-v1 records API; there is no new schema, migration,
transport-health inference or writable conference or issue API. Missing
associations and unknown/stale freshness remain explicit. Record scope describes
its association, not measured flight phase. The snapshot time is backend UTC,
including the injected clock in simulation. Refresh summaries explicitly; the
shell adds no interval polling. Pagination must finish before the shell claims a
complete summary. The existing 15-second shared health check remains unchanged.
Journal receipt/recovery does not wait for summary reads.

Desktop uses three summary columns. Mobile stacks upcoming information ahead of
journal entry, with section links and 44-pixel touch controls. Record
observation opens and focuses a clean journal editor; a dirty draft must be
saved or discarded before opening another. Display links reuse Overview and
Configuration; display mutations remain a separate slice. Missions continues to
own planning.

Rollback uses the existing feature gate (`OPERATOR_ENABLED=false`); journal data
is retained. No new infrastructure or storage is required. The production
acceptance runner now also captures three synthetic scope states at 1920×1080,
390×844 and 844×390, summary network failure/reconnect, restart with unchanged
record identities, keyboard entry, mobile navigation and the absence of extra
summary polling. These are software simulation checks, not aircraft validation.

## Operator Overview display controls (#364)

Expand **Display tools → Show display controls** in Operator. This mounts the
same visibility, boundary, history-window and display-command components used by
Configuration. Collapsing the controls releases their observers and display
channel. Advanced camera, terminal, weather/provider and diagnostic settings
remain in Configuration. Operator's existing enablement gate still applies.
Overview remains the passive customer-facing map; mission/planning and export
contracts are unchanged.

Visibility and history are installation-wide backend settings. Other browsers
and devices read confirmed state through the existing settings queries (five
seconds while the expanded controls are active). The display dropdown and
**Recenter view** use the existing same-origin BroadcastChannel discovery in the
same browser profile/storage partition. They do not control another physical
device. Match the displayed label; multiple or lost targets require explicit
selection. Recenter reports pending until the target acknowledges, then reports
acceptance of its automatic camera behavior, not completion of an animation.
Unacknowledged commands time out after three seconds. Silent windows expire
after fifteen seconds. **Open Overview** waits for new-window discovery and
reports popup/unavailable guidance when discovery fails. Remote fullscreen is
not offered.

**Normal**, **Communications** and **Weather** are three operator-owned preset
slots, initially empty. Save current visibility into a slot, then apply the
saved bundle when needed. Names do not imply factory-defined layers or measured
service availability. Bundles contain only the existing Overview links, metric
panels, information panels, route/POIs, own-aircraft and boundary visibility
switches. History, camera behavior, weather layers/providers and diagnostic
settings are outside these bundles. Saving a slot does not apply it. Applying a
bundle makes one atomic update through the existing visibility API, with its
actual saved response published to the shared query cache. Apply uses the last
confirmed preset snapshot and displayed version; a counterpart’s slot edits
appear on the next settings refresh.

The existing `PUT /api/overview-links/settings` accepts an optional
`expected_values` object with exactly the same keys as the supplied switches.
The file lock covers comparison and merge; a mismatched field returns HTTP 409
without writing. Disjoint changes merge. Legacy clients may omit the condition
and retain the existing last-write behavior. History updates similarly accept
`expected_window_seconds`; stale writes return 409. Updated editors use these
conditions and refresh saved state after failures. Network failures never
produce a saved message; inspect refreshed state before retrying an uncertain
write. This is configuration state, not an Operator journal event or transport
command.

`GET /api/overview-links/presets` returns the three slots, each null or
`{"version": 1, "settings": {"legend_enabled": true}}`.
`PUT /api/overview-links/presets/{normal|communications|weather}` requires
`settings` (a nonempty dictionary of recognized boolean switches) and
`expected_version` (0 for an empty slot). Saving compares the slot version under
the same file lock and returns the incremented version; conflicts return 409.
Storage failures return 503 and preserve the previous file. The UI waits for
this acknowledgment before showing a saved/applied state.

Presets are additive `operator_presets` metadata in the existing Overview link
settings JSON file, with no database schema migration, new volume or new
infrastructure. Existing settings writes preserve that metadata and unfamiliar
future fields. Back up the installation settings file with the deployment's
normal configuration backup. Old binaries ignore and retain the metadata;
rolling back the frontend/backend leaves saved visibility and preset data in
place. Disable Operator to hide its controls while Configuration remains
available. Do not delete shared configuration or Operator journal volumes for
rollback.
