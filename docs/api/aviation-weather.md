# Aviation weather API

Phase 1 of issue 290 provides METAR/SPECI observations, TAF terminal forecasts
and international SIGMET advisories. Enable each layer in **Configuration →
Weather → Aviation weather**. All three start disabled. Overview displays native
station symbols, forecast diamonds, advisory polygons and passive UTC status.
Precipitation radar retains its existing settings and acquisition service.

## Endpoints

| Method | Path                                                        | Result                                                                         |
| ------ | ----------------------------------------------------------- | ------------------------------------------------------------------------------ |
| GET    | `/api/aviation-weather/v1/settings`                         | Default-off bulletin/model preferences, `gfs_selection` and integer `revision` |
| PUT    | `/api/aviation-weather/v1/settings`                         | Atomically save a nonempty subset of preferences and return confirmed settings |
| GET    | `/api/aviation-weather/v1/route-sigmets`                    | Bound route context, current notice state and geographic intersection spans    |
| PUT    | `/api/aviation-weather/v1/route-sigmets/acknowledgement`    | Confirm one exact notice acknowledgement or Show again                         |
| GET    | `/api/aviation-weather/v1/catalog`                          | Versioned radar, bulletin, GFS wind and temperature envelopes                  |
| GET    | `/api/aviation-weather/v1/products/{instance}/{layer}.json` | Immutable normalized GeoJSON for the currently admitted, enabled instance      |
| GET    | `/api/aviation-weather/v1/products/{instance}/grid.json`    | Immutable scientific descriptor with same-origin component hashes              |
| GET    | `/api/aviation-weather/v1/products/{instance}/{field}.bin`  | Admitted `u`, `v`, `t` or `mask` buffer with a SHA-256 ETag                    |

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

Overview shows compact feed status, counts and a legend. Click or tap a station
marker or forecast diamond to inspect its report. The keyboard-accessible
**Inspect weather reports** chooser retains METAR/TAF inspection. SIGMET
polygons and route notices are passive; full SIGMET reports and actions belong
to **Configuration → Weather → Aviation weather**.

### Route SIGMET state

`sigmet_intersecting_only` defaults to `false` and does not enable SIGMETs. When
true, shading includes confirmed intersections with the entire selected ordinary
or simulation route. Matching uses shortest spherical route segments, including
current running/completed replay geometry. Weather eligibility uses actual UTC
and `[valid_from, valid_to)`, independently of replay time. Altitude and route
passage-time matching are not evaluated. Unknown/incomplete matches never become
a definite zero or a clear-route claim.

The no-store route snapshot uses `schema: route-sigmets-v1`. It carries server
UTC, settings/state revisions, generation identity, route name/source/context,
the original SIGMET product envelope, status/reason, complete/truncated flags,
entries, unresolved feature references, future references and omission counts.
Entries bind notice/bulletin/digest identities to the admitted feature IDs,
acknowledgement, attention order, original validity and bounded segment
fractions with entry/exit coordinates. Raw reports and polygons remain in the
immutable product; the route response does not duplicate them.

Clear and Show again send only this strict mutation:

```json
{
  "context_key": "<64 lowercase hex characters>",
  "notice_key": "<64 lowercase hex characters>",
  "semantic_digest": "<64 lowercase hex characters>",
  "acknowledged": true
}
```

`acknowledged: false` requests Show again and advances attention order. A
successful write returns confirmed state revision and attention order. Repeated
identical writes are idempotent. Stale or unknown identities return 409; refresh
before retrying. Invalid bodies return 422. Storage or optional-service failure
returns sanitized 503 and cannot report a successful acknowledgement. All route
responses, including errors, use `Cache-Control: no-store`.

Both visible online screens poll every five seconds, even when unfocused.
Healthy controlled saves propagate within eight seconds; hidden/offline screens
catch up on return. Obsolete route/feed responses cannot replace a newer
binding. Configuration alone can acquire reports. One shared source owner per
query client avoids duplicate loops. Workers and browser owners release on
cancellation, disable, hidden/offline, supersession and unmount.

Acknowledgements persist separately in `data/settings/route-sigmet-notices.json`
with atomic, process-locked writes. Retention is bounded to eight route
contexts, 4,000 records and 2 MiB; expired records are removed.
Least-recently-used inactive contexts can be evicted, so revisiting one may show
notices pending again. Live current-context acknowledgements are never silently
evicted; a full store rejects the write. Corrupt storage fails unavailable
without overwriting evidence.

Enabled readers share source acquisition and constrained disposable
normalization workers. METAR/SIGMET refresh every five minutes and TAF every ten
minutes; there is no source work at startup or with all layers disabled. Source
failures preserve original finite freshness and expiry. Disabling a layer aborts
owned work and invalidates its payloads. Hidden/offline browser views stop work
and release native rendering resources.

Run isolated production acceptance against a clean committed candidate:

```bash
ROUTE_SIGMET_REAL_CAPTURE=/path/to/pinned-capture \
  timeout --kill-after=10s 40m tools/acceptance/aviation-weather/run.sh \
  <full-HEAD-SHA> <provisioned-browser>
```

The runner builds the production images without cache, exercises the Nginx API
and native WebGL renderer with source-shaped transport fixtures, retains
screenshots/evidence under `test-results`, and tears down its private Compose
project and volumes. Fixtures are deterministic controls, not live-weather
claims. Images and browser tests use the exact committed archive; reused browser
dependencies must match its package lock. The runner reserves unique loopback
ports, records ownership, and writes PASS only after browser assertions and
verified teardown. A separate pinned AWC capture is replayed through production
normalization and native rendering at its recorded UTC; this is dated evidence,
not a current live-source claim. GFS production coverage retains its dedicated
worker/field fixture stack, with existing source/hardware gaps reported
separately. See the
[route SIGMET evidence report](../reports/2026-10-15-route-linked-sigmets.md).

Scientific model grids, satellite imagery, wind/cloud/humidity views and route
weather decisions have separate delivery increments. The GFS foundation below
provides model data; Configuration controls and native model rendering follow in
the Phase 2 presentation PR. Satellite/cloud/humidity and route decisions remain
later phases of issue 290.

## GFS foundation

`winds` and `temperature` default to false. `gfs_selection` defaults to
`{"pressure_pa":50000,"horizon_hours":0}`. Supported pressures are 85000, 50000,
30000, 25000 and 20000 Pa; horizons are 0, 3, 6, 9, 12, 18, 24, 36 and 48 hours.
Selection uses the nearest available instantaneous model lead to current UTC
plus horizon, with earlier ties. Catalogs disclose the actual run, lead and
valid UTC. F000 is analysis; positive leads are forecasts. Native pressure
surfaces do not claim flight-level derivation.

Model freshness is fixed at run plus nine hours and expiry at run plus eighteen
hours. Source failure cannot renew either deadline. Targets outside F000–F048
and targets beyond the current lead's actual inventory midpoint have no payload.
Missing or stale worker ownership leaves models unavailable while settings,
bulletins, radar and core health remain usable.

Descriptors declare a 720×361 globe, longitude -180/+0.5 and latitude +90/-0.5,
with a shared conservative U/V/T validity mask. U/V are little-endian Int16 m/s
at scale 0.01; temperature is Int16 K at scale 0.01 and offset 273.15. Mask
values are 0 valid, 1 outside coverage, 2 missing and 3 quality rejected.
Surface pressure masks below-terrain samples before interpolation; any missing
contributor stays unknown. A true zero wind remains valid. Each complete binary
generation is 1,819,440 bytes; envelope allocation bounds include its
descriptor.

Ordinary startup through the Compose wrapper includes the GFS worker:

```bash
./scripts/compose.sh up -d --build
```

The base Compose configuration includes the worker, so ordinary `build`, `up`,
`logs` and `down` commands manage it with the rest of the app. Local Compose
overrides and custom file selection retain Docker's normal behavior. Existing
commands using `-f docker-compose.yml -f docker-compose.gfs.yml --profile gfs`
remain supported. Winds and temperature still default off in Configuration; an
idle worker performs no ingest.

The worker shares one CPU and 1 GiB across its owner and disposable decoder;
scientific dependencies stay in its image. API mounts artifacts read-only and
the mailbox read-write. Worker settings are read-only. A visible catalog renews
one API startup owner's 120-second demand lease; readers share one selection.
HTTP budgets and received bytes persist across worker restarts. No ingest runs
at API startup or with no admitted readers.

Settings saves invalidate old demand under the publication lock. Disable denies
payloads immediately and waits up to fifteen seconds for obsolete work to exit.
If acknowledgement is missing, the API returns sanitized 503 while the disabled
save remains committed. Immutable response leases prevent retention from
deleting an open buffer, and release on disconnect. Unknown, disabled, expired,
obsolete, damaged and private-lineage paths have no accessible payload.

Phase 2 Configuration uses one tagged `gfs_selection` for both model layers:

```json
{
  "winds": true,
  "temperature": false,
  "gfs_selection": {
    "vertical": { "kind": "flight-level", "flight_level": 390 },
    "horizon_hours": 3
  }
}
```

Native pressure choices are 85000, 50000, 30000, 25000 and 20000 Pa. Flight
levels are 50, 100, 180, 240, 300, 340, 390 and 450; horizons are UTC now plus
0, 3, 6, 9, 12, 18, 24, 36 and 48 hours. Legacy pressure selections migrate on
read. The actual available source lead is selected deterministically; Overview
displays its run, lead and valid UTC, rather than implying the target horizon is
an exact available forecast.

Flight levels use two-segment ISA pressure altitude and the two distinct nearest
complete actual U/V/T pressure brackets. U/V/T interpolate in log pressure; no
extrapolation or imaginary source level is admitted. Descriptors carry
`reference: pressure-altitude-1013.25hpa`, `derivation: isa-log-pressure-v1` and
ordered `source_pressures_pa`. Both brackets and surface pressure participate in
conservative validity. The source GRIB instance/version lineage remains private.

Browser admission verifies descriptor/component hashes, lengths, endian types,
physical quantization, geometry, time and selection. Equal immutable components
share owners only when their physical meaning agrees. All optional bulletin,
model and highlight owners share four operation slots and 16 MiB encoded / 32
MiB decoded / 16 MiB GPU allowances, including conversion and simultaneous
old/candidate generations. Model envelopes declare conservative 12 MiB decoded
and 4 MiB GPU bounds. Admission failure removes or retains only an otherwise
compatible, originally unexpired product; it never renews expiry. Visibility,
offline, disable, superseding selection and the 45 second deadline cancel work.

## Exclusive GFS visualization

Winds and temperature are mutually exclusive; both may be off. Enabling either
in Configuration saves the pair atomically. A partial API update that enables
one turns the other off. Explicitly requesting both true returns HTTP 422.
Legacy both-enabled settings are read as wind only and repaired once under the
publication lock at startup or the next writable read. Repair increments the
revision once and invalidates obsolete model demand; read-only worker reads
normalize without writing. Selection and bulletin settings are preserved.

Wind speed colors use interpolated physical U/V components, then magnitude in
knots. The fixed scale is 0 blue, 25 cyan, 50 green, 75 yellow, 100 orange, 125
red and 150+ purple. Values above 150 knots retain their physical speed; only
their displayed color saturates. The atmosphere legend shows this scale. Unknown
or below-terrain samples stay transparent.

Wind trails show the direction air moves and move faster at higher speeds. Their
motion is illustrative (12,000 times physical displacement), not travel time,
route guidance or a forecast animation. At most 2,000 particles retain 12
samples each; masked areas, resets and generation changes never connect trails
across gaps. Temperature has no particles. Reduced motion keeps the wind raster
and key while removing particle resources; changing the preference does not
fetch another grid.
