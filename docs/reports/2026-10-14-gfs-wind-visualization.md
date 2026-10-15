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

## Acceptance closeout — 2026-10-15

The owner confirmed that they have used the new winds and that they work
fine, and explicitly requested closure of the remaining tasks without further
owner testing. Wind visualization is accepted for use; C1 and H1 are closed by
owner acceptance, with their formal runs waived. No workstation, paired URLs,
or additional source capture is required to close this work.

The formal C1 pinned NOAA presentation run was not completed: the saved
2026-10-06 GRIB/oracle capture was absent and the environment proxy rejected
NOAA S3 with CONNECT 403. The formal H1 paired hardware benchmark was also not
run. Owner acceptance does not establish measured source agreement or the
specified p95 performance thresholds. Existing synthetic and software-rendered
results retain their original scope and labels. The optional harness remains
available for future diagnostics in the
[runner guide](../../tools/acceptance/gfs-weather/README.md).

These historical evidence limits are no longer open acceptance tasks or
prerequisites for subsequent work. Revisit them only for a concrete regression
or a new explicit requirement.

The repository link checker `lychee` is not provisioned; GitHub release
provisioning was denied by the proxy. Other static controls are available.
All temporary browser/server/container resources are task-owned and must be
stopped after verification. Evidence and the open-PR worktree are retained.
