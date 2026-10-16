# Responsive Overview Layout

Overview renders one clock group, one Three.js Canvas, one
arrival/planning/legend group and up to five uPlot instances. Layout changes
move the same DOM tree. Shared queries and source derivation remain unchanged;
no mobile copies or extra polling are introduced.

## Available space and scrolling

The Three.js canvas always covers the complete Overview viewport behind all
translucent panels, including the scrolling sidebar. It remains fixed while
panels scroll. The globe's camera, rather than the canvas, is positioned and
scaled into the open area left by those panels.

`useOverviewLayout` observes the bounded `.app-route-content` shell, the canvas,
and an invisible `.overview-map-opening` layout area. Available width, height
and root font size choose composition; legend disclosure and changing feed
content cannot switch modes. Mode is exposed through `data-layout` for browser
verification.

- Desktop requires at least 1500 × 1012 CSS pixels at the default root font
  size. It retains the full-bleed globe, clocks above, metrics at left and
  controls/legend at right. Optional status/legend content has bounded
  scrolling.
- Windowed desktop (`landscape`) requires at least 1100 × 500 CSS pixels. Clocks
  stay above the camera opening and arrival below it. A single 240–320px right
  sidebar contains controls, legend and metrics and owns their scrolling. The
  canvas continues behind the sidebar.
- Portrait and taller narrow windows place clocks at the top, the camera opening
  below them, then arrival information and a bounded lower sidebar. Only that
  sidebar scrolls; neither the canvas nor the clock/arrival groups scroll out of
  view. Unusually long arrival content scrolls within its bounded band so short
  screens retain an opening for the globe.
- Mobile landscape (at least 640px wide and at most 600px tall) places clocks,
  the opening and arrival in the left column, with a scrolling right column for
  all controls and metrics. The canvas fills both columns. Fullscreen releases
  navigation height to the dashboard.

Explore, Reset and Fullscreen share one toolbar with equal-width, 44px-high
buttons. Short visible labels and a fullscreen icon keep narrow toolbars from
wrapping into orphaned rows; full accessible names and tooltips remain. Hiding
the fullscreen action or optional panel groups releases their space.

The renderer and plots stay mounted across composition changes. Safe-area insets
and dynamic viewport units account for mobile browser chrome. Navigation uses a
compact menu below 1024px to avoid crowding windowed headers.

For non-desktop compositions, the camera's safe rectangle comes from the
opening's measured bounds relative to the full canvas. Desktop derives the
opening from actual visible panel bounds. Fullscreen compares the central
opening with the wider gap between right-side controls and legend, choosing
the larger limiting dimension to avoid excessive zoom-out into a shallow gap.
Automatic and Reset/route-overview framing respond to changes in
position and size, including small resizes. Existing smooth rotation,
dolly/projection transitions and manual-intent preservation remain intact.

Label placement clips reserved panel rectangles to their visible scrollports;
scrolled-off metric or legend content cannot incorrectly reserve the map
opening. Legend disclosure and sidebar scrolling leave the canvas and opening
stationary.

Panels use a blue glass tint at 35% opacity (45% without backdrop-filter
support)
and a light 3px blur so the globe remains visible behind the interface.

## Visibility and configuration

Configuration keeps the existing tab and card style, with settings grouped by
purpose. Overview contains panel visibility, shared history, camera behavior,
route/POI layers, borders and clock definitions. Network Traffic contains link
layers, configured satellite/GEP markers, satellite selection and individual
metric panels. Aircraft Traffic contains the own-aircraft marker and flown trail
alongside ADS-B selection. Weather contains radar, station reports, advisories
and GFS layers. Displays, Terminal Controls and Diagnostics retain their roles.

Shared visibility is saved through `/api/overview-links/settings` and reaches
open Overview displays through the existing refresh cadence. Additive panel and
core-layer preferences default on; older saved files preserve their existing
appearance. Each graph can be hidden independently, and hiding all graphs
removes the metrics group while retaining controls in the sidebar. Hidden
clocks, arrival information and metrics release their layout space. Visibility
changes recheck panel fit without waiting for a viewport resize. Layer switches
hide their markers, labels and legend keys while keeping source data available
for camera behavior and other independent layers.

The Overview display identity is a small footer below the legend, visible even
when its compact disclosure is closed. With the legend hidden, the same quiet
identity remains below the map controls so Configuration can still identify the
display. Fullscreen and camera controls stay reachable.

## Camera and input

A controller within the existing Canvas owns one Drei CameraControls instance.
Default responsive input allows native sidebar scrolling. Windowed-desktop wheel
events on stage/gaps forward to the sidebar only when it can scroll; sidebar
events stay native, and Ctrl/Meta wheel is untouched. Explore enables gestures
only within the globe. Exit, Escape, blur and mode changes release gesture state
and preserve the pose. Desktop retains deliberate orbit/zoom without an Explore
control. Reset, fullscreen and configured-follow status remain reachable in the
controls group.

Initial automatic framing prefers valid projected route points. Its orientation
uses a containing spherical cap determined by route extremes, so densely sampled
waypoints and dateline crossings do not bias the overview angle. Perspective
bounds center the route inside the measured area clear of panels. The distance
also keeps visible-hemisphere route points ahead of Earth's surface. Without a
route, framing uses valid map aircraft or the existing orientation. The
45-degree FOV, 3–28 orbit limits and scene geometry remain unchanged. Global
routes can have far-side occlusion; fitting does not flatten them.

If initial route loading fails, the first recovered usable route gets one eased
fit while intent remains automatic. Manual intent prevents that recovery fit.
Default position updates leave the initial automatic camera still. Switching to
a different usable route refreshes its automatic framing; equivalent route polls
preserve the pose. Reset enters **Route overview** mode. It fits the whole route
and fresh aircraft position when they fit at a readable scale. Otherwise it fits
the largest useful contiguous section around the aircraft, reserving twice as
much route distance ahead as behind when the leg allows it. The route's rendered
geometry is unchanged; distant portions remain on the far side of the globe.

Route overview reserves space around the aircraft and keeps it clear of the
globe's horizon. It gently reframes when the aircraft approaches those limits,
using the destination camera pose and different fitting/update margins to avoid
chasing every position poll or an unfinished transition. Stale/error/missing
positions do not drive camera updates. Manual gestures pause route overview
until Reset. Measured layout and fullscreen changes still refresh automatic
framing, including the projection scaling used by small resizes. Continuous
following is opt-in through Configuration, using a browser-local preference with
default false and storage-failure feedback. Following uses only the same map
status coordinates and timestamp; stale/error/missing sources pause it.
Arrival/GPS provenance remains independently derived.

Desktop fullscreen prefers a screen-centered globe when that preserves a useful
route angle and scale. A panel-aware projection offset is used when forcing
exact screen centering would make the route small or push the aircraft toward
the horizon. The route is centered in the opening to the right of the metrics,
below the upper cards and above the legend. Other views use the same measured
panel-aware framing.

Automatic route framing and following use camera-controls damping with a
1.2-second smoothing parameter and a 1.5 scene-units/second dolly speed cap.
This parameter controls damping, not animation duration. The control bounds the
angular damping error vector to cap rotation at 10 degrees/second. Rotation uses
the nearest azimuth, including across the dateline. One control owns both user
gestures and transitions. Equivalent status polls leave the current move
running, and changing a follow target retains damping velocity. Measured
projection offsets use the same critically damped equation, capped at 0.08
viewport fractions/second per axis; layout and fullscreen changes ease instead
of jumping. Equivalent polls and resizing preserve in-progress projection
motion. Route-fit math determines direction and distance. Following uses a
closer distance of 4.5 scene units around the radius-two globe, keeping the
aircraft in the panel-safe opening; it does not fit the entire globe. Fullscreen
follows with Earth centered. Hidden tabs pause updates; the first delta after a
visibility change is discarded to prevent replaying time spent hidden. Manual
input cancels the transition immediately; manual intent preserves
position/quaternion/target/zoom through resizing. Projection aspect updates with
the renderer. Reduced motion finishes transitions discretely and removes
optional scene animation and plot transform transitions. uPlot data uploads
remain tied to accepted data and measured size changes.

POI packing uses renderer-local bounds and reserved overlay rectangles. It
remeasures after meaningful layout or settled camera changes and retains
complete accessible name lists when visual labels cannot fit.

## Verification

See the
[implementation plan](../superpowers/plans/2026-10-02-overview-responsive-
mobile.md)
and
[source contract](../superpowers/plans/2026-10-02-overview-responsive-mobile-
source-contract.md).
Browser tests drive wheel, touch and interrupted pointers; read-only renderer
observation checks pose, while DOM handles verify retained renderer/plot
identity. Software emulation cannot establish physical system scaling or device
gestures.
