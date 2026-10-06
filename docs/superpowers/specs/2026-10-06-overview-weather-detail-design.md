# Overview weather detail and opacity design

## Intent and decisions

Make native Overview precipitation radar presentable when viewers zoom into a
region, while reducing its visual weight so terrain and operational overlays
remain readable. This follows [issue 288][issue] and the completed first
increment in [the weather overlay design][baseline].

The user agreed to target 1080p desktop and fullscreen presentations plus mobile
across the existing camera range. The user also agreed to preserve current
request and memory limits, retaining coarse weather during rapid movement or
heavy multi-viewer demand. This specification records the recommended design for
review; implementation has not started.

The user subsequently asked to consider different providers and maps generated
from raw data, and confirmed that international coverage must remain. The
[provider assessment][assessment] compares managed services, open composites and
existing self-hosted ingestion software. The user chose to avoid ongoing API
fees, so compare free RainViewer delivery with bounded raw-composite generation;
paid services are excluded from the implementation path. Provider selection is
provisional; the RainViewer-specific contracts and allocation scheme below
describe the current implementation candidate, not a restriction against a
better source.

Use a lower fixed radar opacity, selected through rendered comparisons. Keep the
existing optional, default-off setting in Configuration. Add no opacity slider,
weather interaction, manual refresh, or resolution preference.

## Provider contract and alternatives

Checked on 2026-10-06: RainViewer's [Weather Maps API][provider] documents
maximum zoom 7, 256/512-pixel tiles, observed frames, and coverage masks. Its
[transition summary][transition] specifies 100 requests per IP per minute.
Continue using 512-pixel tiles, the existing admitted opaque radar path,
Universal Blue parameters, and verified same-origin backend acquisition.

That is the baseline candidate pending source comparison. Compare actual
higher-zoom RainViewer imagery with tiles generated from NOAA MRMS and OPERA
snapshots. Inspect LibreWXR as prior work; its full deployment defaults are not
assumed to fit the dashboard's hardware. A replacement requires demonstrated
added detail, international coverage, truthful missing-data masks, immutable
frame identity, approved operating cost and bounded server resources. Do not
adopt model or satellite filling without an explicit product decision.

The raw-data comparison starts with one or two immutable regional snapshots,
observed precipitation and masks only, without a continuous ingest service.
Record download size, decode and render latency, server RAM, browser request
counts and 1080p image quality. Adopt self-hosted generation only if the
evidence shows a worthwhile benefit and its separate CPU/RAM/disk limits are
agreed. Preserve remaining international observed coverage through a fully
specified source plan; MRMS and OPERA alone are not a worldwide replacement.

A fixed zoom-3 world atlas needs 64 radar and 64 coverage tiles. Its two
4096-square RGBA textures alone need 128 MiB, versus the current 48 MiB GPU
ceiling. Initial acquisition also exceeds the 90-attempt rolling-minute
application budget. A larger fixed world atlas is therefore rejected.

Increasing texture dimensions or changing interpolation for the zoom-2 atlas
does not add provider detail. Retain that atlas as a complete fallback, and
fetch actual higher-zoom tiles for visible regions. A larger unbounded detail
cache is rejected because the user chose to preserve existing limits.

## Architecture and interfaces

Keep the existing complete zoom-2 radar and coverage atlases, frame controller,
settings ownership, and freshness clock as the foundation. Add four focused
frontend components:

- A pure tile selector consumes the camera matrices, globe transform, viewport,
  and rendered pixel dimensions. It returns a bounded, stable list of XYZ tiles.
- A camera observer inside the existing React Three Fiber canvas supplies
  snapshots without changing native rotation, zoom, follow, or reset behavior.
- A detail owner loads matched radar/coverage pairs, owns cancellation and
  cooldowns, and retains a bounded decoded cache for the displayed frame.
- A detail texture owner packs those pairs into fixed slots and supplies their
  geographic bounds to the existing weather shader.

The existing weather controller remains authoritative for whether acquisition is
allowed and which complete frame is displayed. Detail loading cannot extend a
frame's lifetime, confirm settings, advance the frame clock, or restore an
expired layer. Connect detail ownership to the same activity and generation
fences rather than creating independent settings polling.

Keep source adaptation on the backend and validate a single normalized browser
contract for the selected source. Advertise its tile dimensions, zoom limits,
frame identity, provenance and coverage encoding explicitly. The following
512-pixel paired-atlas calculations apply to the RainViewer candidate. If the
chosen source supplies 256-pixel tiles or packed precipitation/coverage values,
revise both the allocation proof and strict contracts before implementation.
Keep the 48 MiB GPU ceiling; a source change does not authorize higher limits.

The [aviation-weather follow-on direction][aviation-direction] reinforces this
backend normalization boundary. Keep rendering independent of provider URL
grammars and raw formats, with truthful observation time, provenance and
coverage. This issue continues to display observed precipitation only; METAR,
SIGMET, satellite, model and flight-level layers need their own designs.

The manifest keeps `zoom: 2` as the fallback level and adds `max_zoom: 7`.
Update backend and frontend strict contracts together. Radar and coverage routes
accept canonical integer XYZ coordinates for zooms 2 through 7, with
`0 <= x,y < 2**z`. The provider transport independently validates the expanded
path grammar and coordinate bounds before DNS resolution or dialing. Preserve
the admitted frame identifiers, coverage generation, HTTPS host allowlist,
public IP pinning, TLS verification, payload validation, and cache keys.

## Camera selection and stability

Use the actual camera projection, including its view offset, and globe-space
visibility. Derive desired zoom from projected texel size in the drawing buffer;
provider zoom is bounded by 7. Do not derive zoom solely from camera distance or
use a separate weather camera.

Prefer visible tiles that occupy substantial screen area. Avoid refining the
hidden hemisphere and heavily foreshortened horizon. Estimate the visible
footprint conservatively with sphere intersections and projected tile bounds;
include antimeridian wrapping and the Web Mercator latitude limit explicitly.

Select at most eight higher-detail tile pairs. Choose the finest level that fits
the visible footprint when possible. When the footprint cannot fit, use a
coarser level and prioritize the largest visible regions; the complete fallback
continues to cover the remainder. Zoom 7 is a supported ceiling, not a promise
that every view uses it. At 1080p, typical regional views must visibly improve
over the current zoom-2 imagery within these bounds.

Observe camera changes at most four times per second. Wait for 400 ms of stable
tile demand before starting a changed selection. Use a 20 percent projected
resolution hysteresis band when changing levels. Fetch only missing keys, keep
overlapping tiles during small movements, and avoid an abort/reload cycle when
the selected keys have not changed. Bounded pending selection replaces older
pending demand; it never becomes an unbounded history of camera positions.

## Detail loading and frame consistency

Every tile pair belongs to one settings revision, displayed radar timestamp,
coverage generation and expiry, and XYZ coordinate. Publish a slot only after
both images have decoded and passed dimension checks. Radar and coverage always
use the same geographic bounds and detail level.

While a detail pair is incomplete or unavailable, sample the complete coarse
pair. Keep eligible, already loaded detail when it still matches the displayed
frame and coverage generation. Obsolete completions close their bitmaps and
cannot overwrite newer slot mappings.

Update detail only for the frame actually being displayed, even while a newer
coarse frame is loading. A successful coarse refresh swaps the complete frame at
once, removes old detail in that same render commit, and starts refinement for
the replacement frame. Never retain old-frame detail over a new base frame. On
refresh failure, retain only the existing eligible frame and its eligible detail
under the established stale policy.

Use short opacity transitions for newly committed detail. Geographic edge
blending and slot gutters must avoid visible resolution boundaries and texture
bleeding. Where adjacent same-level detail is available, sample it continuously;
where it is absent, blend to the matching coarse pair. Blend premultiplied radar
colors and coverage-derived precipitation together. Coverage transitions must
conservatively retain hatching for absent or uncertain coverage; interpolation
must never turn missing coverage into an apparent clear-weather region.

## Requests, caches and memory

Preserve all existing backend maxima: 90 actual provider attempts per rolling
minute, four active exchanges, 32 pending acquisitions, and 48 cached PNGs with
a 64 MiB compressed-byte ceiling. These remain shared across viewers within the
supported single backend worker.

Within the existing 90-attempt budget, cap detail attempts at 30 per rolling
minute and detail exchanges at two. Count each numeric-address retry as an
attempt. Keep at least two exchange slots available to metadata and coarse
imagery, with coarse demand taking priority in admission. These are tighter
sub-limits, not increases to the overall budget. Coalesce identical detail keys
with existing subscriber leases and enforce the same failure cooldowns.

Across all browser weather work, retain four active fetch/decode operations;
detail may use at most two. Coarse refresh takes priority and cancels obsolete
detail work when necessary. Honor bounded `Retry-After` on detail failures;
avoid automatic immediate retry or retry on every camera observation. Retain the
existing 45-second load deadline and cancel superseded selection work.

GPU storage remains at most 48 MiB, with mipmaps disabled:

- Displayed coarse radar and coverage use 32 MiB.
- Two 2048-by-1024 RGBA detail atlases use 16 MiB total, packing eight matched
  pairs. Each 512-square slot has a one-pixel replicated gutter and a 510-square
  interior sampled from its higher-detail provider image.
- Slot bounds and validity use shader uniforms, without another GPU texture.
- Publish matched slot updates in place; do not allocate a second GPU detail
  atlas set. Clear slot validity before reusing a slot, then publish both images
  and their mapping together.
- Before a coarse GPU replacement allocates its pending texture, dispose the
  detail textures. Use the existing serialized coarse replacement order, whose
  peak remains 48 MiB. Recreate detail storage after replacement completes.

The two-pixel gutter allowance slightly resamples a higher-detail image; it is
not the source of the detail improvement. Evidence must demonstrate actual
higher-zoom acquisition and added geographic detail.

Bound browser-owned decoded imagery to 96 MiB: up to four coarse canvases use 64
MiB, two detail canvases use 16 MiB, eight decoded detail pairs use 16 MiB.
Decoded staging shares the eight-pair budget; evict an unneeded pair before
decoding its replacement. Active operations must reserve their bitmap storage
before decoding, releasing reservations and bitmaps on every exit path. Count
temporary decoded allocations against this ceiling; do not maintain a separate
unbounded image or offscreen-canvas cache. Compressed in-flight blobs remain
bounded by the existing four-operation limit and 2 MiB payload limit.

Hidden views, lost settings trust, disable, disconnect, navigation, and unmount
cancel detail acquisition and release its decoded and GPU resources. Preserve
the existing coarse retention and recovery semantics where applicable. Backend
disconnect releases only that subscriber; global disable and shutdown fence and
cancel all owned provider work.

## Opacity and failure behavior

Begin rendered comparison with radar alpha factors 0.35, 0.40 and 0.45 against
the current 0.72 baseline. Select one lower fixed default based on 1080p
desktop, fullscreen, mobile, day and night views with routes, aircraft, POIs,
borders, and labels present. Keep the coverage-hatching factor independent.

Detail acquisition failure leaves usable coarse imagery and does not by itself
mark a successfully confirmed complete frame stale. Preserve existing frame
refresh failure, UTC age, 20-minute stale threshold, 60-minute expiry, midnight
coverage expiry, settings trust, passive status and linked attribution rules.
Keep core globe, mission controls and telemetry usable during provider failure.

## Verification and acceptance

Add deterministic regressions for:

- Backend zoom and coordinate acceptance/rejection, canonical provider paths,
  pinned transport, admitted frames, coalescing, detail sub-budgets and
  priority.
- Camera projection and view offsets, viewport size, level hysteresis, bounded
  selection, rotation, follow/reset, antimeridian and high-latitude visibility.
- Paired publication, fallback, adjacency and edge transitions, frame refresh,
  stale retention, midnight and age expiry, late completions and cancellation.
- CPU reservations and GPU allocation/disposal ordering at their peak limits.
- Hidden views, disable, disconnect, navigation, shutdown and StrictMode
  ownership, including timers, bitmaps, canvases, requests and textures.

Extend the existing weather acceptance runner to use an issue-288-specific
Compose project, loopback ports, ownership record and bounded wall-clock run.
Preserve production Dockerfiles, native Three rendering, backend lifespan and
Nginx routes. Record the exact committed candidate SHA and image IDs.

Use geographic deterministic provider fixtures containing features that
genuinely appear at higher zoom levels, plus matched coverage boundaries. Verify
actual native zoom, rotation, follow/reset, fullscreen and mobile behavior;
sample GPU pixels and inspect requests, timestamps and resource counts.
Demonstrate detail improvement, opacity comparisons, transitions, failure
fallback, automatic frame refresh and core-dashboard continuity. Screenshots
alone do not prove detail source or frame consistency.

Separately capture a small, dated set of actual RainViewer zoom-2 and
higher-zoom tiles for the same observed frame and a precipitation-bearing
region, respecting the shared provider budget and attribution. Render these
paired captures through the production native-browser path to demonstrate that
real provider data adds visible detail. Label capture replay separately from
live acquisition and from synthetic fixtures. Do not claim synthetic patterns
prove actual provider detail.

Preserve acceptance evidence, including comparisons, pixel results, demand and
memory measurements and cleanup proof. Require fresh production acceptance and
applicable CI at the final PR head. Stop and verify all task-owned processes,
listeners, containers, networks and disposable volumes immediately after checks.
Keep only the open-PR worktree and evidence. Submit the implementation PR
against `dev`; do not merge or publish to `main` as part of this task.

[issue]: https://github.com/bcl1713/starlink-dashboard/issues/288
[baseline]: 2026-10-05-overview-weather-overlay-design.md
[provider]: https://www.rainviewer.com/api/weather-maps-api.html
[transition]: https://www.rainviewer.com/api/transition-faq.html
[assessment]: ../../reports/2026-10-06-overview-weather-provider-assessment.md
[aviation-direction]:
  https://github.com/bcl1713/starlink-dashboard/issues/288#issuecomment-6008230258
