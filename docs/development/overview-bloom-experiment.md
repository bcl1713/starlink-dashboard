# Offline Overview bloom experiment (#429)

This branch is an isolated synthetic laptop experiment based on `origin/dev`
`f0c1bd490cc8ab084bca481e93257f062788172c`, including Operator #428. It is not
approved for merge, production testing or deployment. Stop the local server to
roll back; the normal frontend entrypoint has no experiment controls/composer.

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
emission to 5, line/particle emission by 4 and chevron emission by 4. Star
emission keeps intensity 8 with its semantic color. B hides the extra simulated
line/marker halos and narrows particle sprites around their cores. This is an
initial material-range experiment, with threshold/strength/radius controls;
bright terrain may still enter bloom at low thresholds. It uses no extra city or
particle PointLights and no extra scene pass for emission selection.

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
timeout --kill-after=10s 8m node frontend/mission-planner/scripts/bloom-smoke.mjs
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
