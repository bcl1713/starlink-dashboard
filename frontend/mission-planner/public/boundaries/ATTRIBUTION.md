# Overview geographic boundaries

Made with [Natural Earth](https://www.naturalearthdata.com/).
All Natural Earth vector data is [public domain](https://www.naturalearthdata.com/about/terms-of-use/).

## Source and coverage

Both inputs are Natural Earth 1:10 million scale, version **5.1.0**:

- [Admin 0 land boundary lines](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-boundary-lines/):
  [source archive](https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_boundary_lines_land.zip),
  SHA-256 `16ead035f539c8b6c23650c5845d86ad3556553e7456bdf9b4730210f26aacbe`.
- [Admin 1 state/province boundary lines](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/):
  [source archive](https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces_lines.zip),
  SHA-256 `86acd56ce6c0e47f5fa79725591533b5766f26d6ed1437b086f2b8d4028fe456`.

Country borders are shared international land borders, without country fills,
coastline outlines, maritime claims, lease limits, overlay limits, or water
indicators. Subdivisions cover worldwide states, provinces and equivalent
administrative/statistical regions as supplied by Natural Earth. Coverage is
not universal: Antarctica, some disputed areas and small jurisdictions lack
admin-1 boundaries. These generalized reference lines may be outdated and are
not navigation or legal boundary data.

## Disputed boundaries

We preserve the source's default
[de facto boundary treatment](https://www.naturalearthdata.com/about/disputed-boundaries-policy/),
without selecting a country-specific worldview or adding auxiliary claim lines.
Source classifications containing disputed, indefinite, indeterminant,
line-of-control or unrecognized are retained as **dashed** lines. All other
included classifications are solid. This follows source classifications and
does not establish legal sovereignty or identify every disputed boundary.

## Reproducible conversion and runtime availability

Download the two archives as `countries.zip` and `subdivisions.zip` into a
scratch directory, then run from the repository root:

```sh
uv run tools/build-overview-boundaries.py --input-dir /path/to/archives
```

The script verifies the archive hashes, uses pinned pyshp 2.3.1 and Shapely
2.1.2, unwraps longitude before simplification, preserves multipart separation
and line endpoints, simplifies at 0.025 degrees, and rounds coordinates to five
decimal places. It strips labels and unused source metadata; only points and
source-classified disputed flags are shipped. Country data contains 7,920 line
parts / 22,176 points; subdivision data contains 44,943 parts / 114,763 points.

The generated compact JSON files are bundled in the production frontend and
served by the same Nginx origin. There are **no external runtime requests**.
Each dataset loads only when its own switch is enabled, is cached after a
successful load, and is neither polled nor fetched per feature. Disabling a
layer cancels its pending request and releases its GPU resources. Missing,
malformed or over-budget data reports that layer unavailable while leaving
Overview operational.

Runtime limits are 4 MB and 120,000 source points per dataset and 250,000
projected segments per layer. Projection densifies geographic lines at a
maximum 0.5-degree latitude/longitude step, uses the short date-line path and
retains high-latitude parallels. Each layer uses at most four batched draws
(solid and dashed, each with a contrast stroke), with depth testing enabled and
depth writing disabled.
