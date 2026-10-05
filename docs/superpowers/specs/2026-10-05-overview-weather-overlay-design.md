# Overview precipitation radar overlay design

## Intent and approval

Add current precipitation radar to the native Overview globe so viewers can see
weather context while monitoring a mission. The layer starts off, updates
automatically when enabled, and preserves core dashboard availability.

The user approved the conversational design and this written specification on
2026-10-05, including a shared setting controlled only from Configuration.
Implementation awaits review of the plan and selection of an execution method.
This specification defines the first increment of
[issue 144](https://github.com/bcl1713/starlink-dashboard/issues/144).

## Scope and existing behavior

Configuration owns the weather control; Overview remains a display. Include
latest observed precipitation, radar coverage, frame age, linked attribution,
automatic refresh, bounded retention, and explicit failure states.

Forecasting, historical animation, cloud cover, SIGMETs, G-AIRMETs, METARs,
flight-level products, route changes, adjustable resolution, opacity controls,
and weather interactions on Overview are outside this increment. Aviation
follow-ups remain separate work.

The existing globe uses Three.js through React Three Fiber. Its day and city
light textures, routes, aircraft, labels, camera behavior, and metrics remain
intact. Grafana was removed in PR 277. Retire the obsolete RainViewer redirect
route and synchronous service; the old tile route returns 404 and cannot
initiate provider requests.

## Configuration and propagation

Add a Weather section to Configuration's Overview tab, with an accessible switch
named **Precipitation radar**. Its description explains that it shows
automatically updated precipitation on all Overview displays. Show normal
loading, saving, confirmed-save, and save-error feedback. Do not add a weather
button, settings link, retry control, or interactive popup to Overview.

Persist enabled and revision in data/settings/overview-weather.json using the
existing locked, validated, atomic settings-store pattern. Defaults are false
and zero. The setting is installation-wide and survives browser reloads, backend
restarts, and mission changes. Only an explicit saved change enables it. Reject
unknown fields, non-boolean enabled values, and empty updates. Return the full
confirmed state; save failure preserves the previous state. Revision advances
only when enabled changes; a save of the existing value is idempotent.

Serialize browser saves and cancel obsolete reads before publishing a confirmed
response. Accept only nondecreasing revisions. Configuration and every visible
Overview read settings every five seconds and on visibility or network recovery.
Hidden documents pause polling. A successful settings response remains trusted
for at most 15 seconds; after that, hide weather and stop acquisition until a
fresh confirmed enabled setting arrives.

Successful disable immediately fences and cancels backend weather acquisition
before the PUT completes. Visible Overview windows remove imagery by their next
successful settings read, normally within five seconds. A newer revision or
local load generation prevents late responses from restoring disabled imagery.
Re-enabling starts a new generation; changing camera or mission does not.

## Provider contract

Use RainViewer's latest eligible observed frame from radar.past, never nowcast.
The [Weather Maps API](https://www.rainviewer.com/api/weather-maps-api.html)
documents two hours of frames at ten-minute intervals, XYZ tiles, maximum zoom
7, and a coverage mask whose transparent pixels indicate coverage. Frame time is
generation time and can combine observations of different ages.

The [transition summary](https://www.rainviewer.com/api/transition-faq.html)
documents the removal of nowcast and satellite IR, Universal Blue as the
remaining color scheme, and 100 requests per IP per minute. Use that narrower
contract despite conflicting general FAQ text. The
[API terms](https://www.rainviewer.com/api.html) describe personal and
educational use and require visible linked attribution. Installation use must
fit those terms or an applicable provider agreement; no external contact is part
of this implementation.

Fix tile size at 512 pixels, zoom at 2, color at 2, and options at 1_1. Each
frame is a four-by-four world atlas, 2048 pixels square. This is broad
geographic context; zooming does not request sharper detail. Coverage uses the
documented coverage path with color/options 0/0_0 and the same tile grid.

Validate metadata before caching: bounded object and list sizes, exact HTTPS
provider host, integral nonnegative timestamps excluding booleans, and numeric
frame paths matching their timestamp. Reject future frames beyond a 60-second
clock tolerance; only frames younger than 60 minutes are eligible. Select the
newest eligible observed frame and never regress a retained frame's time.
Recheck time eligibility on cached reads and clamp tolerated future frame age to
zero for display.

## API and component boundaries

| Endpoint                                                      | Contract                                               |
| ------------------------------------------------------------- | ------------------------------------------------------ |
| GET /api/overview-weather/settings                            | Confirmed enabled and revision; no provider access     |
| PUT /api/overview-weather/settings                            | Validated enabled update and confirmed state           |
| GET /api/overview-weather/frame                               | Frame metadata and application-relative tile templates |
| GET /api/overview-weather/radar/{frame}/{z}/{x}/{y}.png       | Buffered PNG for an exact admitted frame               |
| GET /api/overview-weather/coverage/{coverage}/{z}/{x}/{y}.png | Buffered PNG for the admitted coverage generation      |

The frame response contains state, settings_revision, generated_at_ms,
frame_time_ms, coverage_token, coverage_expires_at_ms, zoom, tile_size,
radar_tile_template, and coverage_tile_template. State is off, ready, or
unavailable. Off/unavailable have null frame/coverage values and templates.
Ready identifies one exact frame and coverage generation. Times are integral UTC
epoch milliseconds; the URL frame token is epoch seconds. Provider metadata is
never forwarded verbatim. Settings failure returns sanitized 503; invalid
updates return 422.

PNG routes accept only zoom 2 and coordinates 0 through 3. Radar tokens must
identify the latest or previous admitted eligible frame, with a two-frame
registry limit. Invalid coordinates return 400; unknown/expired frames
return 404. Disabled settings return 409 with no provider or cache-body access.
Unavailable provider data returns sanitized 503 and a bounded Retry-After.

Use a dedicated settings model/store, API router, application-owned weather
service, HTTPS transport, browser data hook, atlas loader, scene layer, and
Configuration section. Keep integration in OverviewPage small. No weather load
enters the base globe's texture loader or Suspense boundary. Configuration reads
and writes settings without acquiring radar or coverage.

Add a dedicated Nginx location with the ^~ /api/overview-weather/ prefix so PNG
requests reach the backend instead of the static-image regex. Retain normal
upstream disconnect propagation. Browser weather traffic stays on the
application origin without expanding CSP provider hosts.

## Acquisition and cache budgets

Acquire only in response to enabled viewers; startup, Configuration, and hidden
or disabled Overview views do not trigger upstream work. Check frame metadata
immediately on enable and every 300 seconds while visible. Refresh immediately
on visibility/reconnect recovery, subject to backend cache and failure cooldown.
Unchanged frame identity does not reload a valid atlas.

Backend metadata success cache lifetime is 300 seconds. Coverage generations use
the integral UTC day number as their token and expire at the next UTC day
boundary, at most 24 hours later. This is a cache version, not a provider
observation time. Admit only the current coverage token and remove the previous
generation from the cache. An enabled visible view checks for a new manifest on
coverage expiry; an expired mask cannot imply clear weather. Failure cooldown is
30 seconds per acquisition key and honors longer provider Retry-After values up
to 300 seconds. There are no immediate retry loops. Cache immutable frame PNGs
by frame and coordinates.

Coalesce identical requests with subscriber leases. Disconnect removes only that
subscriber. Cancel an exchange when its last subscriber leaves; a surviving
viewer keeps its own shared acquisition. Global disable and shutdown cancel all
weather work without cancelling telemetry or other services.

The current deployment runs one backend worker. Across all its viewers, cap
actual upstream HTTP attempts at 90 per rolling 60 seconds, with four active
exchanges and 32 pending unique acquisitions. Reject excess demand safely rather
than queueing indefinitely. Failed connection attempts and retries consume the
same budget. Multiple backend workers or installations sharing an egress IP need
an aggregate limiter before increasing deployment concurrency.

Limit cached PNGs to 48 entries and 64 MiB of compressed bytes, evicting by
recency and removing departed frame generations. Permit only two radar frames
and one coverage generation. Raster responses use immutable frame URLs with
Cache-Control private, max-age=600, immutable; coverage uses private,
max-age=300, must-revalidate, shortened to remaining coverage validity when
necessary. Settings and manifests use no-store.

Browser loads use four concurrent image fetches, a 45-second whole-load
deadline, and one pending frame generation. A newer load aborts the older
pending load. Stop on failure and release its partial images. Do not
automatically retry unchanged failed imagery before the next scheduled check or
recovery event.

## Stream ownership and network controls

The earlier
[rejection evidence](https://github.com/bcl1713/starlink-dashboard/pull/143#issuecomment-5532365252)
identified double closure on shutdown and missing actual ASGI disconnect
handling. Its implementation is reference material, not a passing baseline.

Each exchange has one stream owner. The exchange's cleanup closes and waits for
its writer once. Shutdown marks the service closed, cancels owned tasks, and
awaits their cleanup; it does not independently close the same writers.
Concurrent close callers share completion. Stream reaping has a one-second bound
after cancellation; no new exchange starts during shutdown.

Observe actual ASGI http.disconnect while an API operation waits for
acquisition. Cancel/release that request's lease and remove its watcher in every
completion, exception, timeout, and cancellation path. Buffered responses have
no provider stream whose lifetime depends on browser response streaming.

Start one five-second aggregate exchange deadline before admission waits and
DNS. It covers resolution, numeric-IP connection, TLS, headers, and every body
read, without resetting per chunk or candidate. Allow only the fixed RainViewer
HTTPS hosts and reconstructed paths. Resolve and validate public addresses, dial
the selected numeric address, and preserve original-host Host, SNI, and
certificate verification. Reject redirects, unexpected status/type/encoding,
conflicting framing, malformed or oversized headers, and truncated or oversized
bodies.

Use protocol-aware HTTP framing, including chunked bodies. Bound headers to 32
KiB, metadata to 128 KiB, and PNG bodies to 2 MiB. Require PNG signature and
512-by-512 IHDR dimensions before delivery; the browser must also successfully
decode each tile. Return no upstream URL, internal IP, provider body, or
exception details in application errors. Acceptance fixtures never relax
production address, TLS, or size validation.

## Globe rendering and ownership

Compose the atlas offscreen, preserving provider tile order and alpha. Sample it
using longitude and Web Mercator latitude derived from the same local sphere
coordinates as globePosition. Handle texture orientation, the antimeridian, tile
seams, and the Mercator latitude limit explicitly. Beyond that limit, render no
precipitation and identify absent coverage.

Draw radar as an independent transparent surface with depth testing and no depth
writes, ordered before route and marker overlays. Its material preserves
precipitation visibility on the night side. Do not shift route or aircraft
coordinates to accommodate weather or intercept globe pointer events.
Independently verify the geographic and draw-order contracts in rendered tests.

Initial display requires all 16 radar tiles and a complete, unexpired coverage
atlas. Swap only a fully decoded new radar atlas; never display tiles from two
frames as one frame. Failed or superseded loads leave only an eligible
previously complete frame. Refresh coverage atomically under the same
completeness rule.

Use subtle hatching for uncovered pixels and a passive legend that distinguishes
precipitation from absent coverage. Clear pixels within a valid coverage mask
mean no displayed radar return, not a guarantee of clear weather. Show linked
RainViewer attribution, frame UTC time, age, and a compact status only while the
layer is enabled. The attribution is a source link, not a weather control.

Cap active and pending GPU atlas storage at 48 MiB: one displayed radar atlas,
one pending radar atlas, and one coverage atlas, without mipmaps. Serialize
coverage GPU replacement after committing or cancelling any pending radar
upload: only one radar texture remains while old and new coverage textures
briefly coexist. Close decoded image bitmaps and dispose textures, canvases,
timers, and requests on supersession, disable, or unmount.

## Freshness and failure behavior

Use real UTC time for weather, independently of mission simulation or replay.
Frame age from zero through 20 minutes is current; greater than 20 and less than
60 minutes is stale. At 60 minutes remove imagery. A refresh failure marks
retained imagery stale immediately, even if its age is younger than 20 minutes.
Recovery restores current only after successful validation. Repeated failures,
unchanged responses, remounts, and camera changes never extend original expiry.

Initial load shows loading without blanking the base globe. A failed initial
load, expired frame, unavailable settings, or expired/missing coverage shows
weather unavailable and no radar imagery. A frame refresh may retain a complete
unexpired frame with an explicit stale status. Off removes weather status,
imagery, and provider acquisition. Core rendering, telemetry, controls, and
metrics remain usable in every weather state, including runtime initialization
failure. Weather service construction performs no provider access.

## Verification and delivery

Use test-driven implementation after written-spec and plan approval. Provider
fixtures make failures, time, cancellation, and image content deterministic.
Cover default off, saved persistence, failed saves, two open windows, confirmed
disable, late responses, unchanged frames, atomic replacement, stale/expiry
boundaries, coverage gaps, future/invalid metadata, retries, budgets, and
cleanup.

Exercise the production stream owner with fake numeric-IP TLS streams and actual
route-level ASGI disconnect events. Prove exact-once closure on request cancel,
global disable, shutdown, repeated close, and completion races, plus sibling
survival. Test pre-DNS deadlines, slow body chunks, chunked framing, malicious
host/path data, private addresses, TLS verification, invalid PNG dimensions,
oversized/truncated responses, and bounded cache/task ownership.

Rendered acceptance uses fresh production frontend/backend images at the exact
candidate SHA, actual Nginx proxy routes, and isolated simulation resources. Use
fixtures at provider transport boundaries without bypassing production
validation; identify browser-intercepted controls separately. Verify pixels
against independent geographic fixture landmarks at equator, mid/high latitudes,
tile boundaries, and both sides of the antimeridian. Exercise rotation, zoom,
follow, reset, fullscreen, mobile layout, and day/night views. A Configuration
save must change an already-open Overview without reload or added controls.

Retain screenshots, request/budget counts, resource-disposal evidence, and core
rendering/telemetry continuity during provider failures. Require focused suites,
frontend build/lint, applicable CI, fresh specification and quality/security
review, and documented operator behavior before integration through dev.
The user approved the written specification and implementation plan and selected
native execution on 2026-10-05. Do not close issue 144 until its implementation
acceptance passes.
