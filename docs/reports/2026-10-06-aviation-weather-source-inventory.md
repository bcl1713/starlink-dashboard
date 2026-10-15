# Aviation weather source inventory

For [issue 290](https://github.com/bcl1713/starlink-dashboard/issues/290), start
with AWC terminal reports and advisories, GFS winds and temperature, and one
GOES infrared channel. WAFS and additional satellite regions remain important,
but access conditions and ingest cost must be established before continuous
operation. The accompanying
[architecture proposal](../superpowers/specs/2026-10-06-aviation-weather-design.md)
defines the normalization and rendering boundary.

## Source access and cadence

Endpoints below are backend acquisition locations. Browser payloads contain only
dashboard-owned URLs. Cadence describes publication, not guaranteed delivery
latency. Dates, cycles, object keys and collection capabilities must come from
validated inventories; never manufacture a latest-file URL.

| Product                 | Authoritative origin and acquisition endpoint                                                                                     | Publication and coverage                                                                  | Access and reuse                                                                                                                       |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| METAR and SPECI         | AWC, `https://aviationweather.gov/data/cache/metars.cache.xml.gz`; CSV also available                                             | Worldwide reporting stations; cache every minute; station reporting differs               | Public endpoint; preserve report type and originating station                                                                          |
| TAF                     | AWC, `https://aviationweather.gov/data/cache/tafs.cache.xml.gz`                                                                   | Worldwide reporting stations; cache every 10 minutes                                      | Public endpoint; retain forecast groups and amendments                                                                                 |
| International SIGMET    | AWC, `https://aviationweather.gov/api/data/isigmet?format=geojson`                                                                | Worldwide advisories, subject to feed completeness; proposed five-minute poll             | Public endpoint; verified directly below; preserve originating issuer                                                                  |
| US SIGMET               | AWC, `https://aviationweather.gov/data/cache/airsigmets.cache.xml.gz`                                                             | CONUS cache every minute                                                                  | Public endpoint; this cache does not establish international coverage                                                                  |
| AIREP and PIREP         | AWC, `https://aviationweather.gov/data/cache/aircraftreports.cache.xml.gz`                                                        | Primarily US and North Atlantic; cache every minute                                       | Public endpoint; sparse reports do not establish absence of hazards                                                                    |
| GFS atmosphere          | NOAA NCEP, `https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl`; public mirror `https://noaa-gfs-bdp-pds.s3.amazonaws.com/`  | Global; four cycles daily                                                                 | NOAA open dissemination; GRIB2 field selection or indexed byte ranges                                                                  |
| WAFS hazards            | WAFC Washington and London through `https://aviationweather.gov/wifs/api/collections`                                             | Global; four cycles daily; time and vertical limits depend on collection                  | Approved WIFS account and authentication required; redistribution rights must be checked for the intended use                          |
| GOES infrared           | NOAA GOES East and West, `https://noaa-goes19.s3.amazonaws.com/`, `https://noaa-goes18.s3.amazonaws.com/`; `ABI-L2-CMIPF` objects | Regional full disks; nominal Mode 6 scan every 10 minutes                                 | Public NODD buckets; NOAA attribution; mark processing modifications                                                                   |
| Meteosat infrared       | EUMETSAT, `https://api.eumetsat.int/data/search-products/1.0.0/os`; downloads through Data Store                                  | Europe, Africa and adjoining oceans; MSG full scan every 15 minutes; collection dependent | Account and dataset-specific licence; near-real-time access must be confirmed; hourly open products do not promise full-cadence access |
| Himawari infrared       | JMA via NOAA dissemination, `https://noaa-himawari9.s3.amazonaws.com/`, `AHI-L1b-FLDK`                                            | East Asia and western/central Pacific; full disk every 10 minutes                         | Public NOAA distribution; credit both JMA and NOAA; mark modifications                                                                 |
| Observed radar baseline | RainViewer, `https://api.rainviewer.com/public/weather-maps.json` and `https://tilecache.rainviewer.com/`                         | Existing regional observation coverage                                                    | Existing adapter and terms remain; linked attribution and no availability guarantee                                                    |
| MRMS regional radar     | NOAA, `https://noaa-mrms-pds.s3.amazonaws.com/`                                                                                   | Regional US enhancement; frequency depends on selected field                              | Public NODD bucket; preserve observation masks and field meaning                                                                       |
| OPERA regional radar    | EUMETNET ORD, `https://api.meteogate.eu/eu-eumetnet-weather-radar/collections/observations`; OPERA location `0-20010-0-OPERA`     | European composites; CIRRUS reflectivity every five minutes                               | ORD composite products CC BY 4.0; individual national volumes have separate terms                                                      |

AWC documents cache schedules, geographic scope and API limits in its
[Data API reference](https://aviationweather.gov/data/api/). Use bulk caches
instead of station-by-station polling. The public API permits at most 100
requests/minute and most queries have a 400-result limit. An international
SIGMET adapter therefore needs an explicit completeness check; a successful
response alone cannot prove a complete worldwide feed.

[NWS reuse terms](https://www.weather.gov/disclaimer/) permit reuse of NWS
material unless otherwise noted, require honest attribution and prohibit implied
endorsement. They do not establish unrestricted rights in every third-party
international bulletin. Preserve issuer attribution and verify any attached
restrictions before redistribution.

For GFS, use the
[NCEP product inventory](https://www.nco.ncep.noaa.gov/pmb/products/gfs/) and
[NOMADS filter](https://nomads.ncep.noaa.gov/gribfilter.php?ds=gfs_0p25) to
identify fields. The
[NOAA GFS registry](https://registry.opendata.aws/noaa-gfs-bdp-pds/) documents
the public bucket, six-hour cycle and reuse conditions. Prefer the 0.25-degree
atmosphere output and extract a small field set; downloading all fields, levels
and forecast hours is outside the proposed budget.

[WIFS access requirements](https://aviationweather.gov/wifs/) require approval
and credentials. Its 0.25-degree icing product covers FL050–FL300 and turbulence
FL100–FL450. Do not label missing levels as zero risk. The
[WIFS guide](https://aviationweather.gov/wifs/users_guide/) describes
`kwbc_wafshzds_blended_ice_0p25` and `kwbc_wafshzds_blended_turb_0p25`, GRIB2
items, and four daily updates. Hazard forecasts stop at T+48. Poll metadata
every 10 minutes around expected arrivals; respect the documented 100
requests/minute, one request/minute per thread and 5,000 data requests/day
limits. Keep access and redistribution as a phase-entry gate; public display
graphics are not evidence of open raw-data access.

The [NOAA GOES registry](https://registry.opendata.aws/noaa-goes/) identifies
GOES-19 and GOES-18 as the current East/West data buckets and provides public
access and attribution terms. The
[ABI instrument reference](https://www.nesdis.noaa.gov/our-satellites/currently-flying/goes-east-west/advanced-baseline-imager-abi)
describes scan modes. Start with channel 13 brightness temperature from CMIP; it
is satellite-observed brightness temperature, not a measured cloud altitude or a
precipitation observation.

[EUMETSAT Data Store restrictions](https://user.eumetsat.int/resources/user-guides/frequently-asked-questions-for-data-store)
require dataset licences for restricted collections and an active NRT licence
for near-real-time MSG/FCI delivery through DSN. The
[data policy](https://www.eumetsat.int/legal-framework/data-policy) is the
licensing authority. [MSG services](https://www.eumetsat.int/msg-services)
describe SEVIRI coverage and cadence. Select an actual collection and record its
licence, channel access and delivery delay before promising an Atlantic/Indian
Ocean satellite service. Do not substitute scraped website imagery.

The [NOAA Himawari registry](https://registry.opendata.aws/noaa-himawari/)
documents public distribution, cadence and attribution. JMA's
[HimawariCloud description](https://www.data.jma.go.jp/mscweb/en/himawari89/cloud_service/cloud_service.html)
estimates 103 GB/day compressed for all 16 full-disk HSD bands; its direct
service requires registration and retains downloads for 72 hours. Prefer the
public mirror and one infrared band; this still needs a measured per-band cost.

[MRMS public dissemination](https://registry.opendata.aws/noaa-mrms-pds/) and
[ORD access and policy](https://eumetnet.github.io/openradardata-documentation/1-ORD-API-overview/)
provide regional candidates. ORD documents open composite licensing and limited
anonymous queries, alongside API-key and notification access options. Its
[query guide](https://eumetnet.github.io/openradardata-documentation/2-ORD-API-discovering-and-accessing-data/)
provides dated OPERA ODIM links. General OPERA licensing pages describe other
delivery arrangements; attach the licence of the actual ORD product. Canada, BOM
Australia and JMA radar adapters are deferred: public websites alone do not
establish raw-product endpoints, redistribution rights or ingest cost. Existing
radar operation is covered by the
[current feature reference](../features/overview-weather.md).

## Verified endpoint snapshots

Bounded HTTPS requests on 2026-10-06 around 11:20 UTC returned the following.
These are source-size measurements, not decode, browser or operational
availability evidence. Data remained in the short-lived request process; no
background ingest service or credential configuration was created.

| Request                           | Result                               | Measurement                                                                              |
| --------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------- |
| AWC METAR CSV cache               | HTTP 200; last modified 11:19:11 UTC | 247,945 compressed bytes; 1,027,303 expanded bytes; 5,242 lines including headers        |
| AWC TAF XML cache                 | HTTP 200; last modified 11:20:27 UTC | 314,863 compressed bytes; 4,912,222 expanded bytes                                       |
| AWC international SIGMET GeoJSON  | HTTP 200                             | 95,231 bytes; 133 features; includes hazard, issuer, FIR, base/top and validity fields   |
| GFS 00Z F006 0.25-degree index    | HTTP 200                             | 40,472 bytes; TMP, UGRD and VGRD at 500 hPa listed                                       |
| GOES-19 channel 13 object listing | HTTP 200                             | One full-disk NetCDF object listed at 23,995,077 bytes                                   |
| Himawari-9 object listing         | HTTP 200                             | One band-1 segment listed at 3,771,059 compressed bytes; this is not an IR size estimate |

Reproducible GFS index:

```text
https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20261006/00/atmos/gfs.t00z.pgrb2.0p25.f006.idx
350:257121490:d=2026100600:TMP:500 mb:6 hour fcst:
356:262465194:d=2026100600:UGRD:500 mb:6 hour fcst:
357:263012887:d=2026100600:VGRD:500 mb:6 hour fcst:
```

Listed satellite keys, relative to their respective buckets:

```text
ABI-L2-CMIPF/2026/279/00/OR_ABI-L2-CMIPF-M6C13_G19_s20262790000209_e20262790009528_c20262790009599.nc
AHI-L1b-FLDK/2026/10/06/0000/HS_H09_20261006_0000_B01_FLDK_R10_S0110.DAT.bz2
```

## Volume estimates and promotion gates

These estimates assume unchanged snapshot sizes and the proposed sampling
policy. They are planning inputs, not peak sizes or provider guarantees.

| Selection                                                                    | Estimated acquisition                                         | Retention and outstanding measurement                                             |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| METAR every five minutes                                                     | 71.4 MB/day using measured CSV size                           | Latest/previous complete snapshots; measure XML size if chosen                    |
| TAF every 10 minutes                                                         | 45.3 MB/day                                                   | Latest/previous snapshot; preserve active forecast groups                         |
| International SIGMET every five minutes                                      | 27.4 MB/day                                                   | Active advisories plus cancellation/amendment lineage; verify truncation behavior |
| GFS U/V/T at eight illustrative pressure surfaces, nine times, four runs/day | 864 messages/day; source bytes require range-size measurement | Two complete runs; measure additional bracketing/surface fields for FL selections |
| GOES channel 13 every 30 minutes, two regions                                | About 2.30 GB/day if both equal the measured East object      | Two normalized scans per region; raw input deleted after validation               |
| WAFS, Meteosat and Himawari IR                                               | No approved continuous-ingest volume                          | Measure exact collection/field bytes under the worker cap before enabling         |

A 1440 × 721 GFS field occupies 4,152,960 bytes as Float32. U/V/T for eight
levels, nine forecast times and two runs would occupy about 1.67 GiB
uncompressed, excluding masks and decoder overhead. Publish quantized fields and
stream source messages rather than holding all runs in RAM. The proposed browser
grid is 720 × 361. Never infer decoder peak RSS from grid size alone.

Require retained immutable input hashes, expanded sizes, peak RSS, CPU/wall
time, output size, mask validation and local renders for each promoted source.
Measure delivery delay from source time to acquisition over at least 48 hours; a
one-time HTTP success supplies no latency distribution or availability SLA.
