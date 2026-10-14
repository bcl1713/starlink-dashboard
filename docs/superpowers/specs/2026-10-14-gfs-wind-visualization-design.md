# GFS wind gradient and particles

Status: approved by the user on 2026-10-14. Approval covers preparation of a
separate implementation plan for review. Begin implementation only after that
plan is approved and its execution method is selected.

## Intended outcome

Replace the Overview globe's GFS wind barbs with a continuous wind-speed color
gradient and animated trails. Color communicates speed in knots; trails show the
direction the air moves, with faster motion for stronger winds. The atmosphere
legend explains the colors and retains the selected level and forecast context.

The user specified that GFS wind and temperature are mutually exclusive,
enforced by their Configuration toggles. Temperature has no wind particles. Both
GFS layers may be off. These preferences apply across Overview displays through
the existing installation-wide settings and revision polling.

The palette, legacy-settings precedence, particle limits, and reduced-motion
behavior below were proposed design defaults accepted with spec approval.

## Existing implementation and scope

The inspected baseline is `origin/dev` at
`aef333d46a30c131f61a5de3bfe318c6a7618f43`. The implementation plan must record
its actual full base SHA and account for subsequent changes in `dev`.

Existing production code already provides:

- An admitted 720 × 361 global grid with quantized eastward U and northward V
  components in m/s, temperature in K, and a shared validity mask.
- CPU bilinear sampling in `grid-sampling.ts`, including longitude wrapping and
  conservative validity handling.
- A temperature globe mesh and packed-data shader in `grid-renderer.ts` and
  `grid-shader.ts`; wind currently draws at most 2,000 white barbs.
- Shared Configuration preferences in `AviationSettingsCard.tsx`, atomic saved
  revisions in `aviation_weather/settings.py`, and revision-driven GFS demand
  cancellation through the existing bridge and controller.
- An atmosphere key in `GfsStatus.tsx` inside the existing map legend.

This change covers wind presentation, exclusive GFS selection, and associated
settings compatibility and acceptance. Reuse the NOAA worker, product schema,
grid delivery, flight-level derivation, forecast selection, masks, and freshness
rules. No new data provider or particle dependency is needed.

Radar, METAR, TAF, SIGMET, routes, markers, and their controls keep their
existing behavior. Exclusivity applies to the two GFS layers only. Forecast
playback, surface weather, contours, route wind calculations, a retained barb
mode, and user-adjustable particle controls are outside scope.

This spec supersedes the independent wind/temperature switches and barb
presentation in [GFS Phase 2](2026-10-06-aviation-weather-phase-two.md). Its
data, provenance, resource, and lifecycle contracts continue to apply.

## Configuration and settings contract

Retain the existing `winds` and `temperature` booleans and shared level/horizon;
do not introduce a second persisted mode setting. Every effective settings
snapshot must resolve to exactly one of these modes:

| Mode        | `winds` | `temperature` | Globe                               |
| ----------- | ------- | ------------- | ----------------------------------- |
| Off         | false   | false         | No GFS drawing                      |
| Wind        | true    | false         | Wind-speed gradient and wind trails |
| Temperature | false   | true          | Temperature gradient only           |

Turning wind on sends `{winds: true, temperature: false}` in one save. Turning
temperature on sends the inverse in one save. Turning a switch off sends that
layer's false value and does not automatically enable the other layer. Add brief
helper text stating that only one GFS layer can be displayed at a time. Preserve
confirmed saves, disabled controls while saving, failure feedback, and revision
polling; failed saves keep the last confirmed selection.

Enforce the same rule under the existing server settings lock. A partial update
that enables either layer also disables its counterpart before committing one
revision. Explicitly requesting both true is invalid and returns the existing
validation-error response without changing settings or creating demand. Updates
to unrelated preferences preserve the current GFS mode. Concurrent saves are
serialized; the final committed revision wins and never contains both true.

For older saved files containing both true, normalize to wind enabled and
temperature disabled. The writable settings owner persists that repair
atomically with one revision increment; subsequent reads are idempotent.
Read-only worker readers apply the same effective precedence without writing.
Perform repair through the existing settings/bridge ownership so changed
revisions invalidate old demand before acknowledgement. Missing GFS fields
retain their existing default-off meaning; corrupt files retain the existing
failure behavior.

The frontend also resolves legacy both-true snapshots to wind only before
controller admission, drawing, and legend selection. This protects initial loads
and mixed-version rollouts from overlapping GFS drawings. It does not silently
save preferences from Overview. A switch changes the mode, not the saved level
or forecast horizon.

## Wind gradient and legend

Sample physical U and V with the existing geographic interpolation and shared
mask. Calculate unrounded speed as `hypot(U, V) * 1.9438444924406` knots.
Interpolate the vector components before calculating magnitude, rather than
interpolating precomputed scalar speeds. This keeps CPU, shader, and particle
samples consistent where neighboring vectors oppose each other.

Use a fixed global scale, independent of camera position, forecast, altitude, or
observed extrema. Proposed sRGB stops are:

| Wind speed (kt) | Color  | Hex       |
| --------------- | ------ | --------- |
| 0               | Blue   | `#1d4ed8` |
| 25              | Cyan   | `#06b6d4` |
| 50              | Green  | `#22c55e` |
| 75              | Yellow | `#eab308` |
| 100             | Orange | `#f97316` |
| 125             | Red    | `#ef4444` |
| 150 and above   | Purple | `#a855f7` |

Interpolate linearly in sRGB between stops and saturate only the displayed color
above 150 kt. Do not clamp the underlying wind values or particle sampling to
the color-scale endpoint. Start with opacity 0.45, matching the temperature
renderer. Keep rendering independent of day/night terrain lighting and below
operational markers. Invalid or below-terrain cells are transparent unknown
regions, never colored as calm. Valid zero wind receives the zero-speed color.

Replace the barb icon/key with a gradient labeled **Wind speed · kt**, showing
the same numeric stops and a **150+** endpoint. Renderer and legend consume one
palette definition so they cannot drift. Fit the labels without overlap at
desktop, fullscreen, and mobile sizes; accessible text states the range and
units. Keep current NOAA GFS, level, horizon, time, freshness, and attribution
presentation. Show only the admitted mode's key. Loading or unavailable data
must not create a legend that implies a visible data layer.

Temperature retains its existing palette, °C key, and rendering semantics. It
does not construct, retain, or update wind-particle resources.

## Particle behavior

Use a bounded set of thin, light trails above the wind gradient, following the
admitted U/V field on the globe. Unlike meteorological barbs, which point toward
the source of the wind, particles move **toward** the direction of flow:
positive U moves east and positive V moves north. Sample the field throughout
motion so trails follow local changes in direction rather than straight
screen-space lines.

Advance positions in the globe's local tangent frame and renormalize to its
surface, avoiding a longitude update that divides by `cos(latitude)` near the
poles. Wrap the longitude seam continuously. Trails lie slightly above the
gradient and remain depth-tested so the far side is hidden; they must not draw
chords through the Earth or intercept globe/feature picking.

Use one visual time multiplier for all particles so higher local speed produces
proportionally faster movement. The proposed initial multiplier is 12,000 model
seconds of motion per animation second. This illustrates one model snapshot,
rather than a real-time parcel trajectory or forecast playback. Do not advance
forecast time, change model identity, or imply a physical travel-time
measurement. Use animation delta time, cap a single integration step at 50 ms,
and discard suspended time instead of jumping forward on resume.

Proposed hard caps are 2,000 particles and 12 retained trail samples per
particle, sampled at 30 Hz with staggered lifetimes of at most six seconds. Use
elapsed time for trail sampling so length does not depend on display frame rate.
Seed across the globe with approximately equal area, independently of wind
speed. Resample or retire a particle before it enters invalid data; never bridge
a masked gap with a trail. Zero wind produces no motion, and no minimum-speed
floor may invent flow. Expired particles respawn with cleared history so respawn
never draws a long connecting streak. Continuous fading should avoid
synchronized pulses.

Respect `prefers-reduced-motion`: retain the wind gradient and key, with
particles disabled. A preference change takes effect without fetching a new
generation. The ordinary wind toggle controls both wind rendering elements;
there is no independent particles toggle and no particles over temperature.

## Ownership, lifecycle, and performance

Keep ownership with the current GFS controller: the admitted drawing owns its
mesh, textures, particle buffers, material, update function, and disposal.
Attach particle updates through the existing React Three Fiber frame loop; do
not add a separate animation timer or update React state per particle/frame.
Drawing construction and animation should be separate focused modules so the
existing large grid renderer does not grow into one combined implementation
file.

A settings mode/level/horizon change removes the old incompatible drawing before
admitting the replacement. A refreshed compatible generation swaps as a complete
unit with cleared trails; never mix its colors with another generation's flow.
Disabling wind, selecting temperature, hiding the display, going offline,
expiry, or unmounting stops updates and releases particle resources through the
existing lifecycle. Re-entry requires the current confirmed settings and an
eligible grid. Stale-but-eligible data follows the current explicit stale
status; animation never renews its freshness or expiry.

Preallocate buffers and reuse them during animation. Bound respawn attempts and
sampling work even when the entire grid is masked. Retain the shared optional
weather allowance: 32 MiB decoded/geometry, 16 MiB GPU, and 16 MiB encoded, with
at most four concurrent weather fetch/decode operations. Account for conversion
scratch, grid leases, geometry, history, materials, and old-plus-candidate
peaks. No new particle allowance may consume radar's reserved resources.

Reject an unadmittable candidate through the existing unavailable behavior
rather than publish a partially allocated drawing. Failure in particle
construction must release all acquired resources and keep the rest of Overview
usable. Measure frame/update time, draw calls, allocation peaks, and core globe
responsiveness against the barb baseline using the same camera, grid, overlays,
viewport, and renderer. The proposed hardware acceptance gates at the full
particle cap are p95 particle-update CPU time at most 4 ms and p95 total frame
duration at most 1.2 times the same-condition barb baseline. The implementation
plan must name the hardware benchmark environment, camera/overlay fixtures,
warmup, and capture duration before implementation. Software-rendered browser
evidence validates appearance and correctness separately; absent hardware
measurements leave the hardware performance gate unverified.

## Acceptance requirements

Automated checks and rendered-browser evidence must demonstrate:

1. Atomic wind/temperature switching, both-off behavior, failed saves, partial
   API saves, rejection of both-true requests, concurrent updates, legacy
   repair, and consistent revisions across two browser contexts.
2. Independent reference agreement for knots, east/north orientation, signed U/V
   sampling, opposing vectors, valid zero, missing/terrain masks, seam, poles,
   and color interpolation/saturation. GPU readback validates the actual wind
   shader against CPU/reference values, not just shader text.
3. Particles moving with the local flow at speed-dependent rates, equivalent
   elapsed-time behavior across frame rates within numerical tolerance, bounded
   long-frame behavior, cleared respawns, masked-gap handling, and reduced
   motion.
4. Wind gradient, trails, and matching legend through production Nginx at
   desktop, fullscreen, and mobile sizes; readable routes/markers; usable globe
   gestures and picking; and no particles or wind key while temperature is
   displayed.
5. Refresh, mode/selection switching, stale status, original expiry despite
   failed polling, hidden/offline recovery, worker/source failure, and unmount
   without retained update callbacks or leaked buffers/reservations.
6. Shared resource peaks during replacements, fully masked fields, repeated mode
   switching, and simultaneous radar/bulletin overlays, plus the performance
   comparison and unchanged core telemetry/health and existing weather behavior.

Run meaningful focused tests, the frontend suite, production build, lint, and
applicable settings/bridge backend tests. Production/browser acceptance uses an
isolated clean candidate SHA, the repository's established GFS fixtures and
acceptance tooling, and scoped cleanup of all task-owned runtime resources.
Update old barb-specific proof expectations to wind-field/trail expectations; do
not weaken numeric, resource, provenance, or lifecycle checks to accommodate the
new presentation.

## Review and handoff

Review the exclusive selection behavior, proposed knots palette, legacy wind
precedence, and particle presentation together. After this spec is approved,
write the implementation plan with the exact file map, settings migration and
bridge ownership, renderer/update interface, numeric fixtures, benchmark gates,
and production-browser acceptance commands. Review that plan before selecting
its execution method or making application changes.
