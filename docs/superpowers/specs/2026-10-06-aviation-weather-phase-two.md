# Aviation weather Phase 2: GFS winds and temperature

Status: proposed for owner review; implementation has not started.

For [issue 290](https://github.com/bcl1713/starlink-dashboard/issues/290),
extend the merged Phase 1 aviation weather with global modeled winds and
temperature. The requested next phase follows the
[approved architecture](2026-10-06-aviation-weather-design.md) and the
real-source GFS proof merged in
[PR 292](https://github.com/bcl1713/starlink-dashboard/pull/292). Phase 1 is
merged in [PR 293](https://github.com/bcl1713/starlink-dashboard/pull/293). This
spec proposes two implementation PRs, followed by their integrated acceptance.

## Intended outcome

An operator enables wind barbs and/or temperature shading in Configuration,
selects a pressure surface or flight level and forecast horizon, and sees native
global products on Overview with model run, actual valid UTC, vertical
reference, units, legend, freshness and NOAA attribution. Settings propagate
between open browsers through the existing confirmed revision mechanism. Weather
acquisition, decoding and rendering remain optional and bounded so core
dashboard work stays responsive. Missing cells remain unknown; valid calm winds
remain zero.

The implementation covers U/V winds and temperature. Particles, contours,
forecast animation, humidity, cloud products, precipitation, WAFS, satellite and
route sampling remain subsequent work. Surface winds and temperature have
different reporting heights and require their own component-height contract;
show Surface as unsupported until that contract exists.

## Architecture and delivery choice

Promote the scientific algorithms from the diagnostic proof into
production-owned modules, with production contracts and tests. Production must
not import code from `tools/acceptance` or expose capture manifests, source URLs
or filesystem paths to the browser. The existing proof stays available as
independent evidence.

Use a separate optional GFS worker container. It owns acquisition, decoding,
publication and retention, with one CPU and a 1 GiB memory limit. FastAPI owns
validated settings, bounded demand signaling and immutable payload serving;
handlers never decode or wait for a full model ingest. The existing bulletin
normalization workers remain independent. Failure of the optional worker makes
its layers unavailable while health, telemetry and Phase 1 weather continue.

Compared with decoding in FastAPI, this adds worker packaging and local IPC but
enforces a separate resource budget. Compared with importing the diagnostic
tool, extracting production modules preserves the application deployment
boundary and avoids including satellite/research dependencies unnecessarily.

1. **GFS foundation PR:** worker image, inventory/range acquisition, pressure
   U/V/T normalization, atomic store, retention, demand/cancellation protocol,
   provider-neutral catalog and binary serving. Pressure selection starts with
   850, 500, 300, 250 and 200 hPa. Layers remain default-off; browser controls
   and production rendering follow in the second PR.
2. **GFS presentation PR:** derived flight levels, strict browser grid
   admission, reusable scalar/vector renderers, Configuration preferences,
   passive Overview status, and integrated production/browser acceptance. This
   completes Phase 2.

Keep each PR against `dev` and leave issue 290 open. Each needs its own reviewed
implementation plan after approval of this spec.

## Acquisition and selection

Use the public NOAA GFS bucket documented in the
[NOAA registry](https://registry.opendata.aws/noaa-gfs-bdp-pds/) and fields in
the [NCEP inventory](https://www.nco.ncep.noaa.gov/pmb/products/gfs/). Those
references were checked on 2026-10-06. Attribute NOAA/NCEP and identify
resampling and derived levels as dashboard processing. The registry documents
four runs daily and public reuse; this establishes neither an availability SLA
nor a measured delivery delay.

Discover available cycle prefixes and actual forecast objects from bounded
allowlisted listings. Never manufacture a latest-object URL from the clock.
Initial leads are F000/F003/F006/F009/F012/F018/F024/F036/F048, admitted only
when the selected fields exist. Validate the index, strictly increasing offsets,
unique field/level matches, object size and exact ranges. Use an object
validator to bind index and ranges to one immutable source version; reject
changed objects, ignored Range, mismatched Content-Range, short responses and
duplicate messages. There is no full-file fallback for a failed range request.

Decode GRIB metadata to verify run, lead, valid time, parameter, unit, pressure,
grid, scanning orientation and earth-relative vector basis. Matching filenames
and index text alone are insufficient. Unsupported grids or vector bases fail
admission unless a tested backend transformation exists.

Acquire only the active selection's necessary fields and pressure brackets; do
not preload every level and lead. Share selections between browser readers.
Inventory refresh is at most once per ten minutes while demand exists. Cap the
selection queue at 16 deduplicated jobs and prioritize the current settings
revision. On saturation, retain a compatible unexpired product or report
unavailable; no unbounded background catch-up or retry loop.

## Vertical and time meaning

Use tagged pressure selections in Pa internally and hPa in the UI. In the second
PR support FL050/100/180/240/300/340/390/450 as pressure altitude relative to
1013.25 hPa. Convert the selected FL to ISA pressure server-side and interpolate
U/V/T in log pressure using matching source grids/run/leads. Publish the actual
ordered bracketing pressures and `isa-log-pressure-v1` derivation. A native
pressure surface never becomes a flight level by relabeling it.

Use the smallest supported brackets from available pressure messages; exact
pressure selections are published as native pressure products. Missing bracket
data makes the cell unavailable. Acquire matching surface pressure and suppress
cells whose selected pressure is below terrain, including interpolation
contributors; extrapolated below-ground values are not atmospheric coverage.
Surface-pressure absence also prevents those cells from being admitted.

Configuration offers Current and +3/+6/+9/+12/+18/+24/+36/+48 hour horizons.
Resolve the target from real UTC and choose the nearest admitted instant in one
selected run, with ties toward the earlier instant. Show requested horizon and
actual selected valid time. Promote a newer run only after the whole selected
generation is validated. An older compatible run remains explicitly labeled
until replacement or expiry. Do not combine runs or silently interpolate time.
Reject targets outside the supported run's F000–F048 range.

F000 is modeled analysis; positive leads are numerical-model forecasts. Model
freshness is anchored to run time: stale after nine hours, unavailable after
eighteen hours or when the target leaves supported validity. Refreshing a failed
source never renews these deadlines. Mission simulation time does not affect
model identity or age.

## Immutable normalized product contract

Extend the existing `aviation-weather-v1` envelopes with `winds` and
`air-temperature` entries using `latlon-grid-v1`. Preserve the existing station,
advisory and radar contracts. A JSON descriptor names same-origin hashed binary
components, their exact lengths, units, quantization and allocation
declarations. The current grid envelope needs an additive descriptor contract:
its single payload field alone cannot identify multiple component buffers.

Use 720 × 361 nodes, longitude -180 plus 0.5-degree steps without a duplicated
seam column, and latitude +90 minus 0.5-degree steps. Row-major little-endian
Int16 U/V in m/s and temperature in K have scale 0.01; temperature offset is
273.15 K and wind offset is zero. Overflow fails publication. Uint8 masks are 0
valid, 1 outside coverage, 2 missing, 3 quality rejected. Interpolation requires
all contributors valid. A shared conservative mask for U/V/T is acceptable and
must be declared; invalid samples are never interpreted as physical zero.

One complete U/V/T generation is 1,819,440 binary bytes before metadata. Wind
and temperature can share immutable component buffers and one generation without
double allocation. Identity includes normalization version, geometry,
quantization, masks, source hashes, run/lead and vertical derivation.

Reserve staging space before acquisition. Publish a validated candidate
directory and atomically advance the catalog pointer only after payload hashes,
lengths and envelope admission pass. A crash or rejected candidate leaves the
previous compatible generation usable until original expiry. Reader leases
protect immutable artifacts during responses; retention removes only unleased
objects. Retain at most two runs and only admitted selections. Startup removes
abandoned task-owned staging objects without deleting completed leased products.

Catalog/settings remain no-store. Payload routes accept only admitted instance
and component identifiers, revalidate enabled settings and expiry, use private
revalidation with content hashes, and never accept arbitrary paths or URLs.
Disabled, expired or incompatible products have no accessible payload.

## Configuration, rendering and cancellation

Add a Flight-level atmosphere group to the existing weather Configuration card:
independent default-off wind/temperature booleans, shared vertical selection and
forecast horizon. Existing saved settings migrate with default-off additions.
Old partial boolean updates remain valid. Strictly reject unsupported selection
values before source work. Confirm saves and use the existing revision polling
to synchronize browsers. Overview contains passive context and legends.

Demand is created by visible enabled catalog readers, with a bounded 120-second
lease refreshed by the existing one-minute catalog polling. Disabled layers
cancel demand before save acknowledgement. Selection changes invalidate work for
the prior revision; candidates check revision again before publication.
Last-reader expiry cancels queued and in-flight work; shutdown invalidates all
owned leases, terminates and reaps the decoder, and closes transports. Readers
disconnecting independently must not cancel work still leased by siblings.
Define the IPC request/acknowledgement, crash recovery and file ownership
protocol in the foundation implementation plan and test it across processes.

Reuse the proven geographic projection and packed scalar sampling algorithm in
production-owned renderers. Temperature is one shaded raster, winds at most
2,000 earth-relative barbs. Labels distinguish modeled analysis/forecast from
observations. Render below operational markers and preserve bulletin picking,
radar coverage hatching, route visibility, day/night terrain and globe gestures.
Wind/temperature legends explain units, selected level, source and UTC identity.

Strict parsers check dimensions, masks, units, hashes and lengths before GPU
allocation. Reserve old plus candidate resources before atomic replacement.
Abort and dispose on disable, hide, offline, unmount or superseding revision.
Expiry removes the layer even if network polling fails; recovery fetches a fresh
admitted generation. Missing coverage never acquires a clear-weather label.

## Resource budgets and verification gates

Retain the architecture's limits: one decoder/CPU and 1 GiB worker RAM;
120-second decode with ten-second termination grace; two HTTP exchanges; 20
attempts/minute; 30-second absolute HTTP deadline; 32 MiB/source object and 256
MiB expanded; 5 GiB/day scientific acquisition. Disk quota is 4 GiB including 1
GiB staging, 2.5 GiB published and 0.5 GiB reserve. Persist acquisition
accounting across worker restarts. Pressure-bracket and surface-pressure
overhead must fit these limits, with measured peak RSS and CPU/wall time before
promotion.

The additional browser allowance is shared with Phase 1, rather than newly
allocated to GFS: 32 MiB decoded/geometry and 16 MiB GPU. Total weather limits
remain 128/64 MiB with radar's reserved 96/48 MiB intact. Limit combined new
weather work to four fetch/decode operations, 16 MiB encoded per generation and
a 45-second generation deadline. Include descriptors, conversion buffers, barb
geometry, retained data and replacements in measured reservations.

Acceptance must demonstrate:

- Source version pinning, malformed/truncated GRIB/index rejection, finite
  quotas, deduplicated demand, cancellation, process death and atomic recovery.
- Independent source/CPU/GPU agreement for U/V/T, seam/poles, scan direction,
  valid zero, missing masks, below-terrain masking, and flight-level brackets.
- Confirmed settings propagation between browsers, forecast rollover, stale and
  expiry behavior, source/worker outages and no browser source requests.
- Desktop/fullscreen/mobile native rendering through production Nginx, including
  wind direction/hemisphere orientation, temperature legend and report picking.
- Unchanged radar and Phase 1 controls, and core health/telemetry/globe response
  while GFS acquisition and decoding are saturated or failing.
- Clean candidate SHA, no-cache production images, measured resources, immutable
  evidence and required CI for each PR. Software-rendered browser evidence is
  labeled as such; minimum-host/hardware performance is measured separately
  before enabled deployment claims.
- Scoped cleanup of all task-owned processes, listeners, containers, networks
  and disposable volumes after every acceptance attempt, including failures.

## Review and next step

Review this scope and two-PR split before writing implementation plans. The
first implementation plan must specify worker packaging/IPC, disk leases and
failure recovery, settings compatibility, descriptor schema, exact file map and
the smallest meaningful red/green contract checks. The second must specify FL
derivation, rendering reservations and integrated browser acceptance. Neither
the old diagnostic proof nor approval of this draft constitutes completion of
Phase 2.
