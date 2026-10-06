# Aviation weather local rendering proof design

This is the bounded evidence work required by the
[architecture proposal](./2026-10-06-aviation-weather-design.md) for
[issue 290](https://github.com/bcl1713/starlink-dashboard/issues/290). Determine
whether real scientific and advisory inputs can be decoded into the proposed
representations and displayed on the native globe within the stated budgets. All
three proofs are pending design review and execution. No sample decode or render
is claimed by the source endpoint measurements.

## Common controls

Use a research tool under `tools/aviation-weather-proof/`, independent of the
production API and settings. Pin decoder dependencies in the research tool; do
not add scientific-format parsers to frontend dependencies. Prefer ecCodes for
GRIB2, netCDF4 for GOES CMI, pyproj for source navigation, NumPy for bounded
arrays, and the existing Three/Playwright toolchain for local rendering. Verify
current upstream documentation and dependency licences before pinning versions.

Every acquired artifact records exact public URL/key, retrieval UTC, source
times, content length, SHA-256 and licence/attribution. A replay uses pinned
objects and verifies their hashes; a live acquisition is labeled separately. If
an old source object has departed, do not silently replace it under the same
hash. Archive evidence through the repository acceptance retention system with
checksums and stable links; keep large scientific files out of Git.

The renderer receives only normalized envelope, fields/masks and geographic
features. Instrument browser requests to fail the run on direct provider access.
Use the repository native globe and its camera mapping, terrain and overlay
hierarchy. Show source, observed/forecast semantics, UTC, level and units in
every screenshot. A flat Python plot may help diagnose reprojection but does not
satisfy the native-globe proof.

Record command/session, PID/process group, private Compose project/volumes,
ports and temporary paths before starting. Wrap the entire runner in
`timeout --kill-after=10s 20m`; separately cap each decode at 120 seconds.
Exit/INT/TERM handlers close browser contexts, terminate/reap children and
remove only owned disposable resources. Verify process/listener and labeled
container/network/volume absence after success, failure or timeout. Preserve the
open-PR worktree and archived evidence, not live servers.

## Global model proof

Use the verified GFS 2026-10-06 00Z F006 0.25-degree inventory described in the
[source inventory](../../reports/2026-10-06-aviation-weather-source-inventory.md).
Acquire only UGRD/VGRD/TMP at 500 hPa through indexed byte ranges; derive each
range end from the next message offset in that same index. Require correct 206
Content-Range and bounded lengths; reject a server ignoring Range. A bounded
NOMADS field-filter response is an alternate acquisition with its own recorded
URL/hash, not an interchangeable artifact identity.

Decode with ecCodes and verify run, lead, valid UTC, grid dimensions, scan
orientation, units and pressure level. Rotate vectors into earth-relative
east/north if needed. Produce `latlon-grid-v1` U/V/T and quality mask, wrapping
longitude and preserving invalid cells. This first proof labels 500 hPa; it does
not claim an exact flight-level product or validate FL interpolation.

Render a temperature scalar field and bounded wind barbs locally. Capture world
view, North Atlantic route view, antimeridian and polar view on the native
globe. Compare decoded source values at ten documented coordinates with
normalized samples within declared quantization/resampling tolerance. Use a
synthetic masked cell and directional vector fixture as separately labeled
failure/orientation controls; they cannot replace real-source renders. Measure
source bytes, CPU seconds, wall time, peak RSS, output bytes, decoded browser
bytes and peak GPU allocation.

## Advisory proof

Acquire `https://aviationweather.gov/api/data/isigmet?format=geojson` and pin
one valid real Polygon/MultiPolygon advisory with issuer, hazard, validity and
base/top context. Do not infer the units/reference of provider `base` or `top`
from field names; verify the current API schema and raw bulletin before
normalizing. Preserve unknown references explicitly and compare selected
geometry against the authoritative product display.

Render a locally triangulated polygon and outline above terrain alongside a
route, aircraft and station symbol, with passive provenance/validity text.
Include a real advisory view and separate synthetic controls for a polygon with
a hole, a dateline crossing, invalid vertices, cancellation and expiry. Only a
validated feed with declared scope may report no active advisories; truncation
or unresolved geometry must show incomplete data. Record vertex counts and
renderer allocations, and confirm click/rotation remain responsive.

## Satellite proof

Use the listed GOES-19 channel 13 full-disk CMIP NetCDF object from the source
inventory, or another explicitly pinned public object if that object departs.
The listed 23,995,077-byte object fits the proposed 32 MiB source cap; validate
actual downloaded bytes and hash before decoding. Read CMI units, scale/fill,
DQF and `goes_imager_projection` attributes. Source scan start/end remain
observation identity; retrieval time never replaces them.

Decode brightness temperature and reproject to the geographic output grid in
bounded windows. Mask off-Earth navigation, invalid pixels, rejected quality and
conservative limb limits. Render a local IR texture/legend on the globe with
unavailable ocean/polar areas explicit. Retain scientific values; the backend
does not import a provider's colored map screenshot.

Capture Americas, Atlantic edge/limb and night-side views. Verify ten geographic
samples against the decoded input within a declared resampling tolerance.
Include a separate two-region synthetic seam fixture to test unequal times,
missing pixels and deterministic region ownership. One GOES sample establishes
that rendering path only; it does not establish global satellite completeness,
Meteosat/Himawari access, or multi-region calibration compatibility.

## Evidence and phase entry

| Gate                              | Required retained evidence                                                                                          | Current state                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Source access                     | Origins, terms, cadence, endpoint checks and snapshot volume                                                        | Documented in source inventory; conditional sources remain gated |
| Model decode and local render     | Pinned GRIB2 messages, normalized descriptor/buffers/mask, numeric comparisons, globe captures and resource metrics | Pending                                                          |
| Advisory local render             | Pinned real advisory, normalized feature, geometry/time/vertical controls and globe captures                        | Pending                                                          |
| Satellite decode and local render | Pinned NetCDF, normalized grid/mask, navigation/value controls, globe captures and resource metrics                 | Pending                                                          |
| Radar regression                  | Current focused unit tests; existing production acceptance if production paths change                               | Existing behavior preserved by this documentation-only increment |
| Architecture replacement boundary | Independent source adapters; renderer has no provider parsing or external requests                                  | Proposed; verify in proof request instrumentation                |
| Cleanup                           | Owned PID/listener and Compose container/network/volume listings empty                                              | Required after proof execution                                   |

Publish a measured report with pass/fail per gate and links to artifacts. If a
decode exceeds the cap, reduce source selection or revise the budget through
design review; do not raise limits silently. A fixture-only success or a live
endpoint response cannot complete the three real-source rendering gates. Open
small product implementation issues only after the architecture review and this
evidence are accepted. Keep issue 290 open until every architecture acceptance
requirement has evidence or an explicitly reviewed scope decision.
