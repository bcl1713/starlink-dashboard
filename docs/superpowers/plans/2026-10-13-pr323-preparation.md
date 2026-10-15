# PR323 Preparation and Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve issue 325 with responsive preparation, visible bounded export
state, consistent snapshots, and owned byte-block ZIP delivery.

**Architecture:** Short raw-input capture feeds normalization outside the global
gate and token-checked cache publication. Reuse the slide cache for shared
preparation; persist owned export jobs and ready files separately from slide
BLOBs.

**Tech Stack:** Python 3.11, FastAPI/Starlette, SQLite, existing bounded process
supervision, tempfile, React/TypeScript, Vitest, and real Uvicorn/HTTP probes.

**Spec:**
[Approved design](../specs/2026-10-13-pr323-operator-and-export-repair.md).

## Global Constraints

- All constraints and commands in [the parent plan](2026-10-13-pr323-repairs.md)
  apply. Reuse PR323; preserve snapshot/source ownership and package schema.
- ZIP blocks: 64 KiB. Spool threshold: 8 MiB. Ready-package lifetime: 30
  minutes. Renderer-job limit: 120 seconds. Preparation limit: 600 seconds from
  request.
- Two-second health/status/mission deadlines are acceptance criteria, not larger
  proxy timeouts. No long synchronous lock wait or heavy CPU work on the ASGI
  loop.

## Review Focus

- Binary data containing many newlines must remain byte-identical (Task 1).
- A capture overtaken by a saved change cannot restore stale cache work (Task
  2).
- Disabled preparation and expired/cancelled jobs must remain recoverable (Task
  3).
- Cancelling one export cannot cancel another's shared slide preparation (Task
  3).
- Worker failure, signals, and thread saturation must preserve probe failures
  and verify reaping rather than merely produce an average latency (Task 4).

## Task 1: byte-block streaming and owned package assembly

**Files:** Create `backend/starlink-location/app/mission/package/streams.py`.
Modify package `export_job.py`, `customer_artifacts.py`, `snapshot_export.py`,
and `__main__.py`. Test
`backend/starlink-location/tests/unit/test_customer_export_job.py` and
`test_customer_package.py`.

**Interfaces:** Preserve `OwnedZipResponse(stream, *, headers)` and
`MissionPackageDownload(stream, briefing)`. Add
`iter_zip_blocks(stream: IO[bytes], block_size: int = 65536) -> Iterator[bytes]`
and `new_package_stream() -> IO[bytes]` in `streams.py`, using an 8 MiB spooled
temporary file; both package builders import this helper without a circular
import. Streams are private owned handles, never returned as arbitrary
filesystem paths.

- [ ] **Step 1: Write behavior regressions.** Add
      `test_zip_blocks_preserve_bytes` and `test_package_spools_and_closes`. For
      a multi-block newline-heavy ZIP, assert
      `sha256(downloaded) == sha256(source)`, every block is at most 65536
      bytes, and all but the final block have that length. Assert closure after
      normal send, disconnect, send error, repeated cancellation, and assembly
      failure. Force a package past 8 MiB and assert disk spooling without
      changing ZIP members/schema.
- [ ] **Step 2: Run RED.** Backend selection:
      `tests/unit/test_customer_export_job.py`
      `tests/unit/test_customer_package.py`. Demonstrate current line
      iteration/assembly ownership failures separately from fixtures that
      already pass.
- [ ] **Step 3: Implement the interfaces.** Feed fixed-size reads to the
      existing response ownership wrapper. Replace duplicate whole-ZIP BytesIO
      assembly with private spooling and stream-copy entries in 64 KiB blocks.
      Check cancellation during entry copies and preserve PDF/evidence pairing
      and source/history members.
- [ ] **Step 4: Run GREEN and package controls.** Run the selection plus
      `tests/planning/test_packages.py` and
      `tests/unit/test_export_snapshot.py`. Inspect peak allocation/spooling for
      a representative large package and retain hash/member comparisons;
      response iteration cannot consume or close a different job's file handle.
- [ ] **Step 5: Commit.** Commit only the selected files as
      `fix: stream mission ZIPs in owned byte blocks`.

## Task 2: short capture, cheap cancellation, and ordered background updates

**Files:** Create
`backend/starlink-location/app/mission/slide_cache/capture.py`. Modify
`slide_cache/coordinator.py`, `identity.py`, `persisted_pois.py`, `store.py`,
`prepared_export.py`, `exporter/snapshot_inputs.py`, and
`backend/starlink-location/main.py` and `app/mission/routes_v2.py` for async
guarded read boundaries. Test `tests/unit/test_slide_coordinator.py`,
`test_export_snapshot.py`, and
`tests/integration/test_live_background_route.py`.

**Interfaces:** In `capture.py`, define frozen `RawCapture` with mission ID,
immutable metadata/source bytes, renderer revision, and a dependency token.
Provide `capture_raw(mission_id, route_manager, poi_manager) -> RawCapture`, and
`capture_is_current(raw: RawCapture) -> bool`. Define normalization as:

```text
normalize_capture(raw: RawCapture) -> tuple[
    bytes, tuple[SourcePayload, ...], tuple[str, ...], dict[str, str]
]
```

The last dictionary is leg ID to fingerprint. Keep `capture_inputs`' existing
public return shape. Add
`SlideStore.status_records(mission: str) -> dict[str, dict]` without artifact
BLOBs.

- [ ] **Step 1: Pin the critical section and races.** Add
      `test_normalization_releases_active_gate`,
      `test_superseded_capture_cannot_enqueue`, and
      `test_telemetry_updates_remain_ordered`. Hold normalization behind a test
      barrier and prove another guarded reader proceeds. Supersede a captured
      mission/route/POI/catalog/coverage dependency and assert it cannot enqueue
      over newer work. Assert cancellation checks never call `reconcile_all`;
      assert progress queries never select PDF/snapshot/inputs BLOBs. Verify
      telemetry updates never overlap, and replay order/metrics remain the same
      after offloading.
- [ ] **Step 2: Run RED.** Backend selection:
      `tests/unit/test_slide_coordinator.py`
      `tests/unit/test_export_snapshot.py`
      `tests/integration/test_live_background_route.py`. Barriers use bounded
      waits and cleanup, not sleep-based ordering assumptions.
- [ ] **Step 3: Implement capture and dispatch.** Copy committed raw bytes under
      the current lock order, without validating the full planning graph or
      serializing proposal payloads there. Normalize outside the gate; recheck
      all captured mutable dependencies before token-checked queue publication.
      Retain recovery and external-change detection. Memoize deployed renderer
      identity per runtime; development asset changes explicitly invalidate it.
      Check cheap stop/token state during rendering instead of parsing all
      missions every second. Dispatch one owned telemetry update at a time off
      the event loop and drain it at shutdown, including paced replay and
      disconnected/live paths. Dispatch guarded async mission/list reads away
      from the event loop while preserving error semantics.
- [ ] **Step 4: Run GREEN and concurrency control.** Run the selection and
      `tests/unit/test_slide_cache.py`. Exercise real-server probes from Task 4.
      If Python normalization still starves the loop through the GIL, execute
      the picklable `normalize_capture` in the existing owned `run_bounded`
      process path, using the remaining job deadline; repeat the same probe
      without widening it.
- [ ] **Step 5: Commit.** Commit as
      `fix: shorten customer preparation critical sections`.

## Task 3: preparation jobs, bounded downloads, and visible UI state

**Files:** Create `backend/starlink-location/app/mission/package/preparation.py`
and `preparation_routes.py`; modify `slide_cache/store.py`,
`package/export_job.py`, `customer_artifacts.py`, `prepared_export.py`,
`backend/starlink-location/main.py`, and `app/mission/routes_v2.py`. Modify
frontend `src/types/export.ts`, `services/export-import.ts`, and
`components/missions/ExportDialog.tsx`. Add backend
`tests/unit/test_export_preparation.py`; extend `tests/planning/test_api.py`,
frontend `services/export-import.test.ts`, and `ExportDialog.test.tsx`.

**Interfaces:** Define `ExportPreparation` with ID, mission ID, state, captured
revision/fingerprint, stage, per-leg states, queued/started/finished timestamps,
deadline, expiry, sanitized warning/error codes, and optional download URL.
Implement `ExportPreparationService.start(mission_id) -> ExportPreparation`,
`status(mission_id, job_id) -> ExportPreparation`,
`cancel(mission_id, job_id) -> ExportPreparation`,
`open_download(mission_id, job_id) -> MissionPackageDownload`, and
`close() -> None`. Store metadata in the existing cache SQLite database and
owned artifacts below its private directory; serialize assembly through the
owned service runtime.

Expose POST `/api/v2/missions/{mission_id}/export-preparations` (202), GET and
DELETE `/api/v2/missions/{mission_id}/export-preparations/{job_id}`, and GET
`/api/v2/missions/{mission_id}/export-preparations/{job_id}/download` (200
ready, 409 not-ready/superseded, 410 expired). Legacy POST
`/{mission_id}/export` returns 200 for an already ready current package,
otherwise 202 with a preparation reference and Location. No download endpoint
waits for cold rendering.

Frontend adds `prepareMissionExport`, `readMissionExportPreparation`,
`cancelMissionExportPreparation`, and `downloadPreparedMissionExport`; each
accepts an AbortSignal. Preserve the existing public convenience helpers by
having them use this explicit workflow and parse legacy 202 JSON correctly.

- [ ] **Step 1: Write state/lifecycle tests.** Add
      `test_preparation_deadline_is_not_reset`, `test_ready_package_expiry`, and
      `test_cancel_keeps_shared_preparation`. Assert queued → preparing → ready,
      the 600-second aggregate deadline without reset, 30-minute expiry, scoped
      IDs, explicit disabled/failed preparation, crash recovery, and retry.
      Supersede a pending job on save; verify a previously ready labeled
      download remains one snapshot. Cancel/disconnect export A while B shares
      slides and assert B survives. UI tests assert named stages, available
      cancellation, no invented 50% progress, actionable failure, and no
      download before ready.
- [ ] **Step 2: Run RED.** Backend selection:
      `tests/unit/test_export_preparation.py` `tests/planning/test_api.py`.
      Frontend selection: `src/services/export-import.test.ts`
      `src/components/missions/ExportDialog.test.tsx`.
- [ ] **Step 3: Implement state transitions and UI.** Use persisted tokens and
      captured input identities, cheap status reads, and owned bounded assembly.
      Cancellation ends job-specific work without stopping shared rendering.
      Require full snapshot pairing, store expiry in responses, reap only owned
      expired files, and recover abandoned jobs after restart. Keep omitted-PDF
      warnings explicit. Remove the 600-second wait from HTTP download handling;
      document legacy 202.
- [ ] **Step 4: Run GREEN and negative controls.** Run both selections plus
      `test_customer_export_job.py` and `test_slide_coordinator.py`; verify
      complete mission/source/history round-trip and cleanup on shutdown. Check
      frontend types.
- [ ] **Step 5: Commit.** Commit as
      `feat: expose bounded mission export preparation`.

## Task 4: real-server responsiveness and stage measurements

**Files:** Create
`backend/starlink-location/tests/integration/test_customer_export_responsiveness.py`
and `tools/acceptance/itinerary-planning/export_probes.py`. Extend
`tools/tests/test_itinerary_planning_acceptance.py`.

**Interfaces:**
`probe_series(origin, mission_id, *, seconds, output) -> dict`
accepts string origin/mission ID, floating-point seconds and a `Path` output.
issues health/status/mission probes with a two-second request deadline and
writes every request result/elapsed time. Reports include
scenario/configuration, preparation stage times, headers/body completion,
package hashes, and failures. The integration fixture owns a real Uvicorn server
and all child process groups; the parent production runner owns the Docker/Nginx
scenario.

- [ ] **Step 1: Write failure controls.** Add
      `test_probe_retains_deadline_failures` and
      `test_export_preserves_header_and_body_timings`. A deliberately blocking
      event-loop fixture must produce retained two-second deadline failures. A
      failed body transfer must retain its header timing and partial-byte
      result. Cover cold queued work, warm download, invalidating save, worker
      failure, and termination.
- [ ] **Step 2: Run RED.** Backend selection:
      `tests/integration/test_customer_export_responsiveness.py`; root
      selection: `tools/tests/test_itinerary_planning_acceptance.py`.
- [ ] **Step 3: Implement the measured probes.** Use actual HTTP sockets and
      production endpoints, not in-process ASGI transport. Bound each scenario
      and close connections/server contexts on every outcome. Record load and
      distinct cold/warm state; never discard failed samples or replace the
      maximum with an average. Record lock
      wait/capture/normalization/queue/render/assembly stages.
- [ ] **Step 4: Run GREEN.** Prove the blocking negative control fails its bound
      while the repaired named normal scenarios meet it. Verify no owned server,
      listener, or worker remains. These regressions supplement private
      production controls in the parent integration task.
- [ ] **Step 5: Commit.** Commit as
      `test: probe API responsiveness during customer exports`.
