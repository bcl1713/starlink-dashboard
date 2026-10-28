# Overview bloom tuning (#429)

## Tune the actual Overview

Open the normal application at `/overview?bloomDebug=1`. The temporary panel
renders on the real Overview, using the current mission, map layers, camera,
city texture and animations. No separate package or app is needed.

The live defaults now use the owner-selected October 28 values: strength 0.35,
threshold 0.8, radius 1, bloom bound 3840, exposure 1; cities 17 at `#ffbe6f`,
route/link cores 3.9, particles 0.2, POI cores 40 and aircraft 2.8.

Use **Ambient lighting** to reduce terrain fill independently of emission and
exposure. The slider and numeric input range from 0 to 1 in steps of 0.01; 0.5
is the previous ambient level. Copied/downloaded JSON includes
`lighting.ambientIntensity`. Current appearance and ordinary Overview retain
their original 0.5 ambient level; Reset tuning restores 0.5 and the selected
bloom/emission defaults.

Adjust **Bloom strength**, **Bloom threshold**, **Bloom radius**, **Exposure**
and the bloom resolution bound. Emission controls apply immediately to warm city
lights, route/link cores, particles, POI/ground-entry/satellite marker cores and
both our aircraft and ADS-B aircraft. City color starts at warm amber `#ffbe6f`.
**Find city glow** provides a stronger starting point while keeping the actual
scene visible. Inspect **Bright pass** or **Bloom only**, then return to **Final
scene** to judge the whole map. These debug views process WebGL content; DOM map
labels remain visible.

Choose **Current appearance** to compare the original rendering or **Output pass
only** to isolate the postprocessing output. Changing controls preserves the
camera and animation pools. Normal `/overview` omits the panel and composer.
Values are temporary to this page session and do not write saved settings.

Click **Copy settings** and paste the JSON into chat, or use **Download
settings.json**. If clipboard access is denied, select and copy **Feedback
JSON** manually. The displayed JSON updates after further control edits. It
includes all current controls, the active rendering mode, camera, renderer,
viewport/DPR and actual target sizes, with `scene: "overview"`. It excludes
mission records and route/location lists.

This PR remains unmerged and undeployed pending the separate integration
decision. Browser verification uses the production-built Overview with local API
fixtures, never a production backend.

## Supplemental synthetic regression fixture

The standalone fixture below is retained for repeatable rendering/performance
regression evidence. It is separate from the live tuning workflow above.

This fixture is a synthetic laptop experiment based on `origin/dev`
`f0c1bd490cc8ab084bca481e93257f062788172c`, including Operator #428. It is not
approved for merge, production testing or deployment. The fixture has its own
local server; stop it to end that regression session.

## Prepare while online

Use Node 22.22.2 or a newer Node 22 patch. From the isolated worktree:

```sh
cd frontend/mission-planner
npm ci
```

Commit the experiment sources before making a review package. Then:

```sh
npm run build:bloom
npm run package:bloom
```

The packaging command refuses a dirty build, dirty sources or a build from an
older HEAD. The build stamp in `dist-bloom/build.json` identifies the source
SHA, dirty status, Node version and scenario version. The package is
`bloom-offline/<source-sha>/`, containing built assets, fixtures, attribution
files, server, `RUN-SHEET.md` and `START.txt`. Copy that whole folder to the
laptop. Dependencies are bundled; no npm install, backend, credentials, browser
cache or external imagery service is needed at runtime. Node and a WebGL2
browser must already be installed on the laptop. No new npm dependencies were
added.

## Start, stop and offline check

From the copied SHA folder, use:

```sh
node scripts/bloom-server.mjs
```

Open `http://127.0.0.1:4290` in a fresh isolated browser profile. Bindings are
loopback only; the server accepts only static GET/HEAD requests and refuses
`/api`. The standalone entry installs transport guards before importing the
scene. CSP forbids connection requests, remote assets, forms and embedding; the
label-layout worker is local. No persistent settings or API clients are loaded.
Use Ctrl+C to stop. For another port, set `BLOOM_PORT` on that command only. Do
not use plain `npm run preview` or the normal Vite dev server for this test.

Before departure, disconnect Internet access while retaining loopback, create
another fresh browser profile and cold-launch the full scenario. Confirm the
Earth, city mask, labels, traffic and weather specimens load; switch A/B, orbit,
zoom, replay, measure and export. This physical-laptop offline check remains an
owner action. The automated smoke blocks all non-loopback browser requests and
uses a fresh profile; it does not simulate OS airplane mode.

## Compare on the same laptop

1. Keep the browser version, window size, zoom, OS scaling and power/battery
   state fixed. Enter OS/power details in the experiment field. Record any
   thermal or battery changes separately. Default mode is **A · Current**.
2. Inspect default and full-overlay workloads. Switch modes in place; camera,
   layer choices, sun and particle pools persist. **Reset / replay** resets
   camera and seeded particles deliberately. Pause freezes particles/path for
   matched pictures. Manual orbit/zoom still works when the camera path is off.
3. Run **Measure A→B→A ×3** for each workload. Each run resets the fixed-frame
   camera/particle replay, warms 60 frames and samples the selected 60, 300
   (default) or 600 frame intervals. Let the series finish without
   hiding/resizing the window. A hidden tab, lost WebGL context or
   drawing-buffer change cancels the active capture.
4. Run **Measure output / B bounds** to compare the output-only compositor and B
   at 480/1920 bounds. These runs keep main DPR/drawing resolution fixed. Bloom
   bound means the longest input dimension passed to UnrealBloom; its bright
   target is half that, followed by five downsampled blur mip levels. JSON
   records the actual target sizes after resizing.
5. Export JSON and CSV after each set. The app retains at most 48 runs; store
   exports before closing the tab. JSON includes individual intervals, median,
   p95, sample count/duration, source SHA/dirty flag, settings, scenario,
   renderer, browser identity, drawing sizes, draw calls and start/end
   resource/available heap observations. It does **not** measure GPU duration.
   Compare the repeated A intervals to assess variability; report absolute B−A
   and relative B/A changes with the actual observations, without an invented
   FPS cutoff.
6. Take matched screenshots separately from timing. Warm the scene, pause, then
   save A, output-only and B at the same camera/settings. **Save canvas PNG**
   excludes DOM labels and the control strip; a browser/OS screenshot includes
   them. Keep settings/JSON with images. Inspect night/day/terminator, far-side
   occlusion, near/far zoom, tiny lights, crossing links, overlapping POIs,
   own-aircraft visibility, marker picking and bright weather contrast.

The owner judges appearance and physical-laptop responsiveness. Laptop results
cannot establish production-hardware acceptance. No merge/deployment is
performed by this experiment.

## Implementation and limits

One Canvas/scene stays mounted. At positive R3F priority, A renders once
directly; output-only/B render once through RenderPass → UnrealBloomPass →
OutputPass. The installed Three.js is 0.185.1. The
[reference pass stack](https://github.com/mrdoob/three.js/blob/dev/examples/webgl_postprocessing_unreal_bloom.html)
was rechecked on 2026-10-28. Main targets use half-float HDR and four MSAA
samples. Tone mapping/output conversion occurs in OutputPass for the compositor
modes. Shader color-space chunks resolve to linear output while rendering into
the linear targets. Only bloom targets are reduced; composer resize happens
before the explicit bloom resize. Every owned pass and composer target is
disposed on returning to A or unmount. Output-only uses A materials to isolate
compositor overhead.

A retains current component rendering and settlement texture. B raises city
emission to a configurable warm value (default 20), line/particle emission by 4
and chevron emission by 4. Star emission keeps intensity 8 with its semantic
color. B hides the extra simulated line/marker halos and narrows particle
sprites around their cores. This is an initial material-range experiment, with
live per-element emission and bloom controls; bright terrain may still enter
bloom at low thresholds. It uses no extra city or particle PointLights and no
extra scene pass for emission selection.

The fixture uses the existing CityLitGlobe, AnimatedFlowLine, StarMarker,
OverviewMapLabel and label-layout worker. It has synthetic POIs, crossing
route/link arcs, bounded seeded packet pools, own aircraft and traffic. Full
mode adds synthetic wind/weather specimens. It does **not** reproduce every
production weather/GFS/aviation/boundary/data layer, starfield or full Overview
layout. Visual and performance findings apply to this labeled specimen. The
approved full-scene comparison remains pending if this initial look warrants
that work. NASA texture restoration is a separate axis and was not attempted.

Replay advances simulation 1/60 second per rendered frame, independent of wall
clock. This matches frame-index workloads but is deliberately not live-clock
playback. Warm-up is frame-count based; physical-laptop testing should repeat
runs after shaders settle. Frame diagnostics are bounded; JS heap observations
are browser-dependent and are not total GPU memory. No historical slowdown cause
is asserted.

## Developer verification and cleanup

From repository root, with an explicit wall-clock bound:

```sh
timeout --kill-after=10s 10m ./tools/verify frontend
timeout --kill-after=10s 5m npm --prefix frontend/mission-planner run lint
timeout --kill-after=10s 12m node frontend/mission-planner/scripts/bloom-smoke.mjs
```

Install the matching Playwright Chromium before the smoke when necessary, or set
`BLOOM_CHROMIUM_EXECUTABLE` to an already provisioned executable. The smoke
explicitly uses SwiftShader; it is a rendering/export/offline guard check, not a
laptop GPU benchmark. Evidence and process ownership go to
`frontend/mission-planner/test-results/bloom/<sha>/`. The runner closes
contexts, browser and its private server on exit/signals. Verify the recorded
PIDs/groups and port have gone after a timeout before restarting. No Docker
resources are created. Keep evidence and the open-PR worktree; stop all runtime
resources as soon as verification ends.

To rebuild, repeat `build:bloom`/`package:bloom` after committing sources. To
remove local generated packages, remove only this task's `dist-bloom/` and
`bloom-offline/<sha>/` directories after preserving desired evidence. The
primary checkout stays on `dev`; the experiment branch stays isolated until an
explicit owner decision. Follow the normal worktree cleanup after any separately
approved merge.

## Review evidence and POI interaction

Experiment POIs opt into a 12 CSS-pixel picking radius in A, output-only and B.
An Object3D raycast disk supplies the target without drawing halo geometry or
allocating GPU resources. It checks Earth occlusion and the camera frustum. The
visual halos/core stop contributing hit intersections for these experiment POIs;
ordinary Overview retains its existing picking. Real raycast and browser
regressions compare center, offset, overlapping and far-side clicks in A/B/A.

PR #433's **Offline bloom review evidence** Actions run publishes the artifact
`overview-bloom-<source-sha>` for 30 days. The PR links its exact run/artifact.
The artifact contains a ready-to-extract offline ZIP, SHA-256 checksum, matched
A/output/B default/full PNGs, `visual-settings.json`, raw/summary frame-interval
JSON/CSV, pointer test results and verified runtime teardown. Open `START.txt`
and `RUN-SHEET.md` inside the package. These remain explicit SwiftShader smoke
results; physical-laptop acceptance is pending. Rerunning the same source run
regenerates an expired artifact without deploying or merging anything.

To produce the same bundle locally after a clean build and copied-package smoke:

```sh
timeout --kill-after=10s 1m node frontend/mission-planner/scripts/bloom-verify-cleanup.mjs
timeout --kill-after=10s 2m node frontend/mission-planner/scripts/bloom-review-bundle.mjs
```

The evidence workflow runs only for the isolated experiment branch targeting
`dev`, or a manual run on that branch. It checks out the PR head SHA explicitly,
uses read-only repository permission, starts only its private loopback fixture
server, and has no production origins, deployment steps or operational replay.

## Temporary bloom tuning and sending preferences back

Open **Bloom tuning**, then choose B or click **Find city glow**. This preset
isolates cities, mutes the terrain, raises city emission, lowers the threshold
and increases bloom resolution. The original settlement mask and fixed sun are
retained. A remains the original comparison baseline.

- **Final scene** shows the result. **Bright pass** shows pixels that survive
  the actual downsampled luminance threshold before blur. **Bloom only** shows
  the actual blurred light contribution, including strength, on black.
- **Isolate cities** hides other luminous layers and mutes reflected terrain
  lighting. It retains Earth depth/occlusion and the existing particle pools.
  Turn it off to judge the complete synthetic specimen again.
- Adjust city emission and warm color, routes/link emission, particles, POI
  cores, aircraft emission, exposure, threshold, strength, radius and bloom
  bound. Emission controls update live uniforms without resetting the camera.
  Bloom bounds include 3840 for checking small lights at higher resolution.
- City emission defaults to warm amber `#ffb15c`, intensity 20 in B. The earlier
  fixed value was 5 with cool-white color. A keeps intensity 0.35 and its
  original color. Other B defaults remain line/particle/aircraft gain 4 and POI
  intensity 8.
- The displayed city luminance is an upper bound at full mask/full night, **not
  a sampled pixel value**. Texture filtering, night fade and reduction into the
  bright-pass target can leave small lights below the threshold even when they
  are visible in the final surface image. Use Bright pass/Bloom only to inspect
  the actual result rather than judging from nominal intensity.

Click **Copy settings** and paste the JSON into chat, or attach the file from
**Download settings.json**. These work before any timing run. If clipboard
permission is unavailable, the panel selects a readable JSON text box for manual
copy. The report includes build SHA/dirty flag, scenario, all bloom/emission
values, warm color and linear RGB, isolation/view, camera, viewport/DPR, actual
bloom target sizes, renderer identity and scene/power information. It takes an
independent snapshot; later adjustments do not rewrite an earlier export. **Save
canvas PNG** also downloads a companion settings JSON for that frame.

Measurement series close the panel, disable isolation and use Final scene in all
modes while retaining the chosen emission/exposure values. Each timing JSON/CSV
records those values. The temporary controls exist only in this offline
experiment; they do not create a permanent settings subsystem.
