# Aviation weather catalog foundation

Implement delivery increment 2 of the reviewed
[issue 290 architecture](2026-10-06-aviation-weather-design.md). The merged
native proofs establish the renderer boundary; this increment establishes its
production API contract. This foundation is implemented together with the
owner-confirmed
[Phase 1 bulletin scope](2026-10-06-aviation-weather-phase-one.md). Scientific
ingest remains in later increments.

## Contract

Add `GET /api/aviation-weather/v1/catalog`. Return schema `aviation-weather-v1`,
UTC epoch milliseconds, settings revision and a bounded list of products.
Product envelopes identify source, provenance, observation/forecast/analysis,
method, validity, model run/lead, vertical selection, coverage generation,
freshness, expiry, attribution, capability hash and instance hash.

Strict Python and browser validators reject contradictory time identities,
unknown schema/representation/units, oversized allocations and unsafe payload
paths. Numerical-model validity equals run plus lead; analysis lead is zero.
Observations retain observation/scan times and never acquire a new age on
refresh. Intervals are half-open. Future observation skew is at most 60 seconds.
Payload paths are immutable, same-origin API paths with hashes and allocation
limits: 16 MiB encoded, 32 MiB decoded and 16 MiB GPU. Grids have at most 720 by
361 nodes, eastward longitude and north-to-south latitude, Int16 fields and the
explicit 0/1/2/3 validity mask. Scientific parsing stays server-side.

## Radar compatibility

Publish one observed-precipitation entry using `xyz-rgba-pair-v1`. Preserve the
existing radar capability identity and tile URLs in an embedded validated
manifest; instance identity includes frame time and coverage generation. Radar
has no immutable single-file payload, so it uses an explicit tile binding. No
tile hashes or single-file allocation claims are manufactured.

Read through the existing weather service and its acquisition pool. Default-off
catalog reads cause no network work. At 20 minutes show stale; at 60 minutes or
coverage expiry remove the binding. Coverage retains `absence-rgba-v1` and
`unknown-not-clear` semantics. Errors remain sanitized, and ASGI disconnect
cancels only the request's lease. Cache-Control is no-store. Core health remains
available if optional weather initialization fails.

## Validation and delivery

Exercise real Python/browser parsers and ASGI routes, including shared pool
deduplication, disable, provider failure, UTC boundaries, changed identities,
invalid payload paths and allocations. Run the existing radar lifecycle tests,
frontend suite and production build. Preserve exact-SHA Nginx/browser acceptance
evidence and stop all task-owned runtime resources. Open a feature PR against
dev and keep its worktree while open. Leave issue 290 open for later increments.
