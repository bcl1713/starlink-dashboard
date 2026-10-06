# Overview weather detail normalized contract

Interface supplement to the [production plan][plan], implementing the approved
[backend normalization boundary][spec] and [plan-review comment][comment].
Provider discovery, raw formats, tile hostnames and upstream path grammar stay
in backend adapters/transport. Frontend code consumes normalized observed
precipitation products and same-origin API templates only.

## Manifest capabilities and provenance

Extend the existing strict manifest on backend and frontend together:

| Field               | Normalized contract                                                                |
| ------------------- | ---------------------------------------------------------------------------------- |
| `source`            | Nonempty adapter identifier, `[a-z0-9_-]{1,64}`; not a RainViewer enum             |
| `provenance`        | Nonempty description, at most 256 characters, supplied by backend                  |
| `product`           | `observed-precipitation`; excludes forecast/model filling                          |
| `product_id`        | Opaque lowercase SHA-256 hex identity minted by backend                            |
| `tile_schema`       | `xyz-rgba-pair-v1`, including the schema version                                   |
| `coverage_encoding` | `absence-rgba-v1`; missing observations differ from covered zero                   |
| `zoom`              | Fallback level 2                                                                   |
| `max_zoom`          | Integer between fallback and the supported v1 ceiling of 7                         |
| `tile_size`         | 512 for the supported v1 schema and current allocation proof                       |
| `attribution`       | Backend-owned label and HTTPS URL; browser displays, not parses, provider identity |

Advertise these fields in all states; ready state retains the existing UTC
frame, coverage generation/expiry and admitted template fields. Preserve strict
unknown-field rejection and all freshness/settings validation. Capabilities are
values from the normalized manifest: RainViewer initially advertises max zoom 7
and 512px tiles, while a normalized fixture can advertise max zoom 5.

The frontend may know the supported normalized schema and its memory limits. It
must not derive zoom, dimensions, masks or URLs from a source name or provider
path. Unknown schemas, encodings or unsupported dimensions fail before decoding;
adding another tile format or live provider is outside #288. Selection reads
manifest max zoom/tile size; packing and reservations consume validated schema
capabilities. The current 48 MiB proof applies to the selected 512px schema.

Attribution follows the displayed frame's source. Keep the existing RainViewer
link/text for its adapter, supplied through normalized metadata; frontend status
must not apply that attribution to the alternative-source fixture.

## Source-neutral API and cache identity

Retain the existing dashboard route prefixes and UTC frame/coverage tokens. Make
product ownership explicit in the advertised templates:

```text
/api/overview-weather/radar/{frame}/{z}/{x}/{y}.png?product_id={product_id}
/api/overview-weather/coverage/{coverage}/{z}/{x}/{y}.png?product_id={product_id}
```

The backend derives `product_id` from source, provenance, product, tile schema,
coverage encoding and capabilities, independently of the observed frame time.
Radar/coverage templates contain the actual admitted identifier; the frontend
validates the normalized same-origin contract, never upstream URLs. Product IDs
are opaque to the browser. They prevent immutable browser-cache collisions when
a source/schema changes while observation time and XYZ remain identical.

Reject missing/unknown/incompatible product identity and unadmitted frame or
coverage before DNS/acquisition. Acquisition/cache keys include product identity
plus the existing kind/token/z/x/y, preserving coalescing and all size/count
caps. Retain source-appropriate coverage reuse within the same product identity;
do not make coverage downloads repeat solely because radar time advances.
Provider-specific path construction and HTTPS/public-IP/TLS checks remain in the
backend. No generic provider registry or second live adapter is required.

## Frontend interfaces and lifecycle identity

`WeatherCapabilities` in `src/services/overview-weather.ts` is the validated
manifest capability subset: zoom, max_zoom, tile_size, tile_schema and
coverage_encoding. The selector consumes it rather than source-specific
constants. Shared types in `weather-detail-selection.ts` (first three) and
`weather-detail.ts` (last two):

```ts
type DetailKey = { z: number; x: number; y: number };
type CameraSnapshot = {
  projection: readonly number[];
  cameraWorld: readonly number[];
  globeWorld: readonly number[];
  drawingBuffer: readonly [number, number];
};
type DetailDemand = {
  keys: readonly DetailKey[];
  level: number;
  texelPixels: number;
};
type DetailContext = {
  generation: number;
  settingsRevision: number;
  manifest: ReadyWeatherManifest;
};
type DetailPair = {
  context: DetailContext;
  key: DetailKey;
  radar: ImageBitmap;
  coverage: ImageBitmap;
  dispose(): void;
};
```

Produce `detailContextIdentity(context: DetailContext): string` in
`weather-detail.ts`. Its stable tuple includes settings revision/generation,
product ID, source/provenance, product, observed frame time, coverage generation
and expiry, schema/version, encoding and tile dimensions/capabilities. Every
pair/cache/slot carries this identity plus XYZ. Source/schema changes cannot
reuse incompatible detail even when XYZ, time and coverage token match.

The controller compares full normalized identity before its existing same-frame
shortcut. It owns cancellation and displayed-frame metadata: late completions
close bitmaps, incompatible slots are invalidated, and a replacement coarse
frame publishes its own source/provenance atomically. Preserve eligible coarse
fallback and existing freshness/trust rules; source change never resets UTC age
or extends validity. Detail remains tied to the displayed frame rather than a
pending newer manifest.

Regression fixture: `source: fixture-radar`, distinct provenance/product ID, max
zoom 5, supported 512px schema, and only dashboard API templates. Verify
selection stays <=5, all image requests remain same-origin, no source-name
branches/provider URL parsing, correct attribution, and old detail resources are
released when switching from an otherwise matching source. Unsupported schema
rejects before acquisition. This is synthetic architectural validation, not a
second live provider or image-quality comparison.

## Bounded test helpers

Run from the isolated worktree root:

```bash
backend_weather_tests() {
  (cd backend/starlink-location && timeout --kill-after=10s 10m \
    uv run --with-requirements requirements.txt pytest "$@" -q)
}
frontend_weather_tests() {
  (cd frontend/mission-planner && timeout --kill-after=10s 10m \
    npm run test:unit -- "$@")
}
```

[plan]: 2026-10-06-overview-weather-detail-production.md
[spec]: ../specs/2026-10-06-overview-weather-detail-design.md
[comment]:
  https://github.com/bcl1713/starlink-dashboard/issues/288#issuecomment-6008868505
