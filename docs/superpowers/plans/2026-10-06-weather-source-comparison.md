# Weather source comparison implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task by task. Track steps with checkboxes.

**Goal:** Measure whether free provider tiles or bounded raw-radar generation
best support issue 288 before committing to production source contracts.

**Architecture:** Capture immutable RainViewer, MRMS and OPERA samples, generate
regional tiles offline, and compare them on the existing native Overview globe.
Keep research dependencies and rendering probes outside product code. The
resulting evidence supplies the source decision and the next implementation plan
for camera refinement and opacity.

**Tech Stack:** Python 3.11, Rasterio/GDAL, h5py, NumPy, Pillow, pytest,
existing TypeScript/Playwright probes, production Dockerfiles and Nginx.

**Spec:** [Approved weather design][spec]; [provider assessment][assessment].

## Global constraints

- Preserve international observed coverage; avoid ongoing API fees.
- Use one or two immutable regional snapshots per raw source. No continuous
  ingestion, forecasting, satellite filling or full LibreWXR deployment.
- Preserve production limits: 90 attempts/minute, four exchanges, 32 pending
  acquisitions, 48 cached PNGs/64 MiB, and 48 MiB GPU storage.
- Browser decoded imagery remains bounded to 96 MiB; PNGs remain at most 2 MiB.
- Compare 1080p desktop/fullscreen and mobile using the actual Overview camera.
- Compare radar opacity 0.35, 0.40 and 0.45 against 0.72; keep hatch alpha 0.17.
- Research-only limits: one generation worker, one CPU, 2 GiB container memory,
  1 GiB retained sample/derived data, and 256 MiB per downloaded/decompressed
  object. These are experiment ceilings, not approved production ingest limits.
- Rate-limit capture to 30 HTTP attempts per rolling minute, two active
  requests, two attempts per object, and 45 seconds per request. Honor bounded
  Retry-After; stop capture rather than exceed the allowance.
- Record ownership before starting resources. Use task-specific projects,
  private volumes, loopback ports, timeout/kill grace and exit/signal cleanup.
- Preserve the actor Docker configuration. Never remove shared resources.
- Preserve exact candidate SHA, image IDs, dependency versions and evidence.

## Review focus

1. Clear skies or unavailable raw products must produce an inconclusive result,
   rather than a claim of better detail (Tasks 1 and 4).
2. Missing/undetect values and mask polarity must distinguish covered zero rain
   from absent observations, including reprojection edges (Task 2).
3. Different observation times, corrupt files or changed source bytes must
   prevent a supposedly matched comparison (Tasks 1 and 3).
4. Timeout, browser failure or interrupted generation must release every owned
   resource and preserve failure evidence (Task 3).
5. Different renderer, camera, cache state or absent memory measurements must
   invalidate a resource comparison instead of manufacturing a winner (Task 4).

---

## File map and phase boundary

Create `tools/acceptance/weather_detail_comparison/` with:

- `model.py`: immutable sample/tile/evidence contracts and validation.
- `capture.py`: bounded provider discovery, download, hashing and metadata.
- `generate.py`: raw adapters, projection, precipitation and coverage tiles.
- `report.py`: evidence completeness and comparison summaries.
- `Dockerfile`, `requirements.txt`: isolated research dependencies; record the
  installed dependency lock in evidence without changing backend requirements.
- `run.sh`, `README.md`: bounded capture/generation/replay commands and cleanup.

Create `tools/tests/test_weather_detail_comparison_{capture,generate,report}.py`
and `tools/tests/test_weather_detail_comparison_runner.py` for behavioral tests.
Create `frontend/mission-planner/tests/e2e/overview-weather-comparison.spec.ts`
and `tests/e2e/support/overview-weather-comparison.ts` beneath that frontend.
Reuse `support/overview-weather-probe.ts` for the existing renderer boundary.
Extend the existing weather acceptance runner, Compose file and backend fixture
to supply an isolated comparison mode and saved sample assets. Extend
`tools/tests/test_overview_weather_acceptance.py` for that runner contract.

Keep captures, generated images, logs, dependency locks and reports under
ignored `.superpowers/sdd/issue-288-weather-detail/evidence/<candidate-sha>/`.
Commit a concise result to the existing provider assessment.

This plan ends with measured source selection. Production camera selection,
admission, lifecycle, shader transitions and final acceptance remain required by
the approved spec. Write their implementation plan after this phase establishes
the source format; this phase does not complete issue 288 or authorize a new
continuous ingest deployment.

Run pytest steps from the worktree root using this bounded helper:

```bash
comparison_pytest() {
  PYTHONPATH=tools timeout --kill-after=10s 5m python3 -m pytest "$@" -q
}
```

## Task 1: Reproducible, bounded captures

**Files:** Create `model.py`, `capture.py`, research dependency files and
capture tests from the file map.

**Interfaces:** Produce frozen `Snapshot` records containing source, product,
observed UTC, captured UTC, units, CRS, source URL, license/attribution, local
path and SHA-256. Produce `TileKey(z: int, x: int, y: int)` and
`CaptureSet(snapshots: tuple[Snapshot, ...], tiles: dict[TileKey, TilePair])`;
`TilePair` identifies radar/absence PNG paths, hashes and snapshot identity.
Expose `capture(destination: Path, max_snapshots: int = 2) -> CaptureSet` and
`load_capture(path: Path) -> CaptureSet`. Fail validation with `ValueError`.

- [ ] Write capture tests for immutable identity/hash verification, timestamp
      mismatch, absent precipitation, bounded compressed/decompressed downloads,
      failed/partial cleanup, retry counting and malformed metadata. Assert
      limits of 2 snapshots/source, 256 MiB/object, 1 GiB aggregate, 30
      attempts/60 seconds, 2 active requests and 45-second request deadlines.
      Pin these named cases:

  ```python
  def test_changed_capture_bytes_are_rejected(capture_path):
      # Alter a saved PNG after its hash was recorded.
      with pytest.raises(ValueError, match="hash"):
          load_capture(capture_path)

  def test_capture_caps_each_source(capture_set):
      for source in ("rainviewer", "mrms", "opera"):
          assert sum(s.source == source for s in capture_set.snapshots) <= 2
  ```

- [ ] Run
      `comparison_pytest tools/tests/test_weather_detail_comparison_capture.py`
      Confirm failures originate from the missing capture implementation.
- [ ] Implement the contracts and bounded streaming download. Preserve proxy and
      CA configuration, validate HTTPS source hosts and reject redirects to
      unapproved hosts. Write partial files atomically, hash completed bytes and
      record every network attempt. Never commit credentials or captured
      binaries.
- [ ] Discover MRMS PrecipRate GRIB2 via the documented NOAA data listing and
      OPERA instantaneous RATE composites via the documented ORD anonymous
      API/S3 cache. Preserve actual units, times, missing flags and license
      metadata; reject accumulated rainfall, model data and unrecognized
      products.
- [ ] Capture RainViewer admitted observed paths at zoom 2 and regional zooms 5,
      6 and 7 for the same frame, with matching coverage tiles. Select up to
      eight tiles per regional view. Choose precipitation-bearing U.S. and
      European windows from the captured data; record raw/provider time
      differences and refuse feature-by-feature comparison beyond five minutes
      of separation.
- [ ] Repeat the capture test command and require PASS. Build the research image
      with a 15-minute wall-clock limit, record resolved package versions and
      verify required GDAL drivers. Treat unavailable feeds/drivers as explicit
      evidence, never silently substitute different products.
- [ ] Commit the independently testable capture tool and tests with
      `test: add bounded weather source capture tooling`.

## Task 2: Truthful regional tiles from raw snapshots

**Files:** Create `generate.py` and generation tests from the file map.

**Interfaces:** Consume Task 1 contracts. Produce

```python
generate(snapshot: Snapshot, keys: tuple[TileKey, ...], destination: Path) -> dict[TileKey, TilePair]
```

with 512-square PNGs; absence alpha is 255 for missing/unknown coverage and 0
for valid observations, including zero rain.

- [ ] Write synthetic GRIB-equivalent and ODIM fixtures with independent
      geographic landmarks, positive rain, valid zero, nodata and undetect
      values. Assert distinct zero/absence output, correct north/south and
      east/west orientation, neighboring tile edges, antimeridian wrapping and
      clipping beyond Web Mercator latitude 85.05112878 degrees.
      `test_zero_rain_is_covered` asserts absence alpha is 0 and radar alpha is
      0; `test_nodata_is_absent` asserts absence alpha is 255;
      `test_undetect_is_covered_zero` asserts absence alpha is 0;
      `test_reprojection_never_fills_missing_coverage` asserts all independently
      specified unsupported landmarks retain absence alpha 255.
- [ ] Run
      `comparison_pytest tools/tests/test_weather_detail_comparison_generate.py`
      Confirm the missing generator causes FAIL.
- [ ] Implement MRMS GRIB2 reading using Rasterio and OPERA ODIM reading using
      h5py with declared gain/offset/nodata/undetect and projection metadata.
      Normalize rate to mm/hour. Use tiled/windowed reads and bounded caches;
      derive absent observations before reprojecting. Use nearest-neighbor
      sampling for validity and conservatively mark unsupported footprints
      absent.
- [ ] Generate requested Web Mercator tiles only, with a documented fixed blue
      rain-rate scale shared by both raw sources. Record scale thresholds; do
      not imply RainViewer's proprietary coloring gives equivalent intensities.
      Do not build a world pyramid or interpolate new observational information.
- [ ] Run the same tests to PASS; generate saved samples in the bounded research
      container. Record input/output bytes, wall time, CPU time and peak RSS for
      cold decoding and warm tile generation separately. Check the research
      limits.
- [ ] Commit generator and tests with
      `test: add mask-preserving raw radar tile generation`.

## Task 3: Native globe comparison with reliable cleanup

**Files:** Create browser comparison spec/support and research `run.sh`/README.
Modify
`tools/acceptance/overview-weather/{run.sh,compose.yml,backend_fixture.py}`,
`frontend/mission-planner/playwright.weather-acceptance.config.ts` and runner
tests.

**Interfaces:** Consume hashed captures/TilePairs. Browser support exposes
`installComparison(page: Page, capture: ComparisonCapture): Promise<void>` and
`restoreComparison(page: Page): Promise<void>`; `ComparisonCapture` carries
snapshot identity, geographic tile bounds, pair URLs and hashes. Runner accepts
`run.sh --check` or `run.sh <40-hex-clean-HEAD>` and writes `comparison.json`,
screenshots, request logs and `cleanup.json`.

- [ ] Write runner tests asserting rejection of dirty/non-exact candidates,
      refusing occupied resources, ownership recording before start, safe signal
      cleanup and cleanup failure propagation. Exercise termination of a real
      task-owned dummy process and release of its listener, without Docker.
      `test_timeout_reaps_owned_process_and_listener` asserts the child PID is
      gone and its loopback port can be rebound;
      `test_cleanup_failure_is_nonzero` asserts an exit code other than 0 and
      retained cleanup failure evidence.
- [ ] Run
      `comparison_pytest tools/tests/test_weather_detail_comparison_runner.py`
      and `comparison_pytest tools/tests/test_overview_weather_acceptance.py`;
      confirm new cases FAIL.
- [ ] Parameterize the existing runner's project, image names, ports and browser
      spec while preserving its default acceptance behavior. Comparison uses
      `starlink-288-weather-comparison` and loopback ports 15288/18288. Mount
      saved assets read-only; expose them only through the test backend launcher
      and Nginx. Do not add product endpoints or bypass product provider
      validation.
- [ ] Implement test-only native material comparison through the existing
      reconciler probe: preserve geometry, camera, depth settings and geographic
      projection; add at most eight matched detail slots in two 2048-by-1024
      textures. Keep the 32 MiB base plus 16 MiB detail ceiling and 96 MiB
      decoded ceiling. Restore original shader/uniforms and dispose temporary
      resources in `finally`. Label this as offline source replay, not
      production refinement.
- [ ] Add browser assertions for independently positioned synthetic landmarks,
      missing versus clear pixels, matched pair identity, texture allocation
      peak, restoration and resource release. Then capture actual-data
      comparisons at identical native camera matrices, viewport, renderer and
      geographic windows: baseline zoom 2, captured detail, and generated raw
      detail; include day/night, fullscreen and 390-by-844 mobile with
      operational overlays visible. `comparison refuses mixed frames` expects
      installation to reject different radar/coverage identities;
      `comparison releases textures after failure` asserts the texture count
      returns to its pre-install baseline.
- [ ] Record opacity comparisons at 0.72, 0.35, 0.40 and 0.45 without changing
      hatching. Record actual source resolution, browser PNG requests/bytes,
      decode/upload latency and frame timing. Distinguish source capture
      traffic, replay traffic and projected production demand.
- [ ] Repeat runner tests to PASS and commit the harness. Run the committed HEAD
      under `timeout --kill-after=15s 30m .../run.sh <sha>`. Record
      command/session, PID/process group, project, private volumes and paths
      before startup. Close browsers, reap owned processes and verify
      containers, networks, volumes and both listeners are gone, including on
      timeout; retain cleanup evidence.

## Task 4: Evidence-based source recommendation

**Files:** Create `report.py`, report tests and update [provider
assessment][assessment].

**Interfaces:** Consume capture, generation and browser evidence. Produce
`summarize(evidence: dict) -> dict` with status `complete` or `inconclusive`,
per-source measured costs, comparison validity, limitations and recommendation.

- [ ] Write tests proving missing precipitation, missing measurements, different
      camera/renderer/cache state, mismatched timestamps, failed hash checks and
      failed cleanup produce `inconclusive`. A complete synthetic evidence
      bundle reports measurements but cannot claim real provider quality.
      `test_missing_peak_rss_is_inconclusive`,
      `test_different_renderer_is_inconclusive` and
      `test_failed_cleanup_is_inconclusive` each assert
      `summarize(evidence)["status"] == "inconclusive"`.
      `test_clear_capture_cannot_prove_detail` asserts the same status when all
      compared observation windows have valid zero precipitation.
- [ ] Run
      `comparison_pytest tools/tests/test_weather_detail_comparison_report.py`
      Confirm the absent summary implementation causes FAIL.
- [ ] Implement the summary without inventing measurements. Separate source
      spatial resolution, actual added features, visual readability, bandwidth,
      cold/warm compute and memory. Explain time/color differences and uncertain
      coverage rather than treating them as image-quality improvements.
- [ ] Run report tests to PASS; summarize actual evidence and update the
      assessment with dated captures, exact SHA, costs and links to retained
      files. Recommend RainViewer unless raw generation demonstrates meaningful
      benefit and a specified international fallback. Any raw recommendation
      must state proposed production CPU/RAM/disk limits and the remaining
      coverage/ownership design requiring agreement before adoption.
- [ ] Run all four research test files plus affected acceptance tests with a
      10-minute wall-clock limit. Run applicable Python/frontend lint, type
      checks, Markdown checks and `git diff --check`; commit the measured
      assessment.
- [ ] Present source/opacity recommendation and write the production plan from
      the approved spec and observed contract. Preserve this open-PR worktree
      and evidence; continue issue 288 through implementation, fresh final-SHA
      production acceptance, branch push and a PR against `dev`.

[spec]: ../specs/2026-10-06-overview-weather-detail-design.md
[assessment]: ../../reports/2026-10-06-overview-weather-provider-assessment.md
