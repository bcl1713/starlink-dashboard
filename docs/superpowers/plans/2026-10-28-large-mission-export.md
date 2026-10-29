# Large Mission Export Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. The user has
> instructed continuous implementation in this session; no further plan gate.

**Goal:** Export all retained telemetry and journal history with bounded memory,
including optional lossless compact telemetry.

**Architecture:** Stream pinned SQLite observations and sealed JSON through
bounded readers into immutable file-backed telemetry snapshots. Track capture
ownership and storage reservations in the shared export store. Assemble these
files directly into the final ZIP and retain legacy inline snapshot support.

**Tech Stack:** Python 3.11, SQLite WAL/incremental BLOB reads, standard-library
JSON/CSV/ZIP, FastAPI, React/TypeScript.

**Spec:** [Design](../specs/2026-10-28-large-mission-export-design.md).

## Global Constraints

- Full detail remains the default; compact never downsamples observations.
- Preserve complete source labels, missingness, original UTC/source timestamps,
  journal history, planning history, partial labels and archive-only import.
- Stream sealed TEXT directly through read-only `blobopen`, at most 64 KiB/read.
- Keep the 256 MiB uncompressed supplementary-member limit and explicit errors.
- Keep export controls off Overview and preserve the actor's Docker endpoint.
- Every runtime check has an explicit timeout and task-owned cleanup.

## Review Focus

- UTF-8 splits, malformed/truncated sealed JSON, and excessively large records.
- High-cardinality labels must not grow an in-memory series dictionary.
- Cancellation before job acknowledgment must release disk reservations.
- Restart/handoff must use captured bytes and never delete active readers.
- Capacity errors must survive ZIP-oriented HTTP error handling.

## Task 1: Bounded source readers and telemetry writer

**Files:** telemetry_archive/stream_reader.py, stream_package.py, compact.py,
store.py; tests/unit/test_streaming_telemetry.py.

**Interfaces:** `read_capture(db, rowid)` returns bounded metadata;
`iter_capture_samples(db, rowid)` yields sealed observations;
`write_telemetry_package(output, mission_id, captures, format, workdir, check)`
returns member digests/counts. Captures supply metadata and single-pass samples.

- [ ] Write and observe failing tests for full/compact observation
      reconstruction, sealed rows after rolling deletion, UTF-8/truncation, and
      concurrent WAL writes.
- [ ] Implement bounded JSON framing with per-record limits, snapshot cursors,
      disk-backed compact series IDs, incremental CSV/ZIP/checksums and
      descriptions.
- [ ] Run the focused tests and legacy telemetry package/preparation tests.
- [ ] Commit the independently verified source/writer changes.

Compact members: `series.csv` (`series_id,metric,labels_json`) and
`observations.csv`
(`timestamp_utc,series_id,value,availability,source_observed_at_utc`). Full
observations retain existing columns. IDs hash complete canonical identities.
Nulls remain empty with explicit availability; all CSV text is formula-safe.

## Task 2: Owned disk snapshots and mission assembly

**Files:** mission/package/archive_files.py, operations_archive.py,
preparation.py, preparation_store.py, preparation_worker.py, main.py;
tests/unit/test_archive_files.py and operator/test_mission_archive.py.

**Interfaces:** capture owners reserve disk before creation, pin a 600-second
deadline, publish sidecar descriptors, attach to a job atomically, and release
unattached captures on every exit. A shared registry stores owner/job/lease and
reserved/actual bytes. Worker-owned cleanup handles terminal attached captures.

- [ ] Write and observe failing real-filesystem/SQLite tests for pre-ack
      failure, ready-job reuse, quota rejection, handoff/restart, and immutable
      attachments.
- [ ] Add file-backed capture alongside the legacy inline API, and include
      content digests plus representation in fingerprints without random path
      IDs.
- [ ] Stream sidecar entries into the final partial ZIP; reserve overlapping
      source/spool/final output and retain restart-safe immutable metadata.
- [ ] Test failure/deadline/cancellation/expiry and verify owned resources
      vanish.
- [ ] Commit the verified ownership and assembly changes.

## Task 3: API, operator selection, and useful errors

**Files:** preparation_routes.py, routes_v2.py, export_job.py, nginx.conf,
export-import.ts, ExportDialog.tsx and their tests.

**Interfaces:** `telemetry_format=full|compact` selects representation on both
preparation entrypoints. Known errors use `mission_archive_capacity` with a safe
message identifying the layer/limit, and `mission_archive_deadline` for capture
timeouts. Unknown server exceptions remain generic.

- [ ] Write and observe failing API and UI tests for compact selection,
      malformed selection, readable Blob JSON errors, and cancellation before
      acknowledgment.
- [ ] Run owned capture work in a disconnect-aware request helper and give both
      preparation entrypoints the same bounded Nginx handling.
- [ ] Run backend export suites and frontend export tests, then commit.

## Task 4: Acceptance, review, and remote delivery

**Files:** task-specific acceptance probe and export documentation.

- [ ] Demonstrate above-old-budget active and sealed archive exports through
      production Nginx in both representations and entrypoints; reconstruct and
      hash source observations, including location/speed/altitude/heading and
      GEP labels.
- [ ] Measure peak RSS and writer latency with a paused pinned reader, including
      high-cardinality labels; exercise capacity/pre-ack cancellation/deadline
      paths.
- [ ] Run applicable canonical static/backend/frontend checks with owned
      runners.
- [ ] Obtain the executing-plans skill's required independent whole-branch
      review, fix confirmed findings, and verify runtime teardown.
- [ ] Push and update PR #441 around the implemented behavior and actual
      evidence.

## Execution ledger

- Started at `2837319b`; isolated branch `fix/large-mission-export`.
- Ruling: proceed without another approval round. The user's explicit correction
  authorizes implementation; repeating design/plan gates would conflict with it.
