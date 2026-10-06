# Overview weather endpoints

All endpoints use `/api/overview-weather`. Settings and manifests use
`Cache-Control: no-store`. Provider failures never redirect clients externally.

## Shared settings

`GET /settings` returns `{ "enabled": false, "revision": 0 }` by default.

`PUT /settings` accepts exactly `{ "enabled": true }` or `{ "enabled": false }`.
Non-boolean, missing, and unknown fields return 422. A changed value increments
the revision. An identical save returns the current revision. A storage failure
returns 503 without replacing the saved file. Disabling cancels and awaits
provider acquisitions before returning success. Settings reads and saves do not
initiate provider traffic.

## Frame manifest

`GET /frame` returns these fields:

| Field                    | Meaning                                                 |
| ------------------------ | ------------------------------------------------------- |
| `state`                  | `off`, `ready`, or `unavailable`                        |
| `settings_revision`      | Current shared settings revision                        |
| `generated_at_ms`        | Real UTC generation time in integer milliseconds        |
| `frame_time_ms`          | Observed frame time in UTC milliseconds                 |
| `coverage_token`         | Current UTC epoch day number                            |
| `coverage_expires_at_ms` | Next UTC midnight in milliseconds                       |
| `source`, `provenance`   | Stable adapter ID and informational display description |
| `product`, `product_id`  | Observed precipitation and stable machine identity      |
| `tile_schema`            | `xyz-rgba-pair-v1`                                      |
| `coverage_encoding`      | `absence-rgba-v1`                                       |
| `max_zoom`               | Advertised ceiling (initial adapter: `7`)               |
| `attribution`            | Display label and HTTPS link for the source             |
| `zoom`                   | Fallback value `2`                                      |
| `tile_size`              | Fixed value `512`                                       |
| `radar_tile_template`    | Local radar URL with `{z}/{x}/{y}` placeholders         |
| `coverage_tile_template` | Local coverage URL with placeholders                    |

For `off` and `unavailable`, frame time, coverage token/expiry, and both
templates are null. Off does not acquire provider data. A ready manifest only
selects validated observed frames less than 60 minutes old, allowing at most 60
seconds of provider clock skew. Previous observations prevent frame regression.

Example ready templates:

```text
/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png?product_id={product_id}
/api/overview-weather/coverage/20732/{z}/{x}/{y}.png?product_id={product_id}
```

Radar URL tokens use seconds; manifest timestamps use milliseconds. Product IDs
include stable source/product/schema/capability fields, excluding provenance
wording and frame time. Both browser URLs and server cache keys carry this
identity so a source change cannot reuse incompatible bytes.

## Buffered PNG tiles

`GET /radar/{frame}/{z}/{x}/{y}.png` and
`GET /coverage/{coverage}/{z}/{x}/{y}.png` require the advertised `product_id`
query parameter. Coordinates must be canonical decimal integers with
`2 <= z <= max_zoom` and `0 <= x,y < 2**z`; leading zeros, signs and fractional
representations are rejected before DNS. They return a validated 512-square
`image/png`, without streaming unchecked provider bytes. Radar responses use
private 600-second immutable caching. Coverage uses private caching for up to
300 seconds with revalidation, shortened to its original expiry. Disable and
token eligibility are checked before server cache access.

| Status | Meaning                                                          |
| ------ | ---------------------------------------------------------------- |
| 400    | Invalid tile coordinates                                         |
| 404    | Missing/unknown product or departed/expired frame/coverage token |
| 409    | Weather disabled                                                 |
| 503    | Provider, settings, admission, or validation unavailable         |

503 responses include sanitized bounded `Retry-After` where applicable.
Disconnecting a caller releases only its own acquisition lease. Another caller
for the same key continues; the last subscriber cancels the provider stream.
Shutdown and repeated close share cleanup ownership.

See [Overview weather operation](../../features/overview-weather.md) for
freshness, budgets, persistence, and data-source limitations.
