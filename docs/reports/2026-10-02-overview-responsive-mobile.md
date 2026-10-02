# Responsive Overview — #220

Date: 2026-10-02. Status: ARCHIVED implementation and validation snapshot.
Physical-device acceptance remains pending.

## Behavior and delivery boundary

Overview retains one clock group, one Three.js Canvas and five uPlot instances.
Phones use page scrolling, with arrival/planning panels in the map stage and
metric cards below it. A compact landscape strip uses a scrollable metrics rail
beside the map. Content that cannot fit escapes to readable flow. Desktop keeps
the established panel composition; measured container size and root text select
the mode rather than user-agent detection.

Default responsive gestures scroll. Explore enables globe interaction; Escape,
Exit, focus loss and layout changes leave exploration while retaining manual
pose. Fullscreen and viewport rotation retain renderer/plot identity. The
expandable legend reserves space for projected POI labels, whose full accessible
names remain available.

Brian clarified camera behavior during implementation: opening prefers the route
extents inside the area clear of panels, intentionally placing the route to the
right of the left metrics rail. Aircraft movement does not change the default
camera. Configuration offers browser-local **Follow aircraft on Overview**,
initially off. Fresh map positions drive opted-in following; stale/error/missing
positions pause it. Manual input cancels automatic movement. Automatic moves use
smoothstep easing over 700ms. Reduced motion uses discrete updates and disables
optional scene motion and plot transform transitions while retaining accepted
data updates.

## Source and runtime identity

Selected base: `fa1bba47844f329fb0d3ae4a7c1c4471526c52f2` (`dev`, #219/#237).
Branch: `feat/220-responsive-overview`, isolated worktree `/tmp/starlink-220`.
Responsive composition: `f240e65678277fee6117cbecc518c133c0acc92b`.
Camera/input/preference implementation:
`57f1f44b2a94dcd4e4b4caf23f1b959c21649166`. Brian requested publication of the
branch as-is for testing; this implementation was pushed. No merge, deployment
or issue closure is included.

The production image uses an immutable archive of the pushed candidate, the
repository's Dockerfile/Nginx configuration, and candidate SHA build input. Its
exact SHA, image identity and digest are recorded in the capture manifest. The
reused backend image has unchanged source/configuration against this candidate.
Production APIs and intercepted fixtures are recorded separately.

The isolated project uses the actor-owned rootless daemon at
`unix:///run/user/1002/docker.sock`, preserving inherited Docker configuration.
Loopback ports are 15220 (Nginx), 18220 (backend) and 19220 (Prometheus).
Task-specific volumes/network are removed by an exit trap after smoke checks,
including failure paths. Evidence and image cache do not require running
services.

## Verification and evidence

Canonical frontend verification passes 385 tests in 73 files and the production
TypeScript/Vite build. Static verification runs the complete repository tier,
including typing-policy tests, using the repository's development requirements
for the Python test environment. No gate is skipped.

All 25 new responsive/input cases and 60 existing Overview/Configuration cases
are covered across serial headed runs and focused corrected-case rechecks. The
broad regression initially passed 29/44; its failed/skipped cases are covered by
subsequent runs. Operational coverage passed 14/19, followed by 3/5 and 2/2
corrected-case rechecks. No motion/provenance tolerance changed.

New responsive/input cases exercise wheel and touch, landscape gap forwarding,
browser zoom modifiers, Explore/Exit, interrupted pointer capture, easing,
Configuration following and source failures. DPR 1, 1.5 and 2 rotation checks
compare CSS and actual drawing-buffer sizes while retaining Canvas/uPlot nodes.
Existing chart provenance, gap, motion, resize and resume assertions retain
their tolerances. Legacy oracles are updated only for intentional composition:
explicit globe selection, map-before-metrics order, shell scroll ownership,
170px card minimum, and reachability when content fits without scrolling.

Local session evidence is in `/tmp/issue220-evidence/`. Immutable before
captures are in `baseline/manifest.json`; the final production captures and
recordings are indexed by `production-reviewed/manifest.json`, with per-capture
viewport, root size, DPR, scale, layout, CSS/buffer bounds, camera pose and API
provenance. `production-smoke.json` records real responses and Prometheus
health; `production-persisted-after-restart.json` records saved history after
restart. `docker-containers-after.txt`, `docker-volumes-after.txt` and
`docker-networks-after.txt` record cleanup. Raw regression logs and browser
artifacts remain alongside these files; this repository report does not claim
those local artifacts are remotely published.

The manifest indexes 23 settled-pose stills and seven recordings from pushed
candidate `80c18e868181ce53d931d667a351d633d62d5509`. Later documentation-only
validation commits retain this evidence only when all runtime input trees are
verified identical. Desktop, mobile rotation/scroll and enlarged-text recordings
have inspected contact sheets in `video-1-inspection/`, `video-2-inspection/`
and `video-6-inspection/` beneath the capture directory.

Real API smoke responses are 200, the Prometheus target is UP, and Configuration
saved 900 seconds through the real API; the value survives navigation, reload
and a backend restart. A fresh simulation has no route/selection/catalog and
emits an invalid longitude with no GEP; real captures truthfully show position
unavailable. Route/aircraft/GEP/POI and history captures use explicitly
controlled API fixtures over the same production assets. All three cleanup
inventories are empty after successful and failed smoke paths.

## Limits and operator guidance

Chromium uses ANGLE SwiftShader in this environment. Software captures and DPR
1.5 emulation do not establish Brian's physical 3000×2000 display at 150% system
scaling, actual phone gestures, or ten-foot reading distance. Those checks
remain explicitly pending Brian's assessment of the pushed branch. Forced opaque
fallback verifies shipped styling rather than a blur-incapable browser. Global
routes can remain partly behind the globe; fitting preserves spherical geometry
rather than flattening far-side points.

Operator instructions are in [Overview](../features/overview.md); actual
thresholds, scroll ownership, content escape and camera policy are documented in
[responsive architecture](../architecture/overview-responsive-layout.md). The
[approved plan](../superpowers/plans/2026-10-02-overview-responsive-mobile.md)
and
[source contract](../superpowers/plans/2026-10-02-overview-responsive-mobile-source-contract.md)
record the implementation boundary and user steering.
