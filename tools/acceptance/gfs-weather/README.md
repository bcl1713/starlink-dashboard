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
