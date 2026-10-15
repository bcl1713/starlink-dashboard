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
The verified final review fixes are in
`0b3cd44692922b3c2365d019fe986dc8094742b4`, also pushed for testing.

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

Canonical frontend verification passes 387 tests in 73 files and the production
TypeScript/Vite build. Static verification runs the complete repository tier,
including typing-policy tests, using the repository's development requirements
for the Python test environment. No gate is skipped.

All 27 new responsive/input cases and 60 existing Overview/Configuration cases
are covered across serial headed runs and focused corrected-case rechecks. The
broad regression initially passed 29/44; its failed/skipped cases are covered by
subsequent runs. Operational coverage passed 14/19, followed by 3/5 and 2/2
corrected-case rechecks. No motion/provenance tolerance changed.

The independent whole-branch review identified three important defects, each
reproduced before its fix: hidden desktop Reset/follow status, overflowing
desktop arrival content at the minimum width, and route recovery retaining an
initial fallback camera frame. All three fixes pass their focused regressions;
the complete responsive/input suite passes 27/27. Manual pose and default
position-update behavior remain covered. Desktop geometry now also measures the
Reset/status group. Its visual baseline was inspected and passes without
snapshot updates.
All 11 existing desktop composition/readability cases are covered by 10/11 and
a corrected 1/1 recheck. The backdrop contrast fixture uses 18:00 UTC to put its
Americas route in daylight; its pixel threshold and deadline are unchanged.
Separate production captures retain midnight lighting.

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
recordings are indexed by `production-final/manifest.json`, with per-capture
viewport, root size, DPR, scale, layout, CSS/buffer bounds, camera pose and API
provenance. `production-smoke.json` records real responses and Prometheus
health; `production-persisted-after-restart.json` records saved history after
restart. `docker-containers-after.txt`, `docker-volumes-after.txt` and
`docker-networks-after.txt` record cleanup. Raw regression logs and browser
artifacts remain alongside these files; this repository report does not claim
those local artifacts are remotely published.

The final manifest is `production-final/manifest.json`, indexing 23 settled-pose
stills and seven recordings from pushed candidate
`0b3cd44692922b3c2365d019fe986dc8094742b4`. Its production image identity is
`sha256:ec3f1f40ea9285072e4a1cdf66e9abdf8294ea521d113bca1c924bfc83d6ae7b`.
Earlier captures at `80c18e86` remain in `production-reviewed/`.
Later documentation-only
validation commits retain this evidence only when all runtime input trees are
verified identical. Desktop, mobile rotation/scroll and enlarged-text recordings
have inspected contact sheets in `video-1-inspection/`, `video-2-inspection/`
and `video-6-inspection/` beneath the capture directory.

Real API smoke responses are 200, the Prometheus target is UP, and Configuration
saved 900 seconds through the real API; the value survives navigation, reload
and a backend restart. A fresh simulation has no route/selection/catalog or
GEP. Position availability in the captures comes from the live status sample;
the initial recorded response has a valid longitude near 180 degrees.
Route/aircraft/GEP/POI and history captures use explicitly
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

Two minor review findings remain deferred: landscape eligibility assumes 24px
total horizontal padding, so larger safe-area insets can reduce the map below
its intended 560px width; desktop POI reservations omit the clock/metric sibling
bounds, so long visual labels can appear behind those panels. Complete accessible
POI names remain available.

Operator instructions are in [Overview](../features/overview.md); actual
thresholds, scroll ownership, content escape and camera policy are documented in
[responsive architecture](../architecture/overview-responsive-layout.md). The
[approved plan](../superpowers/plans/2026-10-02-overview-responsive-mobile.md)
and
[source contract](../superpowers/plans/2026-10-02-overview-responsive-mobile-source-contract.md)
record the implementation boundary and user steering.

## Camera and fullscreen feedback follow-up

Brian's fullscreen screenshot called for a centered globe with the route filling
usable space on the right. Desktop native fullscreen now measures the opening
beside the metrics, below the upper cards and above the bottom overlays, then
rotates and fits the route inside it while keeping projection offsets zero.
Other views retain their previous framing. The fullscreen control now uses a
20px Lucide Expand SVG with centered button alignment.

Automatic camera motion now uses maximum speed and acceleration, accelerating
from rest and braking to rest without a fixed or minimum duration. Rotation is
limited to 10 degrees/second and 2 degrees/second squared; logarithmic zoom and
viewport offsets have their own limits. Controller tests verify both rotation
and zoom limits through complete moves at 30, 60 and 144 fps, including stopping.
A small-move test verifies there is no minimum runtime.

Follow-up verification uses the built Vite preview, separate from the earlier
Docker production evidence above: 393 unit tests pass, lint and production
build pass, and five focused headed Chromium tests pass for fullscreen route
geometry, Explore/manual preservation, reduced motion, desktop input and reset
intermediate poses. A four-layout browser check also verifies the fullscreen
SVG, centered icon-only buttons, 44px targets and native fullscreen entry/exit.
Evidence is under `/tmp/issue220-evidence/`: `camera-feedback-units.log`,
`camera-feedback-build.log`, `camera-feedback-lint.log`,
`camera-feedback-browser.log`, `fullscreen-icon-geometry.json` and
`fullscreen-route-feedback.png`. No Docker containers were started for this
follow-up; the actor's Docker daemon reports no running containers.

A subsequent dt check exposed the inherited 50ms frame-delta cap, which slowed
motion below 20 fps. Visible frames now use their complete elapsed delta.
Hidden tabs pause motion and discard the first resumed delta. Regression tests
compare identical four-second poses at 5, 10, 15, 30, 60 and 144 fps and verify
hidden/resumed behavior. The cap and hidden-frame cases failed before the fix.
Final dt verification: all 400 unit tests, build and lint pass; two headed
Chromium checks pass for reset interpolation and manual preservation. Logs are
`camera-dt-units.log`, `camera-dt-build.log`, `camera-dt-lint.log` and
`camera-dt-browser.log` in the same evidence directory. The preview stopped
afterward; this correction did not start Docker containers.

## Unified CameraControls and closer following

The CameraControls migration was checkpointed and pushed as `5602e027` at
Brian's request before changing follow framing. The subsequent animation audit
found that following still fitted the whole globe, CameraControls rotation had
no speed cap, and measured projection offsets changed immediately.

Initial route/aircraft framing, follow activation and changing positions, Reset,
route recovery and fullscreen/layout changes now use the same critically damped
control with full visible-frame delta. Its damping parameter is 1.2 seconds,
with no prescribed animation duration. Dolly is capped at 1.5 scene units/second
and angular damping at 10 degrees/second. Projection offsets use the same
damping equation with a 0.08 viewport-fractions/second cap per axis. Equivalent
polls retain both camera and projection motion. Manual input freezes the
current pose, while reduced motion applies the destination discretely. Hidden
tabs retain the existing pause/resume handling.

Following now targets a distance of 4.5 scene units around the radius-two globe,
with the aircraft in the panel-safe opening. Default initial route framing and
fullscreen route extent calculations are retained. The particle-flow animation
already advances with delta, and history charts use monotonic elapsed time;
marker and ribbon frame callbacks only adjust projected sizing.

Five new regression cases failed before these changes. All 403 unit tests,
production build and lint now pass, along with four headed Chromium checks for
fullscreen route fitting, default/opt-in follow behavior and close zoom, follow
pause/Reset and eased Reset poses. Logs are `follow-unified-red.log`,
`follow-unified-units.log`, `follow-unified-build.log`,
`follow-unified-lint.log` and `follow-unified-browser.log` under the existing
`/tmp/issue220-evidence/` directory. These checks used a local built preview;
no Docker containers were started.
Two additional headed Chromium checks pass for manual camera preservation
through viewport rotation and reduced-motion chart behavior; their log is
`follow-unified-manual-browser.log`. The previews have stopped and the actor's
Docker daemon reports no running containers.
