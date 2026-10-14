# GFS Wind Acceptance Tasks

Continuation of the [approved implementation plan](2026-10-14-gfs-wind-visualization.md).

## Task 5: Native Browser Proof, Performance Evidence, and Delivery

**Status:** Native implementation and labeled synthetic controls complete.
Pinned-source C1 and hardware H1 remain unverified; see the
[evidence report](../../reports/2026-10-14-gfs-wind-visualization.md).

**Interfaces:** Retain the existing `run.sh <exact-SHA> <browser> presentation`
entry point, source fixtures, project `starlink-290-gfs-presentation`, ports
15293/18293, and private volumes. Add evidence keys `wind_raster`,
`wind_particles`, `exclusive_modes`, and `reduced_motion` to presentation
requirements without removing existing keys. `gfs-wind-probe.ts` provides
`windSnapshot(page: Page)` and
`windReadbacks(page: Page, coordinates: GeoSample[])` using the actual admitted
scene/material/framebuffer. Define
`GeoSample = {latitude: number; longitude: number}`; `windSnapshot` returns a
promise containing presence, mode, grid instance, particle count, a bounded
position sample, draw calls, owned bytes and budget peaks. `windReadbacks`
returns a promise of samples with geographic location, physical U/V, knots,
validity mask, and four-channel RGBA readback. Probe types live in that
test-support module and are never imported by production.

- [x] Extend `test_gfs_acceptance_runner.py`: removing any new proof rejects
      presentation PASS; NaN, infinity, zero samples, absent cleanup, or
      over-budget metrics reject PASS. Add route roundtrip and paired UI/browser
      assertions to `gfs-weather-production.spec.ts`, replacing combined-layer
      enable and ready predicates with explicit wind then temperature modes.
- [x] Add native shader readbacks for signed U/V, physical speed and rendered
      color on independently captured NOAA oracle coordinates, plus labeled
      synthetic controls for opposite vectors/zero/masks. Check both diagnostic
      components and ordinary production color/alpha output. Tolerances:
      source/CPU quantization at most 0.01 m/s; packed GPU components at most
      0.02 m/s; knots error at most 0.06 kt; unblended color within 2/255 per
      channel. Select probe pixels away from particles, compare transparent
      masks against a raster-hidden control, and restore
      camera/material/visibility in `finally`.
- [x] Add visible trail/direction checks on the real drawing, far-side
      occlusion, repeated wind/temperature/off cycles, live reduced-motion
      changes, mode change during refresh, complete generation swap, stale and
      original-expiry removal, and hidden/offline recovery. Confirm wind legend
      and temperature exclusion in both browser contexts; check radar hatching,
      reports/picking, route markers, and gesture behavior. Keep all existing
      foundation/source/hash/FL/terrain and core-response controls.
- [x] Capture desktop 1920×1080, fullscreen at that viewport, and mobile 390×844
      screenshots for both modes and reduced-motion wind. Measure legend label
      rectangles for overlap, finite native geometry, draw calls, GPU/decoded
      peaks, and empty particle resources in temperature/off states. Browser
      exceptions or source-provider requests from the page fail acceptance.
- [x] Run runner contract tests from the root:

  ```sh
  timeout --kill-after=10s 5m python3 -m pytest tools/tests/test_gfs_acceptance_runner.py tools/tests/test_gfs_compose.py -q
  ```

  Expect new evidence requirements to FAIL before extending runner/probes;
  implement them and rerun to PASS. Update the runner README and operator/API
  docs with exclusive toggles, knots scale, illustrative motion, and migration.
  Record measured results only after their runs, distinguishing pending gates.

- [x] Add a dedicated hardware Playwright config with existing provisioned
      Chrome, one worker, no retries or SwiftShader flags, external same-origin
      Nginx URL, headed mode, and no managed/shared service startup. Inputs are
      `GFS_HARDWARE_BROWSER`, `GFS_HARDWARE_BASELINE_URL`,
      `GFS_HARDWARE_CANDIDATE_URL`, `GFS_HARDWARE_BASELINE_SHA`,
      `GFS_HARDWARE_CANDIDATE_SHA`, and `GFS_HARDWARE_OUTPUT_DIR`; validate
      exact SHAs, installed executable, and permitted HTTP(S) origins before
      opening contexts. Baseline and candidate each serve their own isolated
      production Nginx/backend/worker and identical pinned replay source. An
      absent target or fixture is an unmet preflight, never a substitute
      live-data benchmark. `gfs-wind-performance.spec.ts` selects the real
      controls and measures full-cap update duration via a scoped wrapper around
      the existing drawing update; restore the wrapper in `finally`. Keep
      instrumentation in acceptance support, not new production test APIs.
- [ ] Measure the two targets below. The approved spec requires naming the
      hardware environment before execution; until the user supplies its
      details, H1 is an outstanding preflight input, not a claimed passing
      benchmark.

  | Target         | Environment and fixture                                                                                                                                                          | Result required                                                                                  |
  | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
  | C1 correctness | This managed cloud environment's provisioned Chrome with SwiftShader, real-source historical replay, production Nginx, the viewports above                                       | All presentation evidence, resource bounds, cleanup; explicitly label software rendering         |
  | H1 hardware    | User-designated Overview workstation and installed Chrome, hardware acceleration enabled; record machine/OS/CPU/GPU/browser/DPR/refresh rate and WebGL renderer before execution | At 2,000 particles, p95 update ≤4 ms and p95 total frame duration ≤1.2× the paired barb baseline |

  For H1 use 1920×1080, fixed DPR 1, camera `(6,0,0)` looking at origin,
  controls idle, 500 hPa F006 pinned source. Measure once with GFS only and once
  with the same radar/bulletin overlay fixtures enabled. Warm up 15 s; capture
  60 s for each of three paired baseline/candidate runs, alternating order.
  Every run must satisfy the gates; use nearest-rank p95, report frame count,
  draw calls, allocation peaks, and core health/status latency. Use real time
  for animation; historical source replay does not alter frame timing. If
  hardware identity/fixtures are absent, renderer is software, or data is
  incomplete, record hardware gate **unverified** and do not claim deployment
  performance acceptance. Baseline is the implementation feature branch's exact
  pre-change dev SHA; archive it and build separately, never copy the old barb
  implementation into production as a selectable mode.

- [ ] Commit the acceptance changes as
      `test: verify exclusive GFS wind rendering and particle lifecycle`. Use a
      clean committed candidate for final controls from the repository root:

  ```sh
  ACCEPTANCE_POLICY_BASE_SHA="$GFS_WIND_BASE_SHA" timeout --kill-after=10s 20m python3 tools/verify static
  timeout --kill-after=10s 20m python3 tools/verify backend
  timeout --kill-after=10s 15m python3 tools/verify frontend
  GFS_ACCEPTANCE_SOURCE_DIR=/path/to/pinned/source-root timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh "$(git rev-parse HEAD)" /path/to/provisioned/chrome presentation
  ```

  These are commands to run during implementation, not verification performed
  while writing this plan. Discover actual installed/source paths through the
  established environment workflow; do not fabricate or install a browser. Use
  the actor's Docker daemon and fresh no-cache candidate images. Preserve
  exact-SHA artifacts and clean all task-owned processes, listeners, containers,
  networks, and disposable volumes after each attempt.

- [ ] Run H1 only after recording its target, pinned fixture delivery and paired
      baseline/candidate URLs. From `F`, with the six hardware inputs above set,
      run:

  ```sh
  timeout --kill-after=10s 30m npx playwright test \
    --config playwright.gfs-hardware.config.ts \
    gfs-wind-performance.spec.ts
  ```

  Record those inputs and target identity in the report; if H1 remains
  unavailable, report the outstanding gate plainly. Any source/tooling or
  report commit after acceptance changes candidate SHA: rerun applicable
  exact-head controls rather than attach stale evidence.
- [ ] Request a whole-branch review, fix verified findings, push the feature
      branch, and open a PR against `dev` linking the approved spec/plan and
      evidence. Leave merge and deployment out of this task. Do not call
      software-only proof hardware approval. Keep the worktree for the open PR,
      with runtime resources stopped and cleanup evidence attached.
