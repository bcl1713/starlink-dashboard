# ADS-B provider acquisition

Issue #296 supersedes the individual included-aircraft lookup described in #244.
Inclusion policy, public settings and `hex:HHHHHH` source status keys remain the
same.

## Verified contract

Verified against public provider documentation and source on 2026-10-06, without
sending aircraft lookup requests to the live provider:

- [adsb.lol OpenAPI](https://api.adsb.lol/api/openapi.json) declares
  `GET /v2/hex/{icao_hex}` (also `/v2/icao/{icao_hex}`), returning the normal
  `now` / `ac` aircraft envelope. It does not declare a batch count limit.
- The
  [provider route implementation](https://github.com/adsblol/api/blob/3c969c84f6f659e1c83715a73cb6c2b6eb1d1d89/src/adsb_api/utils/api_v2.py)
  passes the decoded path value to readsb as `find_hex=<value>`. The
  [ReAPI transport](https://github.com/adsblol/api/blob/3c969c84f6f659e1c83715a73cb6c2b6eb1d1d89/src/adsb_api/utils/reapi.py)
  permits commas in that value.
- [readsb query documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#--net-api-port-query-formats)
  documents comma-separated `find_hex` identifiers and a limit of **1,000**. Its
  [current parser](https://github.com/wiedehopf/readsb/blob/dev/api.c) stops
  parsing at `API_REQ_LIST_MAX`; its
  [current header](https://github.com/wiedehopf/readsb/blob/dev/api.h) defines
  that value as 1,024. Use the smaller documented limit, 1,000, rather than
  relying on an implementation detail that permits more.
- The
  [provider README](https://github.com/adsblol/api/blob/3c969c84f6f659e1c83715a73cb6c2b6eb1d1d89/README.md)
  describes dynamic rate limits based on load, with no fixed requests-per-second
  allowance. The live OpenAPI does not publish a numeric rate allowance either.

These sources establish the batch syntax and a documented underlying limit; they
do not pin the live provider's readsb image or intermediary URL limits. A
deployment may reject a long URL before the underlying count limit. Such errors
follow normal backoff; do not guess a new limit or burst into individual
requests. Recheck the provider contract before changing the cap.

## Acquisition and recovery

Settings validation trims, uppercases and deduplicates six-digit strings without
integer conversion, preserving leading zeroes. Exclusions retain their existing
precedence. Collect the eligible codes for the cycle and make one request, for
example `https://api.adsb.lol/v2/hex/00AB12%2C000002`. Encode each comma once as
`%2C`; `%252C` would transmit an encoded literal instead of a comma. An empty
list makes no included request.

Military collection remains independent. A current position supplied by the
successful military response in this cycle avoids another lookup. A cached
position absent from that response does not. Included-only collection does not
request the military background feed. The existing catalog demand lease can
still temporarily collect the broader catalog, including its existing selection
rules; it uses the same acquisition owner and batching path.

For more than 1,000 eligible codes, split into the minimum number of sequential
chunks. Stop on the first failed chunk. There is no individual lookup fallback.
Included acquisition has one shared exponential failure count and retry deadline
(15/30/60/120/240/300 seconds, or a longer Retry-After). Changes to list
membership, mode or enabled state do not erase an unexpired deadline. Military
acquisition keeps its independent failure state. Separate viewers read one
application-owned cache and do not multiply requests; multiple backend workers
or replicas still require explicit coordination outside this single-worker
runtime.

Transport success updates source acquisition status for all attempted codes.
Missing contacts do not gain positions, observation times or acquisition times.
Only returned valid positions enter the cache, and older duplicates cannot
replace newer observations. Positions are Current below 30 seconds, Stale below
120 seconds and expired at 120 seconds, measured from the provider observation
rather than the time a request succeeded.

## Operator verification

Run the adapter, shared acquisition and controlled HTTP transport tests from
`backend/starlink-location`:

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/unit/test_adsb_lol.py tests/unit/test_overview_adsb_traffic.py \
  tests/integration/test_overview_adsb_batch.py \
  tests/integration/test_overview_adsb_acceptance.py
```

The transport tests inspect `httpx.Request.url.raw_path`, count actual adapter
requests, exercise partial results and errors, and verify chunk boundaries. They
never query live aircraft. Production-path acceptance must use an isolated
Compose project, a clean committed candidate and the controlled provider
fixture. Retain the candidate SHA, image IDs, Nginx API responses and browser
evidence, then stop and verify task-owned resources.

Keep the project User-Agent contact and adsb.lol / ODbL attribution. Provider
production-use expectations still apply; this change does not enable the
feature, deploy it or authorize operational rollout.
