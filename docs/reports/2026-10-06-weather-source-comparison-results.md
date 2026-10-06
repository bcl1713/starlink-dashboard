# Weather source comparison results

Retain RainViewer for [issue 288][issue], using real higher-zoom tiles for the
visible region. MRMS and OPERA raw generation works within the research limits,
but does not replace international coverage or demonstrate a sufficient benefit
to justify operating a new ingest service. Keep source adaptation behind the
backend's normalized contract, as the [aviation-weather comment][comment]
recommends. Future aviation, satellite and model products remain separate work.

## What was measured

Exact native replay candidate: `553d96ded55971cda417cd79f1c14182d7d2bab6`.
Production Dockerfiles, Nginx, backend lifespan and the existing Three globe
were used with a test-only shader and saved-source asset mount. Both browser
tests passed in 7.4 minutes. Eighty screenshots cover U.S./European
precipitation, desktop 1920-by-1080, fullscreen, mobile 390-by-844, and
day/night. Paired rows have identical camera matrices, projection, viewport,
renderer and cache state.

The renderer was Chromium ANGLE/Vulkan SwiftShader. These are offline research
captures, explicitly labeled in the screenshots. They do not prove production
camera selection, scheduling, lifecycle or device performance. The passive UI
freshness display belongs to the test fixture; immutable source times are in
capture metadata and screenshot labels.

| Source                   | Observed UTC, 2026-10-06 | Input                                   | Geographic resolution                                |
| ------------------------ | ------------------------ | --------------------------------------- | ---------------------------------------------------- |
| RainViewer, U.S.         | 02:30                    | Captured 512-pixel PNGs, levels 2/5/6/7 | Provider tiles; zoom is not native sensor resolution |
| MRMS PrecipRate          | 02:30                    | 476,684-byte decompressed GRIB          | 0.01 degree grid, approximately 1 km                 |
| RainViewer, Europe       | 02:10                    | Captured 512-pixel PNGs, levels 2/5/6/7 | Provider tiles; zoom is not native sensor resolution |
| OPERA instantaneous RATE | 02:15                    | 1,528,676-byte HDF5                     | 2 km projected grid                                  |

U.S. observations match exactly; Europe's five-minute difference can change
storm shapes. RainViewer's palette and raw precipitation-rate styling differ, so
colors are not equivalent intensity scales. No model, satellite or forecast
values were added. Covered zero precipitation remains distinct from missing
observations, including reprojection edges and areas outside regional coverage.

## Generation and browser costs

Raw generation ran offline in one container limited to one CPU and 2 GiB. Each
source produced 40 matched radar/mask pairs: complete level-2 fallback plus
eight regional pairs at each of levels 5, 6 and 7.

| Source | Cold open/decode wall / CPU | Warm render wall / CPU | Generated PNG bytes |
| ------ | --------------------------- | ---------------------- | ------------------- |
| MRMS   | 0.603 / 0.602 s             | 1.767 / 1.765 s        | 199,652             |
| OPERA  | 0.072 / 0.072 s             | 1.257 / 1.257 s        | 211,006             |

Peak RSS was 640,147,456 bytes (610.5 MiB) for the combined process. OPERA's
record inherits this high-water mark; these values cannot establish independent
per-source RAM costs. Open/decode and render are distinct phases; this is not an
end-to-end ingest latency measurement. Retained data stayed within 1 GiB.

| Source     | Rendered views | Replay PNG fetches | Compressed PNG bytes fetched |
| ---------- | -------------- | ------------------ | ---------------------------- |
| RainViewer | 40             | 1,728              | 11,340,912                   |
| MRMS       | 20             | 864                | 1,798,050                    |
| OPERA      | 20             | 864                | 2,066,746                    |

These totals repeat baseline and regional assets across comparison variants;
they are browser replay traffic, not upstream provider traffic or production
bandwidth forecasts. Fetch/decode/upload timings and eight manual frame samples
per view are retained in `browser/comparison.json`. Frame medians were 0–0.1 ms;
that measurement's granularity and manual software-rendered path make it
unsuitable for a user-device performance claim.

The research owner accounts for 48 MiB weather GPU allocation and 81 MiB peak
owned decoded allocation, below the 48/96 MiB ceilings. These follow actual
canvas dimensions and bitmap ownership; they are not total browser RSS. Capture
used a separate 30-attempt rolling-minute limit and two active requests.
Production still needs its shared 90-attempt budget, 30-attempt detail sublimit,
four exchanges with at most two detail exchanges, and coarse priority.

## Visual judgment and remaining acceptance

Inspected U.S. and European comparisons show smaller storm-edge features in
RainViewer level-6 detail than in its level-2 fallback. Raw RATE tiles also show
regional detail, but their distinct products, masks and palette prevent a claim
of objectively better imagery. Outside the selected eight slots the coarse
fallback remains visible; production edge blending is still required.

Opacity 0.40 is the recommended candidate between the rendered 0.35 and 0.45
alternatives; the 0.72 baseline obscures more terrain. Keep missing-coverage
hatching at its existing independent factor of 0.17. Aircraft, routes and POIs
were not populated in this research scene, so the final default must be checked
with those overlays in production acceptance. No final opacity or completed
issue-288 claim follows from this replay alone.

Synthetic tests independently verify geographic lookup, mask polarity, mixed
identity rejection and texture restoration after both success and failure.
Report tests reject incomplete costs, missing precipitation, mismatched camera
conditions or timestamps, unverified hashes, synthetic substitution and failed
cleanup/restoration. Research suite: 67 passed; frontend acceptance selection: 9
passed. The new production plan covers remaining behavior and final-SHA
acceptance.

## Retained evidence and cleanup

Evidence is local and ignored by Git, rooted at
`.superpowers/sdd/issue-288-weather-detail/evidence/` in the task worktree:

- `capture-initial/capture.json`: immutable identities, hashes, attribution,
  source URLs, source timestamps and matched-region selection.
- `capture-initial/generation.json`, `research-runtime.txt`: actual compute,
  memory, projection, source grid and dependency/driver records.
- `553d96ded55971cda417cd79f1c14182d7d2bab6/browser/comparison.json`: all 80
  recorded views, PNG requests, camera/renderer conditions and measured costs.
- That candidate's `browser/` subdirectories: screenshots and Playwright
  results.
- `images.txt`, `runtime-owner.json`, `process-owner.json`, `cleanup.json` and
  `process-cleanup.json`: image and ownership records; both cleanup checks pass.
- `source-comparison-report.json`: validated summary; production refinement is
  explicitly marked unverified.
- Earlier failed candidates retain traces explaining fixes to the static-asset
  route, cached shader-uniform identity and software-renderer test deadline.

Task-owned processes, Compose containers, networks, private volumes, temporary
source archive and both ports (15288/18288) were verified released. No runtime
service remains for this comparison. Preserve the open-PR worktree and evidence.

[issue]: https://github.com/bcl1713/starlink-dashboard/issues/288
[comment]:
  https://github.com/bcl1713/starlink-dashboard/issues/288#issuecomment-6008230258
