# Mission ZIP journal archive

The existing mission ZIP remains the single product for customer briefing,
portable mission-plan transfer and mission archival. Use the existing Missions
Export control, then extract only `exports/mission/<mission-name>-brief.pdf` for
the customer. The complete ZIP also contains internal operational records and
historical text. Existing filenames, planning files, CSVs, PDF preparation
cache, job polling, cancellation and ready-download expiry remain unchanged.

When Operator is enabled, normal mission export includes complete current
records, immutable full-text revision history (including corrections, removals
and restores), #369 transport decisions, provenance and original UTC timestamps.
It does not query Prometheus, refresh forecasts or require optional providers.
An enabled but unavailable journal fails preparation rather than silently
publishing an empty history. Disabled Operator is labeled in the outer manifest.

## Archive contents and validation

- `operations/current.json`: existing current-state projection.
- `operations/activity.jsonl`: existing acceptance-sequence activity projection.
- `operations/audit.jsonl`: full original revisions, in acceptance order.
- `operations/journal.json`: schema-versioned current records and all revisions
  ordered by actual UTC occurrence time, with acceptance sequence breaking ties.
  Unknown actual times follow known actual times. Planned times remain separate;
  they are never presented as observations. Superseded originals remain present.
- `operations/events.json`: persisted modeled advisory occurrences, event heads,
  transitions, notification tiers and acknowledgments. This captures existing
  #348/#368 results without recalculating predictions during export.
- `operations/handover.txt`: current-record handover snapshot.
- `operations/manifest.json`: journal identities, source mode, high-water
  sequence, versions, associations and SHA-256 digests of all other journal
  files.
- `telemetry/`: existing #349 telemetry package members under one collision-free
  prefix, preserving its inner manifest, ordered leg paths, observation/event
  CSV schemas, gaps and immutable capture revisions. No second flight detector
  or per-leg archive is introduced. Missing/unsealed legs remain explicitly
  partial; normal mission archival requires no confidence acknowledgment. The
  existing explicit telemetry-only endpoint retains its original partial-request
  contract.

The existing outer `manifest.json` stays version 2.0. Additive
`archive_components` identifies component capture boundaries, source modes and
checksums for all added members; `file_structure.archive_files` lists them.
Validate SHA-256 over the unmodified UTF-8 member bytes, compare the outer and
journal manifests, then validate journal schema versions and stored identities.
Telemetry manifests retain their own observation/event checksums.

Operator revisions and persisted event tables share one SQLite read snapshot.
The manifest distinguishes the actual journal capture interval from the last
revision's recorded time. Planning is protected by the existing capture token
and supersession checks. Telemetry pins each leg's existing capture revision.
These are sequential component snapshots, not a simultaneous transaction across
stores. The planning fingerprint identifies its input boundary. Operator edits
after capture belong to the next export and do not rewrite a prepared download.

## Portable mission-plan import

Existing ZIP imports continue to import only mission/planning data and routes.
New archival members are ignored by ordinary plan import. Import never restores,
merges, duplicates or overwrites the destination's Operator records or telemetry
archive database. Keep the original ZIP to retain its archival members;
importing and re-exporting a plan is not a historical journal restoration
workflow. Dedicated historical restoration remains outside issue #370.

## Persistence, migration and rollback

Frozen supplementary files are committed with the queued export job in the
existing slide-cache SQLite database before the request is acknowledged. The
additive `export_archive_snapshots` table requires no Operator database
migration, new volume or external service. Cache identity includes journal/event
bytes and telemetry revisions. Queued jobs use their persisted snapshot after
restart; abandoned preparing jobs retain the existing explicit failed/retry
behavior. Ready ZIPs survive restart unchanged until their existing 30-minute
expiry. Failed, cancelled, superseded and expired jobs release supplementary
snapshots.

Back up mission storage, the independent Operator store and #349's archive roots
using their existing procedures. Rollback to the previous binary ignores the
additive export table and ZIP members; keep data intact. Disabling Operator
hides its interface and omits future journal captures without deleting saved
history. Existing ready packages retain their captured contents until expiry. Do
not copy an exported journal into an active database.

## Synthetic acceptance

The owned runner builds exact committed production images, uses production Nginx
and the existing browser controls, and starts a clean second backend with
private storage on the same isolated network:

```sh
timeout --kill-after=10s 90m python tools/acceptance/operator-journal/run.py \
  --archive --candidate "$(git rev-parse HEAD)" \
  --project starlink-operator-370-example \
  --evidence /tmp/starlink-operator-370-example
```

Use a new project and evidence directory for every run. It drives real #349
flight-state detection, takeoff/landing/on-blocks and both leg archives with
synthetic operational-format samples, explicitly distinguished from the
simulation-mode Operator records. The fixture has no aircraft, terminal,
Prometheus or external provider. Sparse synthetic metrics retain labeled gaps;
no complete measured service claim is made. Evidence includes an independently
extractable real customer PDF, complete example ZIP, independent digest checks,
clean-instance plan import with unchanged destination journal, legacy import,
repeated downloads, retrospective edits, restart and desktop/mobile captures.
The runner tears down its processes, containers, networks, volumes and image
tags.
