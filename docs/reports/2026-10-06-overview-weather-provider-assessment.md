# Overview weather provider assessment

## Purpose and status

Evaluate sources for [issue 288][issue]: sharper precipitation during native
globe zoom, lower visual weight, and efficient shared delivery. Preserve the
agreed 1080p desktop/fullscreen and mobile target, international coverage,
default-off Configuration setting, freshness and missing-coverage semantics, and
current application request and browser GPU limits.

The user explicitly invited different providers and maps generated from raw
data, and confirmed that international coverage matters. This assessment uses
primary provider documentation checked on 2026-10-06. It is a documented
comparison, not a completed image-quality or throughput benchmark. No accounts,
subscriptions, ingest services or replacement integrations have been created.

The user subsequently chose to avoid ongoing API fees and prefer free or
self-hosted sources. Paid managed providers below are comparison references;
they are excluded from the recommended implementation path. Free evaluation
allowances do not satisfy that recurring-cost constraint for an always-on app.

## Recommendation

The [aviation-weather architecture comment][aviation-direction], reviewed on
2026-10-06, recommends local ingest/cache/normalization and a consistent
frontend contract for future aviation hazards, flight-level atmosphere,
satellite and terminal products. Its explicit implementation order finishes
radar detail and opacity in this issue first. Carry that boundary into source
selection: keep provider adaptation server-side and retain
observed-versus-modeled provenance. These follow-on products are not part of
this comparison or issue acceptance. Missing radar coverage continues to be
shown as missing observations, pending a separate design for clearly labeled
satellite or model fallbacks.

Compare the existing free RainViewer path against locally generated tiles from
MRMS and OPERA composites before finalizing the source. Begin with one or two
immutable snapshots per region, observed precipitation only, no history,
nowcasts or global models. Measure actual detail, input/download size, decode
and tile-generation time, peak server RAM and browser requests. This is a
bounded comparison, not authorization to deploy a worldwide ingest service.

Retain RainViewer as the working source and international baseline during that
comparison. MRMS plus OPERA alone cannot replace all existing coverage. If local
generation wins, a separate design must specify the remaining observed regional
feeds or a frame-consistent RainViewer fallback. Keep source adaptation on the
backend and the browser rendering contract small; do not build a general
multi-provider platform.

LibreWXR is useful prior work to inspect, but the pinned revision's deployment
defaults are substantially larger than this dashboard's minimum hardware and its
product semantics differ. Do not adopt its full stack by default or promise it
is a cheap drop-in replacement. A stripped, radar-only trial would first need
independent resource and coverage evidence.

This recommendation is an engineering judgment from the contracts below. Higher
advertised map zoom, vector-derived styling, or worldwide modeled precipitation
alone does not establish additional observed detail, lower bandwidth, or a
better presentation at the supported globe zoom range.

## Comparison

| Source                           | Useful capability                                                                   | Main tradeoff                                                                | Assessment                                                       |
| -------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| RainViewer                       | Existing observed-radar tiles and coverage masks; 512-pixel tiles through zoom 7    | 100 requests/IP/minute; limited free-service terms                           | Keep as baseline; test higher-detail regional tiles              |
| Xweather Raster Maps             | Radar across several international regions; standard tiles normally through zoom 21 | Account, metered usage, and unresolved frame/mask requirements               | Credible managed alternative, excluded by the no-fee decision    |
| NOAA MRMS + EUMETNET OPERA       | Open regional gridded composites suitable for generating tiles locally              | Ingest, reprojection, cache and regional-source operations                   | Credible raw-data foundation; incomplete worldwide replacement   |
| LibreWXR                         | Existing self-hosted multi-region processor with compatible-style tile endpoints    | Resource footprint, source blending, coverage semantics and software license | Inspect stripped radar-only feasibility; avoid full defaults     |
| Tomorrow.io                      | Worldwide precipitation field; 256-pixel map tiles through zoom 12                  | API access and unresolved native observation resolution/mask semantics       | Secondary managed candidate                                      |
| OpenWeather Global Precipitation | Mixed-source global precipitation; documented sub-kilometer product claim           | Radar/model/satellite blend; tile zoom still capped at 7                     | Broader precipitation context, not a proven radar-detail upgrade |
| Google Weather maps              | New high-resolution U.S./European precipitation nowcast tiles through zoom 16       | Experimental, regional, different product semantics                          | Does not replace the required international observed-radar layer |
| NASA IMERG Early                 | Global gridded satellite precipitation                                              | Four-hour minimum latency and about 10 km resolution                         | Unsuitable for the current radar freshness and detail target     |

## Managed providers

### RainViewer baseline

The [Weather Maps API][rainviewer] documents observed frames, 256/512-pixel
tiles, maximum zoom 7, and a separate coverage mask. The [transition
summary][transition] states 100 requests/IP/minute. Prefer those specific
product contracts over the general [API FAQ][rainviewer-faq], which still
contains inconsistent statements about rate limits and nowcast.

The FAQ describes personal, educational and small-community use without an SLA;
commercial and guaranteed-availability use requires separate terms. This is a
source-selection constraint to verify for deployment, not a reason to change the
already working layer during this assessment.

### Xweather

[Raster tile documentation][xweather-tiles] describes 256-square PNG XYZ tiles
and normally supports zoom 1 through 21. The [layer catalog][xweather-layers]
lists observed radar for regions including North America, Australia, Japan,
South Korea and several European countries. It separately describes
`radar-global` as combining actual radar and satellite-derived estimates. Do not
silently substitute that blended product for observed radar.

The [raster changelog][xweather-changelog] describes a vector-based radar
rendering change in 2018. That does not imply the raster API delivers vector
geometry to our Three renderer, nor that its native measurements become more
detailed at arbitrary zoom. Use the standalone raster API for comparison;
adopting MapsGL would add an SDK and another mapping integration.

Resolve actual frame timestamp selection, immutable frame identity, geographic
coverage, missing-data behavior, maximum meaningful detail and permitted shared
backend caching before adoption. Published [time-offset
parameters][xweather-time] are useful but do not, alone, prove the existing
complete-frame guarantees.

### Illustrative Xweather cost

The [pay-as-you-go page][xweather-pricing] publishes 15,000 shared free accesses
per month and USD 0.0006 per raster map unit thereafter. It describes that
pricing as available in the U.S. and Canada; confirm account eligibility and
access to the needed international products. A [map unit][xweather-usage]
represents one 256-square, single-layer tile; combining layers does not make the
extra layers free.

These calculations assume 24 single-layer map units per update, one shared
working set, no other API use, and the published rate:

| Usage assumption                                     | Monthly map units | Estimated monthly API charge |
| ---------------------------------------------------- | ----------------: | ---------------------------: |
| One hour/day, 22 days, updates every five minutes    |             6,336 |                     USD 0.00 |
| Eight hours/day, 22 days, updates every five minutes |            50,688 |                    USD 21.41 |
| Always on, 30 days, updates every ten minutes        |           103,680 |                    USD 53.21 |
| Always on, 30 days, updates every five minutes       |           207,360 |                   USD 115.42 |

This is a scenario calculation, not a quote or measurement of the proposed
integration. Panning, distinct viewer regions, coverage delivery, duplicate
loads, source cadence and contractual cache rules change usage. A second viewer
need not double acquisitions when permitted caching coalesces the same tiles,
but a viewer in another region creates different demand. No paid commitment is
authorized by this assessment.

### Other managed candidates

[Tomorrow.io map tiles][tomorrow-tiles] support zoom 1 through 12 and 256-square
PNGs. Its [field catalog][tomorrow-fields] lists worldwide precipitation
intensity and map access. Obtain the observation-versus-model contract,
meaningful native resolution, coverage and plan entitlement before treating this
as a radar replacement.

[OpenWeather Global Precipitation][openweather] explicitly combines models,
satellites and radar, and documents tile zooms 3 through 7. Its resolution claim
does not establish that the product preserves the existing observed-radar and
coverage semantics.

[Google's experimental weather-map API][google-weather] documents U.S. and
European nowcast products, zoom 0 through 16, and one-hour tile caching. Its
regional coverage and nowcast semantics do not meet the selected global
observed-radar scope. Do not infer production stability from its tile zoom.

## Generating tiles from raw data

### Prefer existing gridded composites to radar volumes

[NOAA MRMS][mrms] documents kilometer-scale mosaics with a two-minute update
cycle and domains including the continental U.S. and additional U.S. regions.
Its [product table][mrms-products] identifies precipitation rate and
reflectivity products, update frequencies and distinct missing/no-coverage
values. Start with a selected two-dimensional composite, not individual radar
volumes or the full suite of products. A single national composite already
avoids recreating radar quality control and mosaicking.

[EUMETNET Open Radar Data][opera] supplies European OPERA composites in ODIM
HDF5 and cloud-optimized GeoTIFF. CIRRUS reflectivity has 1 km gridding and a
five-minute update cycle; surface rain-rate composites are also available. Its
current documentation describes anonymous access with low query limits, API-key
access, and notifications as the most efficient retrieval method. Composite
products are described as CC BY 4.0, with national-product policies and metadata
remaining distinct. Older OPERA pages describe separately licensed access; use
the current ORD route and verify the actual selected dataset.

MRMS and OPERA cover useful regions but do not preserve all international radar
coverage by themselves. Filling the remainder requires additional observed
regional feeds or retaining a managed provider. Satellite or forecast filling
would need explicit source labeling and different coverage semantics.

### Efficiency opportunity and operational cost

An ingest worker could acquire each selected composite once per source update,
store a bounded immutable snapshot, and generate requested globe tiles from that
snapshot. Upstream demand would track source cadence rather than viewers' camera
movements. Coalesce local tile generation and cap render concurrency; avoid
eagerly generating a full worldwide zoom pyramid every update.

A locally generated tile could pack a numerical precipitation value and a
validity/coverage channel together, with the browser shader applying the color
ramp and opacity. That can replace separate radar and coverage image requests
and their separate textures. This is an engineering option to benchmark, not a
measured bandwidth or memory improvement; packing precision, PNG sizes and
sampling behavior determine the actual benefit.

The worker adds grid decoding, reprojection, disk storage, CPU and server RAM.
Those costs are outside the existing PNG cache and browser texture ceilings and
would need their own explicit limits. Reusing the existing 48 MiB browser GPU
budget does not make server-side raw-data processing cost-free.

Use consistent units, preserve no-data flags, and pin all derived tiles to one
immutable frame generation. Regional source observation times must remain
recorded. Do not label independently refreshed regional mosaics as a single
uniform observation time or blend an older source into a newer frame unnoticed.

### Existing self-hosted implementation

[LibreWXR][librewxr] documents multi-region ingestion and compatible-style
tiles. Inspected revision `39305b7f81b19adaa9fe9c95a6259101e1be9d4f`, committed
2026-10-04: its [Compose file][librewxr-compose] defaults to a pipeline plus
renderer with 12 GB and 18 GB memory limits. Those are configured ceilings, not
measured usage or proof of minimum requirements. Its
[configuration][librewxr-config] uses 16 render workers by default, while the
legacy single-mode alias uses one worker with the same two-service architecture.
Cached older documentation still describes a true single-process mode.

That full configuration is unsuitable as an assumed lightweight addition to this
repository's [4 GB minimum, 8 GB recommended host][system-requirements]. Its
software is AGPL-3.0-or-later; source-data licenses remain separate.

Its default global precipitation includes satellite-derived estimates and model
fallbacks. Its documented coverage tile indicates where radar exists, while
RainViewer's mask indicates absent radar coverage. Therefore, compatible-style
URLs do not establish semantic compatibility. Verify pinned-version behavior,
source provenance, actual missing-data masks, frame immutability, resource peaks
and international coverage before considering adoption. Do not point the
existing provider transport at an arbitrary replacement URL or weaken its
security checks.

### Satellite-only raw alternative

[NASA IMERG Early][imerg] has approximately 10 km spatial resolution and
four-hour minimum latency. That misses both the sharper-detail objective and the
existing one-hour hard expiry. It could support a separately scoped
historical/global precipitation view, but should not replace current radar.

## Decision evidence still needed

Before choosing a replacement, obtain:

- Same-region observed imagery at comparable native geographic resolution,
  rendered at actual 1080p native globe zoom with the lower-opacity candidates.
- Coverage comparisons for representative international mission regions,
  including missing-data masks and source type rather than marketing maps.
- Frame identity, observation time, refresh, expiry and cache guarantees.
- Measured compressed bytes, fetch counts, decode/texture storage, latency,
  failure recovery and multi-viewer demand at the agreed resource ceilings.
- Approved recurring cost for managed service, or bounded CPU/RAM/disk and
  maintenance scope for self-hosted ingestion.

Under the user's no-fee decision, only the self-hosted-resource branch of that
last check applies. RainViewer's existing free-service suitability also remains
part of deployment review; no paid plan is the proposed fallback.

Maintain the current implementation while evaluating. Provider selection remains
provisional until this evidence is available. The camera-driven loader remains
necessary for efficient globe delivery whichever source is chosen; source
selection can additionally change tile size, payload encoding, masks and the
maximum meaningful zoom.

[issue]: https://github.com/bcl1713/starlink-dashboard/issues/288
[aviation-direction]:
  https://github.com/bcl1713/starlink-dashboard/issues/288#issuecomment-6008230258
[rainviewer]: https://www.rainviewer.com/api/weather-maps-api.html
[transition]: https://www.rainviewer.com/api/transition-faq.html
[rainviewer-faq]: https://www.rainviewer.com/api.html
[xweather-tiles]: https://www.xweather.com/docs/maps/getting-started/map-tiles
[xweather-layers]: https://www.xweather.com/docs/maps/layers
[xweather-changelog]: https://www.xweather.com/docs/maps/changelog
[xweather-time]: https://www.xweather.com/docs/maps/getting-started/time-offsets
[xweather-pricing]: https://www.xweather.com/pricing/weather-api-pay-as-you-go
[xweather-usage]: https://www.xweather.com/docs/maps/getting-started/accesses
[tomorrow-tiles]: https://docs.tomorrow.io/reference/get-map-tile
[tomorrow-fields]: https://docs.tomorrow.io/reference/weather-data-layers
[openweather]: https://openweathermap.org/api/global-precipitation-map
[google-weather]:
  https://developers.google.com/maps/documentation/weather/weather-map
[mrms]: https://www.nssl.noaa.gov/projects/mrms/
[mrms-products]: https://www.nssl.noaa.gov/projects/mrms/operational/tables.php
[opera]:
  https://eumetnet.github.io/openradardata-documentation/1-ORD-API-overview/
[librewxr]: https://github.com/JoshuaKimsey/LibreWXR
[librewxr-compose]:
  https://github.com/JoshuaKimsey/LibreWXR/blob/39305b7f81b19adaa9fe9c95a6259101e1be9d4f/docker-compose.yml
[librewxr-config]:
  https://github.com/JoshuaKimsey/LibreWXR/blob/39305b7f81b19adaa9fe9c95a6259101e1be9d4f/src/librewxr/config.py
[system-requirements]: ../setup/system-requirements.md
[imerg]: https://gpm.nasa.gov/taxonomy/term/1357
