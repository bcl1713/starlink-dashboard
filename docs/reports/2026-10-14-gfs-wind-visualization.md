# GFS Wind Visualization Evidence

The native implementation replaces wind barbs with an interpolated wind-speed
raster and bounded flow trails. Temperature and winds are exclusive in both
Configuration and server settings; both may be off. The knots key uses fixed
0/25/50/75/100/125/150+ stops. Reduced motion retains the raster/key and releases
particle resources. Existing GFS ingestion and flight-level contracts remain.

The [approved design](../superpowers/specs/2026-10-14-gfs-wind-visualization-design.md)
and [plan](../superpowers/plans/2026-10-14-gfs-wind-visualization.md) describe the
interfaces and gates. Rendering and acceptance tasks are linked continuations
to keep each document within the repository's 300-line limit.

## Verification Scope

Unit/integration coverage exercises server exclusivity, atomic legacy repair,
frontend toggles, signed-vector interpolation, palette endpoints, masks,
frame-rate-independent integration, timing caps, trail resets, owner rollback,
lifecycle cancellation, reduced motion, and cleanup. A final independent review
found four Important issues; fixes preserve bulletin availability during GFS
lock failure and strengthen ordinary shader output and H1 provenance/timeouts.
No Minor findings were deferred. Exact-candidate results are attached to the PR.

The labeled synthetic Nginx/Chromium journey uses independent wind fields to
check the admitted shader/framebuffer, U/V and knots quantization, ordinary
color/alpha, opposing vectors, calm/masked samples, trail direction and occlusion,
mode switching, preference changes, responsive legends, and resource release.
Its artifacts are under `test-results/gfs-wind-synthetic`; SwiftShader evidence
is software rendering, not source validation or hardware performance approval.

## Outstanding Gates

C1 pinned NOAA presentation acceptance is unverified: the saved 2026-10-06
GRIB/oracle capture is absent, and this environment's proxy rejects NOAA S3
with CONNECT 403. The user confirms GFS works on local dev. No substitute
source or synthetic presentation PASS is claimed.

H1 is unverified: no target workstation or paired production URLs were supplied.
The headed hardware harness validates the independently archived build/source
manifest, pinned replay buffers, F006/500 hPa, overlays, baseline barbs, and the
full-cap candidate throughout capture. It rejects software rendering. Every
paired run must meet p95 particle update ≤4 ms and total frame duration ≤1.2
of the baseline. See the [runner guide](../../tools/acceptance/gfs-weather/README.md).

The repository link checker `lychee` is not provisioned; GitHub release
provisioning was denied by the proxy. Other static controls are available.
All temporary browser/server/container resources are task-owned and must be
stopped after verification. Evidence and the open-PR worktree are retained.
