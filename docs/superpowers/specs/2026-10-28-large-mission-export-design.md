# Large mission exports without losing recorded detail

## Intent and agreed scope

An in-flight mission export failed after about 34 seconds with
`Telemetry archive input size limit exceeded`. The same interval included a
`SQLITE_BUSY` failure while recording live samples. The user needs to get the
complete available dataset off the machine, retain journal history, and process
it separately, potentially using an LLM to prepare an after-action report.

The user chose a reliable full export plus an optional smaller dataset.
Subsequent clarifications require preserving observations rather than generating
analyses: location, speed, altitude, heading, all other retained telemetry,
GEP/IP metadata, source labels, timestamps, missingness, and full journal
history. Compact means lossless normalization, not time averaging or
downsampling. Pattern detection, predicted-versus-observed matching,
recommendations, and report generation are outside this change.

## Approaches

1. Raise the current memory limits. This leaves repeated in-memory copies and
   long database readers in place; it merely moves the failure point.
2. Stream the complete archive into private files and offer a compact lossless
   telemetry representation. This addresses the observed failure and reduces
   processing overhead without dropping evidence. This is the selected approach.
3. Export only time-bucketed summaries. This reduces rows but loses details
   needed for later analysis of movement, transitions, and short impairments.
   The user's clarification rules this out.

## Existing failure path

Mission preparation captures the Operator journal and telemetry before queuing
assembly. Active telemetry reads accumulate Python dictionaries under a 128 MiB
budget that includes a conservative allowance per row. CSV generation then
builds whole lists and strings, creates an in-memory telemetry ZIP, extracts its
members again, and embeds them as strings in a persisted JSON snapshot. Larger
histories can fail even when their compressed exports would be modest.

The archive uses SQLite's default journal mode. A long export read can impede a
recording writer. The traceback establishes the input budget as the export's
failure cause; the log alone does not establish that all database contention
came from that export.

## Export contract

- Full format keeps the existing mission ZIP, planning/import members, customer
  PDF behavior, Operator archive, and telemetry CSV schemas. All retained live
  observations within each pinned per-leg revision's capture range remain
  represented, including history retained in earlier sealed revisions when a
  correction reopens a leg. Revision identity and provenance remain explicit;
  the export need not duplicate whole historical revision packages.
- Compact format keeps planning and complete journal/event history, but encodes
  telemetry using a per-leg series dictionary and observation rows referencing
  series IDs. It explicitly identifies its format and schema in the manifest. It
  retains every observation and its original timestamp and source timestamp.
- Series identity includes the complete original metric and label mapping.
  Distinct IPs, locations, collectors, provenance sources, and concurrent series
  never merge. Unknown freshness, nulls, and measured zero remain distinct.
- A compact export is smaller to parse and does not require repeated JSON label
  parsing. It is not advertised as a particular compression ratio or as fewer
  samples. Full detail remains the default for compatibility.
- Include a short machine-readable dataset description plus a README describing
  member paths, UTC fields, source/freshness semantics, missingness, and the
  compact join. Neither file contains generated operational conclusions.
- Preserve the complete journal's acceptance-order audit, chronological views,
  corrections, deletions, and persisted modeled-event history. Preserve planning
  snapshots and their source revisions. Do not invent historical predictions
  that were not retained, or label the current plan as the original preflight
  prediction.
- Cached egress geolocation remains proxy evidence with unknown freshness where
  that is all the recorder retained. An IP or location change is not relabeled
  as a verified network handover or service outage.
- In-flight and unrecorded legs keep their existing explicit partial/gap labels.
  No new uncertainty acknowledgment is required.

## Streaming and snapshot ownership

Introduce a telemetry archive writer that accepts iterators and writes CSV rows,
ZIP entries, and checksums incrementally. The mission path must not use the
legacy list-returning capture to accumulate the complete active-leg history.
Small callers can keep the existing bytes-returning helper as a compatibility
adapter to the new writer.

An export read pins capture heads, capture metadata, and observations in a
consistent SQLite read transaction. Configure the telemetry archive for WAL so
recording writers can proceed while that read is active. Close its cursors and
connection on success, failure, timeout, and cancellation. Do not change the
independent flight-event ledger's journal mode as an incidental change.

Active observations stream from the pinned database cursor. Sealed revisions
remain authoritative after rolling data expires; their retained JSON samples
must also be read incrementally, rather than loaded into a complete Python list.
For sealed data, select the capture's SQLite row ID without selecting its
`payload` TEXT, then open that column with Python 3.11's read-only
`sqlite3.Connection.blobopen`. Feed a reader capped at 64 KiB per read into the
incremental parser on the same pinned connection. Retrieving the complete TEXT
value and only then parsing it incrementally does not meet this requirement. Use
a maintained incremental JSON parser if needed; any dependency change must
regenerate the repository's hashed CI requirements and receive container checks.
Per-row and metadata limits remain explicit.

Compact series deduplication must also stay bounded. Use a task-owned
disk-backed index of complete metric/label identities and stream its dictionary
rows; do not retain an unbounded Python mapping of every series. Include that
index, parser buffers, individual records, SQLite caches, and compression
buffers in the memory and disk measurements. High-cardinality labels must remain
lossless even when almost every observation introduces another series.

For a recovering head, stream earlier sealed observations within its declared
range and merge rolling observations with rolling precedence. Use the same
bounded disk index for deduplication and compact series so additional history
does not introduce an unreserved second index.

Freeze the telemetry projection into a compressed, immutable private sidecar.
Persist only its generated identifier, format, size, checksum, and component
metadata with the queued job. Do not serialize its CSV bytes into JSON. Resolve
identifiers inside the service-owned artifact directory; clients cannot supply
filesystem paths. Assembly copies sidecar members into the final ZIP in bounded
chunks and calculates outer member checksums without loading those members.

The sidecar must be durable before acknowledging a queued export. Current
sequential component-capture semantics remain explicit. Capture includes a real
deadline and byte checks, not just a tool or HTTP output timeout. Route/proxy
handling must cover both supported preparation entrypoints consistently.

The preparation identity includes telemetry contents, representation, and frozen
journal/planning identity. Changes after capture cannot rewrite an existing job.
Existing inline snapshots remain readable after upgrade. Restarted workers use
the persisted sidecar; they do not recapture later observations or journal
edits.

Keep finite disk and output quotas. Replace the telemetry's aggregate in-memory
input limit with bounded streaming buffers; do not silently truncate data to
fit. Retain the existing supplementary output limit initially and account for
sidecar bytes in the live artifact quota. If a genuine output/disk limit is
reached, return an actionable capacity error and preserve source history.
Compact format offers a lower-overhead representation of the same observations.

The 256 MiB supplementary-member limit remains a limit on the sum of actual
uncompressed supplementary members, including journal files, telemetry members,
dictionary rows, and dataset descriptions. A successful smaller compressed ZIP
does not bypass it. This design supports larger input histories with bounded
memory; it does not promise unlimited history. The error must name the capacity
that was exceeded and must never return a truncated success.

### Ownership and quota transitions

Generate a capture owner ID and reserve storage in the shared export store
before creating a sidecar or compact index. Track their generated identifiers,
reserved bytes, actual bytes, state, owning job when attached, and a renewable
lease. Reserve additional capacity atomically before writing additional bytes;
an HTTP request's lifetime alone is not an ownership record.

| Transition                                     | Required ownership and cleanup behavior                                                                                                                                                         |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Capture before acknowledgment                  | Own `.part` files and the compact index through the capture record; enforce cancellation, deadline, lease, and quota checks before acknowledgment.                                              |
| Capture failure, disconnect, or deadline       | Close readers and writers, delete only that capture's temporary artifacts, and release its reservations without inserting a queued job.                                                         |
| Sidecar publication and job attachment         | Flush and sync the sidecar before atomic publication; attach its immutable identity and ownership to the persisted snapshot and queued job before acknowledgment.                               |
| Reuse of an existing ready job                 | Keep the existing job and its artifacts; dispose of the newly captured duplicate and release its reservations before returning the reused job.                                                  |
| Assembly                                       | Reserve and count the growing final ZIP while its sidecar still exists. Temporary spools, the sidecar, compact index, and final ZIP must not occupy unaccounted storage concurrently.           |
| Restart or elected-worker handoff              | Recover attached jobs from their persisted immutable artifacts. Reclaim unattached or abandoned files only after proving the prior lease is no longer valid.                                    |
| Ready publication                              | Once the final ZIP is durable and published, release sidecar/index data that no longer has a reader or recovery purpose. Retain sufficient immutable metadata for ready-job identity and reuse. |
| Failure, cancellation, supersession, or expiry | Close any owning worker before removing its files, release reservations idempotently, and preserve source history and other jobs' artifacts.                                                    |

The implementation plan must define transaction boundaries and crash recovery
for a failure between each filesystem and database step, including deletion
failure. File ownership, quotas, and leases must work across processes; an
in-process lock is insufficient. Active readers retain ownership until they
close, so a cleanup worker cannot remove an artifact still in use.

Completed, failed, cancelled, superseded, expired, interrupted, and abandoned
jobs must release their owned sidecars when no longer needed. Cleanup must work
across restart and elected-worker handoff and must never delete recorder source
databases or other jobs' artifacts. Ready downloads retain their existing expiry
and immutable bytes.

## Operator flow and error reporting

Add Full detail / Compact lossless selection to the existing mission export
dialog. Explain that compact retains observations and uses a series dictionary.
Keep this control off Overview. Include the selection in API validation and job
identity. Existing API calls continue to select full detail by default.

Propagate known capacity/storage errors through the export API and decode JSON
error bodies even when the request expected ZIP bytes. Show specific recovery
guidance for those known errors, without exposing arbitrary server tracebacks.
Maintain cancellation, progress states, and download behavior.

The separate `/export` Prometheus CSV remains available. Its resolution-based
queries are not relabeled as the mission archive's individual raw observations.

## Verification and acceptance

- Reproduce the original failure with synthetic live observations exceeding the
  old budget, and demonstrate a complete export with matching counts/checksums.
  The scenario must begin at real archive rows and the actual HTTP preparation
  boundary, not at already-frozen CSV bytes. Record the old budget calculation,
  source counts, reconstructed counts, and member digests.
- Verify full and compact representations reconstruct the same observations,
  including labels, nulls, zero, source times, GEP/IP changes, and concurrent
  series. Verify location, speed, altitude, and heading explicitly.
- Export a large sealed leg after rolling-row deletion; compare its retained
  evidence. Measure the entire SQLite-to-parser-to-ZIP read path and reject
  tests that first load the sealed payload into a full Python string or list.
- Exercise compact output with high-cardinality label mappings as well as many
  repeated observations. Verify bounded memory, complete dictionaries, and
  lossless joins in both cases.
- Use separate real SQLite connections to prove recording can commit during a
  deliberately paused export read. Measure writer latency and export peak RSS.
- Change or correct sources after capture and verify ready downloads remain
  immutable. Exercise restart, handoff, cancellation, deadline, quota
  exhaustion, missing/corrupt sidecars, expiry, and orphan cleanup.
- Preserve complete journal audit/corrections/deletions, plan-only import,
  partial labels, all checksums, and existing package/customer-PDF behavior.
- Verify both selections and readable errors in the rendered mission planner.
  Exercise both preparation entrypoints through production Nginx, for full and
  compact output. Cover cancellation, disconnect, deadline, and capacity errors
  before a queued-job acknowledgment as well as during background assembly.
- Run applicable canonical backend/frontend/static checks and isolated committed
  production Docker/Nginx/browser acceptance. Record ownership and explicit
  wall-clock limits, then verify all task runtime resources are removed.
- Push the feature branch and open a pull request against `dev`; preserve its
  worktree for review. Updating the user's running aircraft-side installation is
  a separate deployment step after review.

## Builder discretion

Choose internal module boundaries, buffer/page sizes, stable deterministic
series ID construction, and incremental-parser implementation. Preserve the
contracts above. The implementation plan should specify the exact compact column
names, limit/error codes, artifact layout, and cleanup transitions before
coding.
