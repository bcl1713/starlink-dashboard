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
  ordered by effective UTC occurrence time, with acceptance sequence breaking
  ties. Issue corrections use the existing issue-message effective time rather
  than the issue's current-state timestamp. `chronological_activity` supplies
  that effective time, its basis and immutable correction lineage alongside each
  revision. Unknown actual times follow known actual times. Planned times remain
  separate; they are never presented as observations. Superseded originals
  remain present.
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

## Size and resource limits

The import HTTP endpoint accepts a complete ZIP up to **2 GiB** (2,147,483,648
bytes). Production Mission Planner Nginx permits 2 GiB plus 1 MiB for multipart
framing; the application checks the ZIP's actual spooled-file length. An exact 2
GiB ZIP is accepted; larger files return an attributable `413` with
`mission_package_too_large`. Other upload endpoints retain their existing
limits. The original 100 MiB whole-ZIP limit was insufficient for telemetry-rich
archives.

Import uses Starlette's disk-spooled upload directly, without reading the whole
ZIP into memory. Before constructing ZIP entries, a bounded standard-library
classic/ZIP64 footer read enforces at most 10,000 entries and a 16 MiB central
directory. Planning members (`mission.json`, `planning/`, `routes/`, `pois/` and
`itinerary/`) have a separate **100 MiB expanded-byte total**. This keeps
planning materialization bounded while rejecting excessive compressed planning
expansion before reading or publishing it. Journal, telemetry and briefing
members are neither inflated nor applied during plan import. Keep adequate
temporary disk capacity for both the Nginx request body and backend upload
spool; a near-limit upload can temporarily use approximately 4 GiB across the
two services. The limits apply to legacy and enhanced packages alike. The import
rate limit is unchanged.

Export still uses the existing local capture/build architecture. Each journal
and telemetry capture has a **128 MiB input budget**; journal rows and unsealed
telemetry rows include a conservative per-row allowance, and sealed telemetry
JSON is checked by byte length before loading. The complete added UTF-8 member
set is limited to **256 MiB**. JSON-escaped persisted snapshots have a **384 MiB
per-job** limit and a **768 MiB aggregate live-payload quota** in the existing
slide-cache database. These are deliberately finite initial archive capacities,
not promises that arbitrarily long or dense telemetry histories fit. Source
records and telemetry are never deleted to fit an export. Large histories that
exceed a capacity fail the entire preparation and require a future streaming
archive implementation or a deliberately reviewed capacity change.

Only one request capture per export service runs at a time; a concurrent request
receives a retryable archive-unavailable response. Snapshot strings are escaped
in 16 KiB chunks, and cache fingerprints are hashed incrementally. Capacity
checks and the queued-job insert are atomic: rejection creates no acknowledged
job or partial archive. The elected worker still bounds assembly concurrency.
These bounds constrain data volume; Python row/model expansion and overlapping
capture/assembly can use several times the raw bytes in memory. Deployment
memory must account for that amplification. Production acceptance reports
measured peak RSS rather than claiming constant-memory export.

Failed, cancelled, superseded and expired jobs delete their snapshot rows.
SQLite reuses freed pages; the database file need not shrink on disk, and the
live-payload quota is not a physical database-file-size cap. Do not run blocking
`VACUUM` on the active shared cache. Ready ZIPs and their snapshots retain the
existing 30-minute expiry and restart behavior. Storage exhaustion fails
preparation; it never produces a truncated success. The limits do not restrict
retention in the independent source Operator or telemetry stores.

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

The large-capacity probe starts at the frozen supplementary-file boundary and
exercises production persistence, ZIP assembly and HTTP import with a synthetic
36-hour CSV workload. It does not demonstrate that this dense history fits the
128 MiB source capture budget. The separate end-to-end multi-leg scenario tests
real journal and telemetry capture; input-limit regressions verify complete
rejection rather than truncation when source capture capacity is exceeded.

## Inferred flight events and reconciliation

Mission Planner separates estimated event occurrence from later confirmation.
**Estimated landing** is probable ground arrival from GPS/Starshield PNT
movement and altitude evidence, not measured wheel contact. Manual event
creation and correction remain available when the event ledger is usable; supply
the observed UTC time and reason. When the ledger itself is unavailable,
preserve the crew's observed times and reconcile after recovery. A selected live
mode or healthy metrics stream alone does not prove that detection and recording
are available. The Flight recording panel shows each stage and recovery action
without requiring acknowledgement before saving or using a mission plan.

The final KML waypoint is a route reference, not a parking stand. The existing
configurable `destination_radius_m` defaults to 10,000 m as supporting airport
vicinity context. It is not an airport polygon, a calibrated airport boundary or
a sufficient landing criterion. Large airports or off-center route references
may require a deliberate policy adjustment and operator reconciliation. No
external airport-data service is required. Landing, taxi-in and parking may all
occur beyond the old 100 m endpoint circle.

Engineering defaults in `FLIGHT_DETECTION_POLICY` require established flight and
descent of at least 200 feet, ground-like groundspeed below 35 knots sustained
for 20 seconds, altitude span at most 75 feet and fitted altitude trend at most
1 foot/second in magnitude. The trend tolerance is a conservative engineering
choice, not calibration from this aircraft's flight. Bounded altitude noise and
runway slope can qualify; continuing descent/climb, renewed acceleration or a
go-around interrupts confirmation. Dwell uses fresh distinct altitude evidence;
repeated/out-of-order timestamps, missing altitude and observation gaps cannot
supply confirmation. Frozen sensor values without fresh provenance remain
uncertain. Freshly timestamped identical values alone cannot establish whether a
sensor has physically frozen: GPS inference cannot eliminate that ambiguity. GPS
altitude is MSL, not AGL or pressure altitude; neither zero altitude nor a
published airspeed/stall threshold establishes ground contact. Strong headwind
and ambiguous approach evidence still call for operator judgement.

Occurrence is the beginning of the supported low-speed stable-altitude
candidate; confirmation is later, after dwell. This change does not extrapolate
or backdate to an earlier matching altitude or unrelated level approach. The
detector is not an exact touchdown-time reconstruction tool. Taxi-in and
on-blocks remain distinct from landing, with parking below 1 knot inside a 50 m
local dwell area for 300 seconds. Departure taxi holds do not become destination
parking. Defaults are configurable and not aircraft operating limits.

The archive still starts 30 minutes before off-blocks and ends 30 minutes after
the first confirmed destination on-blocks occurrence, including DV offload. It
never seals at touchdown; later repositioning does not extend that destination
capture. Raw extraction/recovery must finish or exhaust its bounded retries
before sealing. Unavailable samples/history remain labeled partial rather than
invented. See
[storage and runtime recovery](../troubleshooting/data-issues.md#live-flight-detection-and-recording).
