# Responsive Overview Layout

Overview renders one clock group, one Three.js Canvas, one
arrival/planning/legend group and five uPlot instances. Layout changes move the
same DOM tree. Shared queries and source derivation remain unchanged; no mobile
copies or extra polling are introduced.

## Available space and scrolling

`useOverviewLayout` observes the bounded `.app-route-content` shell, not the
Overview's growing scroll content. ResizeObserver tracks the stage and overlay
sizes; root font changes and legend disclosure also schedule measurement. Mode
is exposed through `data-layout` for CSS and browser verification.

- Desktop requires at least `max(1500px, 93.75rem)` width and
  `max(1012px, 63.25rem)` height. Its five-card rail remains 440px wide.
  Measured panel overflow, overlap, or insufficient clear map height selects
  stacked page flow, latched until viewport/root changes.
- Landscape requires at least 800px usable width, a readable 210–240px rail,
  560px map width, 220px stage height and 120px height clear of arrival content.
  Readability minima scale upward with enlarged root text. Very tall viewports
  use stacked or desktop composition rather than the landscape strip.
- Other sizes use stacked flow. The shell owns vertical page scrolling; metric
  cards have no nested scroller. In landscape, only the metrics rail scrolls.
- When overlays cannot fit, panels move below a 360px renderer. Expanded legend,
  root font over 20px or measured oversized content triggers this escape. Within
  a settled viewport, the flow decision stays stable until a resize/root change;
  loading-induced decisions reset when initial queries settle.

Semantic content keys exclude changing observation timestamps/countdowns.
Observed size changes still update the reserved rectangle. This avoids feedback
between reflowed panel height and the decision to reflow it. Safe-area insets
and `dvh` are used with a `vh` fallback. Actual CSS dimensions select layout;
system scaling, browser zoom and DPR are recorded separately in acceptance
evidence.

## Camera and input

A controller within the existing Canvas owns one Drei CameraControls instance.
Default responsive input allows browser scrolling. Landscape wheel events on
stage/gaps forward to the rail only when it can scroll; rail events stay native,
and Ctrl/Meta wheel is untouched. Explore enables gestures only within the
globe. Exit, Escape, blur and mode changes release gesture state and preserve
the pose. Desktop retains deliberate orbit/zoom without an Explore control.
Reset and configured-follow status remain available beneath the fullscreen
control.

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

Desktop fullscreen keeps the globe centered on the screen when that preserves a
useful route angle and scale. A panel-aware projection offset is used when
forcing exact screen centering would make the route small or push the aircraft
toward the horizon. The route is centered in the opening to the right of the
metrics, below the upper cards and above the legend. Other views use the same
measured panel-aware framing.

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
[implementation plan](../superpowers/plans/2026-10-02-overview-responsive-mobile.md)
and
[source contract](../superpowers/plans/2026-10-02-overview-responsive-mobile-source-contract.md).
Browser tests drive wheel, touch and interrupted pointers; read-only renderer
observation checks pose, while DOM handles verify retained renderer/plot
identity. Software emulation cannot establish physical system scaling or device
gestures.
