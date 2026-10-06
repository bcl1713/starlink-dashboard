# Aviation weather API

Phase 1 of issue 290 provides METAR/SPECI observations, TAF terminal forecasts
and international SIGMET advisories. Enable each layer in **Configuration →
Overview → Aviation weather**. All three start disabled. Overview displays
native station symbols, forecast diamonds, advisory polygons and passive UTC
status. Precipitation radar retains its existing settings and acquisition
service.

## Endpoints

| Method | Path                                                        | Result                                                                            |
| ------ | ----------------------------------------------------------- | --------------------------------------------------------------------------------- |
| GET    | `/api/aviation-weather/v1/settings`                         | Boolean `metar`, `taf`, `sigmet` and integer `revision`                           |
| PUT    | `/api/aviation-weather/v1/settings`                         | Atomically save a nonempty subset of those booleans and return confirmed settings |
| GET    | `/api/aviation-weather/v1/catalog`                          | Versioned product envelopes for existing radar and the three aviation layers      |
| GET    | `/api/aviation-weather/v1/products/{instance}/{layer}.json` | Immutable normalized GeoJSON for the currently admitted, enabled instance         |

Settings and catalog responses use `Cache-Control: no-store`. Payloads use
`private, no-cache`, an ETag and a SHA-256 identity. Unknown, disabled, expired
and superseded payload identities return 404. Invalid settings return 422;
optional service failures return sanitized 503 responses. The OpenAPI schema
exposes strict envelope fields and their validation constraints.

## Data meaning

Station positions use longitude/latitude. Winds and gusts use m/s, visibility
and ceilings use meters (ceiling AGL), pressure uses Pa and temperatures use K.
Missing values remain null; variable wind and visibility lower bounds are
explicit. Flight category is derived only when the reported evidence supports
it. METAR/SPECI reports become stale at 75 minutes and expire at 120 minutes
from observation. TAF validity is half-open UTC; all forecast groups retain
FM/BECMG/TEMPO/probability semantics and BECMG completion time. Forecast symbols
use currently effective groups and show unknown when alternatives disagree.

SIGMET retains raw text, issuer/FIR, provider and canonical bulletin series,
issue time, validity, revision/cancellation relation and reported vertical
reference. Unsupported or ambiguous altitude evidence remains unknown. Cancelled
and expired advisories have no shading. Invalid geometry survives as an
unlocated textual advisory. Polygons retain holes and split at the antimeridian.
Cancellation history is bounded to 24 hours and targets the original bulletin
interval rather than later reuse of the same series.

AWC dissemination is the source; originating station/issuer identity and
attribution remain visible. Feed completeness is unknown or explicitly partial.
Missing reports and empty feeds mean unknown weather. Each published layer is
bounded to 1 MiB. Station subsets sample ten-degree geographic cells and
disclose omissions; oversized advisory feeds retain only still-valid previous
data. The current AWC station captures therefore show partial global coverage.

## Runtime and acceptance

Enabled readers share source acquisition and constrained disposable
normalization workers. METAR/SIGMET refresh every five minutes and TAF every ten
minutes; there is no source work at startup or with all layers disabled. Source
failures preserve original finite freshness and expiry. Disabling a layer aborts
owned work and invalidates its payloads. Hidden/offline browser views stop work
and release native rendering resources.

Run isolated production acceptance against a clean committed candidate:

```bash
tools/acceptance/aviation-weather/run.sh <full-HEAD-SHA> <provisioned-browser>
```

The runner builds the production images without cache, exercises the Nginx API
and native WebGL renderer with source-shaped transport fixtures, retains
screenshots/evidence under `test-results`, and tears down its private Compose
project and volumes. Fixtures are deterministic controls, not live-weather
claims. Source normalization also has dated live-capture controls.

Scientific model grids, satellite imagery, wind/cloud/humidity views and route
weather decisions remain later phases of issue 290.
