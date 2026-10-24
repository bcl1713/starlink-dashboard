# ADS-B provider acquisition

The optional aircraft layer uses anonymous
[adsb.fi open data](https://github.com/adsbfi/opendata). No API key, account or
authentication header is required. The provider's
[published terms](https://github.com/adsbfi/opendata/blob/main/README.md) permit
personal, noncommercial use; contact adsb.fi for commercial use. This source was
selected for the dashboard's confirmed personal/noncommercial deployment.
Coverage depends on the worldwide receiver network: aircraft may be absent or
have old positions, and a military classification is provider metadata rather
than a complete inventory. There is no automatic provider fallback.

## Verified contract

On 2026-10-24 anonymous requests to `https://opendata.adsb.fi/api/v2/mil` and an
encoded two-aircraft `/api/v2/hex/HEX%2CHEX` request returned HTTP 200, the
`now`/`ac` envelope, and both requested aircraft in the latter response. `now`
is Unix milliseconds; `seen_pos` is seconds since the position observation.
[API documentation and usage terms](https://github.com/adsbfi/opendata/blob/main/README.md)
publish a **one request per second ceiling**, not a target polling rate.

The adapter retains the conservative **1,000-code** chunk cap from compatible
[readsb query documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#--net-api-port-query-formats).
The two-code live check does not establish the live provider's maximum batch
size or intermediary URL limits; a deployment may reject a long URL earlier.
Such errors follow ordinary backoff, with no individual lookup fallback.

## Acquisition and recovery

The existing scheduler runs every **15 seconds**. Ordinary lists require one
military and at most one included batch per cycle, at most about eight requests
per minute while both sources need acquisition. Included-only mode omits the
military feed unless the existing catalog demand lease requests it. Current
positions returned by military acquisition avoid redundant included lookups;
cached positions absent from the current response do not. Viewers share one
application-owned cache and acquisition owner. Multiple backend workers or
replicas require coordination outside this single-worker runtime.

Settings trim, uppercase and deduplicate six-digit hex strings, preserving
leading zeroes. Exclusions take precedence. Empty lists make no request.
Eligible included codes use one encoded request, for example
`https://opendata.adsb.fi/api/v2/hex/00AB12%2C000002`; commas are encoded once,
not as `%252C`. Larger lists use the minimum number of sequential chunks and
stop on the first failed chunk.

All adapter endpoints and chunks share a lock and at least **1.1 seconds between
request starts**. The limiter spaces acquisition calls; it does not add polling.
Cancellation or a transport failure still consumes the started request's slot. A
valid upstream `Retry-After`, in seconds or HTTP-date form, establishes a
provider-wide cooldown. Calls to either endpoint fail promptly with the
remaining delay during that cooldown instead of waiting through it or retrying
internally.

Included acquisition retains its shared exponential failure deadline
(15/30/60/120/240/300 seconds, or a longer Retry-After), independent of military
source backoff. Changes to list membership, mode or enabled state do not erase
an unexpired deadline or the provider cooldown. Public source keys remain
`military` and `hex:HHHHHH`; public settings and API schemas are unchanged.

Transport success updates source acquisition status for every attempted code.
Missing contacts do not gain positions or observation/acquisition timestamps.
Only returned valid positions enter the cache; older duplicates cannot replace
newer observations. Positions are Current below 30 seconds, Stale below 120
seconds and expired at 120 seconds, based on provider observation time.

## Operator verification

From `backend/starlink-location`, with installed project dependencies:

```sh
timeout --kill-after=10s 10m python -m pytest \
  tests/unit/test_adsb_fi.py tests/unit/test_overview_adsb_traffic.py \
  tests/unit/test_main_overview_adsb.py \
  tests/integration/test_overview_adsb_batch.py \
  tests/integration/test_overview_adsb_acceptance.py
```

Tests use controlled HTTP transports and never query live aircraft. They cover
runtime hostname/prefix, anonymous headers, encoded batching, normalization,
pacing, cancellation, global cooldown, source backoff and cache freshness.
Production acceptance uses `tools/acceptance/adsb/run.sh` with a clean committed
candidate, production Dockerfiles/Nginx and the controlled provider fixture. Set
`ADSB_ACCEPTANCE_PROJECT`, `ADSB_ACCEPTANCE_PORT`, and `ADSB_EVIDENCE_DIR` for a
private run. Retain the SHA, image IDs, API and browser evidence; the runner
removes its containers, networks, disposable volumes and archived source.

Keep the descriptive project User-Agent and adsb.fi attribution/terms link.
