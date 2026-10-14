# GFS foundation acceptance

Run from a clean exact committed candidate with the actor's configured Docker
daemon. Use an existing browser; the runner never installs one.

```sh
GFS_ACCEPTANCE_SOURCE_DIR=/path/to/pinned/source \
  timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh \
  "$(git rev-parse HEAD)" /path/to/chrome foundation
```

The source directory contains `source.idx`, `u.grib2`, `v.grib2`, `t.grib2`,
`sp.grib2` and the independent `oracles.json`. The runner verifies the pinned
2026-10-06 00Z F006 source hashes before allocation. HTTP substitutions supply
source listing/index/range bytes only. Production quota, version verification,
scientific child, normalization, IPC, store and API code remain active. A labelled
historical clock replay starts after the unchanged bulletin/radar browser journey.

Project `starlink-290-gfs-foundation` owns ports 15292/18292 and disposable
volumes. The signal/exit cleanup stops its process trees and Compose resources.
The shared acceptance evidence helper inventories a SHA-qualified directory in
`test-results/gfs-foundation`. A foundation PASS requires source oracle samples,
Nginx buffer hashes/masks, ETag delivery, acknowledged disable, cancellation,
failed decoder and source-version denial, core response latency, worker cgroup
CPU/peak memory, disk/network bytes, and verified cleanup. Preserve this evidence
when removing the feature worktree.

SwiftShader rendering and source fixtures are explicit evidence labels. This
runner accepts the backend foundation only; it does not accept model presentation
or claim current live NOAA availability.

For integrated Phase 2 acceptance, supply the same foundation files plus a
`presentation/` subdirectory containing the captured files whose digests are in
[presentation-source.json](presentation-source.json), then run:

```sh
GFS_ACCEPTANCE_SOURCE_DIR=/path/to/pinned/source-root \
  timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh \
  "$(git rev-parse HEAD)" /path/to/chrome presentation
```

Project `starlink-290-gfs-presentation` owns loopback ports 15293/18293. Separate
fresh private-volume phases run the existing bulletin/radar browser regression,
foundation controls, and native GFS presentation. Browser test definitions come
from the exact candidate archive; provisioned dependencies require an identical
lock and are attached only after image builds. Source transport serves only the
captured real F006/F009 objects, including the actual 150/200 hPa FL390 brackets
and F009 850 hPa terrain case. Source hashes and independent physical oracles
are retained alongside actual shader readbacks and native geometry checks.

Presentation PASS additionally requires two-context Configuration propagation,
selection/horizon and original-deadline controls, combined desktop/fullscreen/
mobile screenshots, cancellation/recovery, and encoded/decoded/GPU/slot peak
measurements within the shared allowance. A cached-image diagnostic can help
investigate failures but cannot write PASS; final acceptance builds all three
candidate images with `--no-cache`. Historical replay and software rendering
remain explicit; deployment hardware and live source availability need separate
validation.

## Wind gradient and particles

Presentation now requires `wind_raster`, `wind_particles`, `exclusive_modes`
and `reduced_motion` in addition to every existing foundation/presentation
proof. Numeric shader readbacks check signed U/V, magnitude after vector
interpolation, knots, masks and sRGB palette output. Finite positive native
sample and particle counts and existing shared resource peaks are mandatory.
Wind and temperature are exercised sequentially in both browser contexts.

The optional `playwright.gfs-synthetic.config.ts` runs labeled synthetic
controls against a loopback production build served by Nginx. It records
software shader/color, mask, motion, toggle and responsive legend evidence.
It cannot write the pinned-source presentation PASS.

`playwright.gfs-hardware.config.ts` requires the six hardware inputs listed in
[the approved plan](../../../docs/superpowers/plans/2026-10-14-gfs-wind-visualization.md),
plus `GFS_HARDWARE_TARGET` (machine/OS/CPU/GPU/browser/refresh identity) and
`GFS_HARDWARE_SOURCE_MANIFEST` (the readable pinned source manifest). It uses
headed provisioned Chrome without software-rendering flags or service startup.
Every paired run must meet p95 update ≤4 ms and p95 total-frame ≤1.2 times the
barb baseline. Missing target/source inputs and software rendering leave H1
unverified; synthetic and SwiftShader results cannot satisfy it.

The H1 manifest is independently prepared from the two exact builds and pinned
replay normalization. It must contain `source_root`, `clock_utc_ms` (the pinned
2026-10-06 06Z replay epoch), `normalized_buffers` (U/V/T/mask SHA-256 digests),
and `targets.BASELINE` / `targets.CANDIDATE`. Each target supplies its `sha`,
`origin` and an `assets` map of origin paths to SHA-256 digests from that build,
including `/index.html` and every referenced JS/CSS asset. Archive this manifest
with build provenance; do not derive expected hashes from the served target.
The harness hashes every local pinned presentation source, served build asset,
and admitted model buffer. It requires F006 at 500 hPa, baseline barbs, matching
admitted radar/bulletins when selected, and 2,000 candidate particles throughout
each capture. The baseline is dev SHA
`aef333d46a30c131f61a5de3bfe318c6a7618f43`; target origins and SHAs must differ.
Use a 30-minute outer timeout for twelve paired warmup/capture periods and setup.
The manifest also includes `overlay_products`: the ordered non-GFS catalog
signatures `{layer, instance, payload}` from the pinned combined replay, where
`payload` is its payload SHA-256 or radar product ID. Both served targets must
match these signatures when overlays are enabled.
