# Aviation weather local rendering proof implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Track steps with checkboxes.

**Goal:** Measure native-globe proofs for real GFS, SIGMET and GOES IR.

**Architecture:** Research normalizers publish immutable local assets served
through production Nginx. A test-only native Overview renderer compares GPU
readback with an independent CPU oracle and reports measured proof outcomes.

**Tech Stack:** Python 3.11, ecCodes, netCDF4, pyproj, NumPy, pytest, Bash,
existing Three/esbuild/Playwright, actor Docker and provisioned browser.

**Spec:** [Architecture](../specs/2026-10-06-aviation-weather-design.md) and
[proof design](../specs/2026-10-06-aviation-weather-proof-design.md). The owner
[review](https://github.com/bcl1713/starlink-dashboard/pull/291#pullrequestreview-5427727454)
accepts the architecture at `a64b952b7176f54a078166c7fe44aabf3233b9b9`.

## Global constraints

- No production weather API/settings/dependency changes or continuous ingest.
- Keep source scientific formats/projections out of FastAPI handlers/browser.
- Schema `aviation-weather-v1`; representations `latlon-grid-v1`/`advisory-v1`.
- Maximum grid 720 × 361, longitude -180 plus 0.5-degree steps, latitude +90
  minus 0.5-degree steps; no duplicate longitude seam column.
- Little-endian Int16 components with declared scale/offset; Uint8 mask: 0
  valid, 1 outside coverage, 2 missing, 3 quality rejected. Unknown is not zero.
- One decoder, one CPU, 1 GiB memory, 120-second decode plus 10-second grace.
- Two HTTP exchanges, 20 attempts/minute, 30-second absolute HTTP deadline; 32
  MiB compressed/object, 256 MiB expanded/object, 5 GiB/day scientific input.
- Dedicated 4 GiB disk quota: 1 GiB staging, 2.5 GiB published, 0.5 GiB reserve.
- Four browser fetch/decode operations, 45-second generation deadline, 16 MiB
  encoded/generation, additional decoded/geometry 32 MiB and GPU 16 MiB.
- Preserve radar's 96 MiB decoded/48 MiB GPU; weather totals 128/64 MiB.
- At most 500 advisories, 100,000 polygon/contour vertices and 2,000 wind barbs.
- Preserve radar opacity 0.40, hatching 0.17 and existing lifecycle controls.
- `timeout --kill-after=10s 20m` around each proof run; separately bounded
  builds.
- Record command/session/PID/process group, private project/volumes, paths/ports
  before allocation. Exit/INT/TERM cleanup reaps children and verifies absence.
- Preserve Docker endpoint/context, proxies, CA trust, credentials and shared
  resources. Consume a provisioned browser; never install a browser in the run.
- Retain full satellite scan intervals and per-region times. Empty/truncated
  advisory collections cannot produce a worldwide no-hazards presentation.
- Immutable source hashes, exact clean candidate SHA, measured allocations and
  diagnostic status accompany evidence. These are diagnostic proofs.

## Review focus

1. Ignored Range, changing source bytes or partial download cannot publish an
   artifact; immutable replay fails on changed bytes (Task 1).
2. Source/CPU/GPU agree on zero/missing, seam/pole/orientation and units (Tasks
   2/5).
3. Empty, truncated, unresolved or cancelled SIGMETs cannot imply worldwide
   safety; unknown vertical reference remains unknown (Tasks 3/5).
4. GOES quality/limb masks and unequal scan times remain explicit through the
   descriptor and passive presentation (Tasks 4/5).
5. Decode timeout, browser failure and signals release all recorded owned
   resources; missing metrics or cleanup evidence prevent PASS (Tasks 1/5).

## Files and interfaces

Create package `tools/acceptance/aviation_weather_proof/` with `__init__.py`,
`model.py`, `exchange.py`, `capture.py`, `gfs.py`, `advisory.py`,
`satellite.py`, `grid.py`, `run_browser.py`, `journey.mjs`, `report.py`,
`run.sh`, `Dockerfile`, `requirements.txt`, `README.md`. Normalizers own source
parsers; `grid.py` owns quantization, masks and atomic publication.

Create tests under `tools/tests/` with prefix `test_aviation_weather_proof_` and
suffixes `capture.py`, `gfs.py`, `advisory.py`, `satellite.py`, `runner.py` and
`report.py`. Create frontend files under
`frontend/mission-planner/tests/e2e/support/aviation-weather-proof/`:
`model.ts`, `sampling.ts`, `grid-renderer.ts`, `advisory-renderer.ts`,
`browser.ts`; unit tests live at
`frontend/mission-planner/src/test/aviation-weather-proof.test.ts`.

Modify only the test backend fixture
`tools/acceptance/overview-weather/backend_fixture.py` to mount read-only
`/capture` at `/api/overview-weather/aviation-proof-assets` exclusively in
`WEATHER_ACCEPTANCE_MODE=aviation-proof`. Reuse the existing weather Compose
topology and camera observer; do not broaden the production routes.

`model.py` defines frozen records with these constructor fields:

```python
CapturedObject(url: str, byte_range: tuple[int, int] | None,
               relative_path: str, sha256: str, byte_size: int)
CaptureManifest(source: str, captured_at_ms: int,
                objects: tuple[CapturedObject, ...], attribution: tuple[str, ...])
```

`ProductArtifact` contains `descriptor_path: Path`,
`payload_paths: tuple[Path,...]`, `capture_manifest_path: Path`; confine paths.

Run Python tests from the worktree root with the task environment:
`PYTHONPATH=tools timeout --kill-after=10s 5m python -m pytest <test-file> -q`.

Frontend focused tests, from `frontend/mission-planner`:

```bash
timeout --kill-after=10s 5m npm run test:unit -- src/test/aviation-weather-proof.test.ts
```

## Task 1 Bounded real-source capture and immutable replay

**Files:** Package model/exchange/capture, requirements/Dockerfile, capture
tests. **Consumes:** Public endpoints/object identities in the source inventory.
**Produces:**

```python
capture(source: str, destination: Path, *, cycle: str | None = None,
        object_key: str | None = None) -> CaptureManifest
load_capture(manifest_path: Path) -> CaptureManifest
```

Invalid input raises `ValueError`. Sources are `gfs`, `isigmet`, `goes19-c13`.

- [ ] Write failing tests `test_range_ignored_cannot_publish`,
      `test_content_range_mismatch`, `test_changed_bytes_reject_replay`,
      `test_partial_download_removed` and `test_exchange_deadline_reaps_worker`.
      Assert exact 206/range lengths, unchanged hashes, zero published partials,
      32 MiB/object, 20 attempts/60s, two exchanges and no surviving owned
      child.
- [ ] Run the capture test file; expect FAIL from the missing contracts/tool.
- [ ] Implement bounded streaming exchanges with allowlisted HTTPS hosts,
      explicit ranges, custom User-Agent and absolute deadlines; preserve
      proxy/CA. Existing `weather_detail_comparison.exchange` accepts only 200
      and is not a GFS-range transport. Record ownership before starting the
      exchange worker; terminate/reap it on timeout, signal, disconnect or
      parent death.
- [ ] Pin research-only dependencies after verifying upstream Python 3.11
      support and licences; record resolved versions in evidence. Build with
      `timeout --kill-after=10s 15m`, secret CA mount and no credential image
      layers.
- [ ] Capture the three real GFS 500 hPa U/V/T messages from the verified 00Z
      F006 index; derive range ends from subsequent offsets in that exact index.
      Capture full international SIGMET GeoJSON and the recorded GOES C13
      object. Changed/departed keys fail replay; live replacement requires a new
      manifest.
- [ ] Run capture tests to PASS, then commit
      `test: add bounded aviation weather proof captures`.

## Task 2 GFS grid with independent geographic oracle

**Files:** `gfs.py`, `grid.py`, GFS tests. **Consumes:** Task 1 manifest with
three hashed GRIB2 messages. **Produces:**
`normalize_gfs(capture: CaptureManifest, destination: Path) -> ProductArtifact`;
`grid.py` exposes:

```python
write_grid(descriptor: dict, components: dict[str, numpy.ndarray],
           mask: numpy.ndarray, destination: Path) -> ProductArtifact
```

Descriptor names fields, units, geometry, scale/offset, validity, source hashes
and mask; never infer scientific metadata from filenames.

- [ ] Write tests `test_scan_orientation_and_seam`,
      `test_valid_zero_vs_missing`, `test_model_time_identity`,
      `test_pressure_is_not_flight_level`, `test_quantization_bounds`. Synthetic
      2×2 landmarks must preserve N/S/E/W; zero U/V remains mask 0, fill remains
      mask 2; valid_at equals run plus lead; selected vertical is pressure 500
      hPa; overflowing Int16 fails publication.
- [ ] Run GFS tests; expect FAIL from missing normalization.
- [ ] Decode ecCodes messages offline within the worker cap. Verify UGRD/VGRD
      m/s and TMP K, common run/lead/grid/pressure; rotate non-earth-relative
      vectors before publication. Regrid to declared 720×361 nodes; bilinear
      output requires all contributors valid. Use temperature offset
      273.15/scale 0.01 K and wind offset 0/scale 0.01 m/s, rejecting overflow.
      Publish only complete artifacts.
- [ ] Select ten independent source-grid coordinates including dateline and
      near-pole samples; retain original decoded values, normalized values,
      coordinates and resampling error. The CPU oracle reads source metadata and
      arrays independently of the browser UV implementation.
- [ ] Run tests to PASS; measure one-CPU/1-GiB offline normalization with
      `timeout --kill-after=10s 120s`, recording CPU/wall/peak RSS/input/output
      bytes. Commit `test: normalize real GFS fields for native globe proof`.

## Task 3 Advisory geometry and completeness semantics

**Files:** `advisory.py`, advisory tests. **Consumes:** Task 1 immutable
international SIGMET snapshot. **Produces:**
`normalize_advisories(capture: CaptureManifest, destination: Path) -> ProductArtifact`;
advisory-v1 GeoJSON with per-feature issuer, revision/cancellation, hazard, raw
text, half-open validity and vertical tags.

- [ ] Write tests `test_empty_is_not_worldwide_clear`,
      `test_truncated_feed_is_incomplete`,
      `test_unknown_vertical_is_not_all_levels`,
      `test_cancelled_or_expired_is_not_active`, `test_dateline_hole_geometry`.
      Empty/truncated snapshots declare unverified/incomplete scope, never a
      global no-hazards flag; unknown altitude stays unknown; cancelled/expired
      features are absent from the active render; split geometry preserves holes
      and area.
- [ ] Run advisory tests; expect FAIL from missing normalizer.
- [ ] Verify provider schema/raw bulletin units and base/top references against
      current AWC documentation. Normalize one real located valid advisory and
      keep the full input for completeness investigation. Split dateline
      crossings, preserve holes/lineage; invalid geometry becomes
      textual/unlocated. Explicit incomplete/unknown coverage is acceptable; do
      not invent feed completeness.
- [ ] Record count/cap/truncation and unresolved completeness in source
      evidence; bounded response success cannot establish feed completeness.
- [ ] Run tests to PASS; commit
      `test: normalize international advisories without false clear states`.

## Task 4 Satellite navigation quality and scan identity

**Files:** `satellite.py`, satellite tests; reuse Task 2 grid writer.
**Consumes:** Task 1 hashed GOES-19 C13 CMIP NetCDF object. **Produces:**
`normalize_satellite(capture: CaptureManifest, destination: Path) -> ProductArtifact`,
IR brightness temperature in K with scan interval, sensor identity, quality mask
and `valid_at_ms=scan_end_ms` display selection.

- [ ] Write tests `test_scale_and_quality_flags`,
      `test_off_earth_and_limb_mask`, `test_scan_interval_survives_identity`,
      `test_region_intervals_not_collapsed`. Known source fill/quality values
      map to masks 2/3; unsupported navigation maps to mask 1; scale/offset
      produce known K values; changing scan start changes instance identity;
      unequal region intervals remain two distinct records.
- [ ] Run satellite tests; expect FAIL from missing normalizer.
- [ ] Read CMI scale/fill/units, DQF and geostationary projection attributes in
      netCDF4/pyproj; process bounded windows. Initially accept DQF=0 only and
      reject view zenith angles over 75 degrees; record this conservative policy
      in normalization identity. Reproject without filling invalid contributors.
      Quantize temperature with the Task 2 offset/scale and preserve scan
      start/end.
- [ ] Retain ten independent input navigation/value samples with normalized
      comparisons and declared resampling errors; label brightness temperature,
      not inferred cloud height or precipitation. Measure under Task 2 worker
      caps.
- [ ] Run tests to PASS; commit
      `test: normalize GOES IR with explicit scan and missing coverage`.

## Task 5 Native rendering diagnostic runner and evidence report

**Files:** Frontend proof support/unit test files; fixture mount; runner,
browser wrapper/journey, report/README and runner/report tests from file map.
**Consumes:** Three ProductArtifacts and independent numeric oracles.
**Produces:** `installProof(page: Page, descriptorURL: string): Promise<void>`,
`restoreProof(page: Page): Promise<void>`, `sampleProof` has the signature:

```typescript
sampleProof(page: Page, latitude: number, longitude: number):
  Promise<{value: number | null; mask: number}>
```

`evaluate_proofs(evidence: Path) -> dict` returns per-gate diagnostic outcomes.

- [ ] Write frontend tests `test_grid_length_and_hash_rejection`,
      `test_cpu_seam_pole_and_masks`, `test_scan_interval_label`,
      `test_mosaic_lists_each_scan`, `test_empty_advisory_label`,
      `test_allocation_and_failed_install_cleanup`. Assert exact payload
      lengths, signed decoding, all-four-valid interpolation, UTC scan interval
      labels and per-region intervals; empty/incomplete feed labels never say no
      hazards. Reject allocations above 32 MiB decoded/16 MiB GPU, including
      replacement.
- [ ] Write Python runner/report tests for fixture-only mount, source URL/hash
      mismatch, missing GPU metrics, missing real-source capture, failed mask
      readback, absent cleanup and killed descendants. Each prevents a passed
      gate. Run those files and the named frontend test with bounded commands;
      expect RED.
- [ ] Bundle test-only browser modules using existing esbuild as in
      `metric-panel-fixture.ts`. Obtain the actual Overview scene/camera with
      `observeOverviewCamera`; add owned overlay meshes and dispose/restore
      them. Decode packed Int16 values in the shader using nearest-filtered
      RGBA8 high/low bytes plus manual interpolation and conservative masks. Add
      native wind barbs, triangulated advisory polygons/holes and passive proof
      labels.
- [ ] Add geographic GPU quantity/mask readback using the same sampling shader,
      independently projected visible camera samples and actual tessellated mesh
      intersections. Compare ten real-source values within one quantization
      step; include separate seam/pole/invalid fixtures. Check final
      palette/opacity pixels against known backgrounds within 3/255 RGB after
      documented color conversion, avoiding antialiased edge pixels. Assert
      satellite interval/mosaic labels and incomplete SIGMET presentation in the
      rendered page.
- [ ] Implement `run.sh <clean-40-hex-SHA> <capture-root> <profile-path>` with
      project `starlink-290-aviation-proof`, loopback ports 15290/18290 and
      private volumes. Reuse production Dockerfiles/Nginx and weather Compose
      topology. Launch through `start_final_browser_session` as the existing
      diagnostic `overview_history/run_browser.py` does, connect journey
      Playwright over its CDP session, close contexts/session in finally and
      retain browser diagnostics. No `npm`/`npx`/browser install in the run;
      unprovisioned profile records blocked.
- [ ] Record candidate/images/versions, input/output hashes and times, CPU/RSS,
      encoded/decoded/GPU peaks, camera/renderer/viewport, requests,
      source/CPU/GPU samples, labels and desktop/fullscreen/mobile captures.
      Reject any browser provider request. Preserve complete success/failure
      evidence and verify owned process groups, ports and labeled Docker
      resources absent before PASS.
- [ ] Run focused tests to PASS, syntax/type checks and current radar contract
      tests; commit `test: render and measure aviation weather local proofs`.
      Execute exact-SHA diagnostic runs, seal/checksum evidence with platform
      evidence helpers, then commit a concise measured report under
      `docs/reports/`. Conditional access, FL interpolation and global satellite
      seams remain unproven; dispatch no product implementation issues yet.
