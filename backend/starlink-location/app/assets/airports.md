# Offline airport catalog

`airports.json.gz` is a packaged worldwide airport lookup snapshot downloaded on
2026-10-24 from the public-domain
[OurAirports data](https://ourairports.com/data/), using
<https://davidmegginson.github.io/ourairports-data/airports.csv>.

The snapshot contains 48,103 records. Select all `large_airport`,
`medium_airport`, and `small_airport` rows with finite latitude/longitude in
−90…90 / −180…180. Closed airports, heliports, seaplane bases and balloonports
are excluded. “Active” means not classified as closed by the source; no
operating status is inferred beyond that classification.

Retain source `ident`, `name`, `icao_code`, `iata_code`, `gps_code`,
`local_code`, `municipality`, `iso_country` (as `country`), and coordinates
(`latitude_deg` and `longitude_deg` as numeric `latitude` and `longitude`).
Empty optional identifiers become null. Preserve Unicode names and source
coordinates. Sort by `ident`, encode compact UTF-8 JSON, then gzip with mtime 0.
Runtime lookup strips accents and folds case for search; all query words must
match. Exact identifier matches rank first; other matches sort by name and
identifier. Return at most 20 records. Queries shorter than two characters
return no records. No external lookup occurs at runtime.

To refresh, download the CSV from the source above, repeat this selection and
normalization, and update this file's date, count and source checksum. Preserve
all identifier fields, including ICAO identifiers that differ from the source
`ident`.

Downloaded source CSV SHA-256:

```text
a19e9690fc3bffa8c0af18c4de9a6c8e711e64d4647837c58c12269fe348cf17
```
