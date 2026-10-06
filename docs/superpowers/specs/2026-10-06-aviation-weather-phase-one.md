# Aviation weather Phase 1

The owner requested implementation of Phase 1 of issue 290: METAR/SPECI, TAF,
international SIGMET, Configuration preferences and native station/advisory
rendering. Build on the reviewed architecture and catalog foundation. New layers
are independently default-off. Radar retains its settings, acquisition and
renderer. No scientific model ingest or route replanning belongs to this phase.

## Production boundary

Use AWC bulk XML gzip caches for METAR/SPECI and TAF and the international
SIGMET GeoJSON endpoint. A single shared optional service owns acquired,
normalized snapshots; requests lease that work, with cancellation of a reader
leaving siblings alive. Fetch only enabled products when catalog/payload readers
need a refresh; no source work at startup or while all layers are disabled.
Cadences are five minutes METAR/SIGMET and ten minutes TAF. Preserve finite
original freshness/expiry on failures; no retry loops. Share at most two AWC
HTTP exchanges, 20 attempts/minute, a 30-second exchange deadline, 32 MiB
compressed and 256 MiB expanded maximum. In Phase 1 use stricter 8 MiB gzip, 32
MiB expanded, 16 MiB normalizer output and 64 MiB combined retained snapshots.
Published browser collections are capped at 1 MiB per layer. Stations use a
deterministic round-robin selection over ten-degree geographic cells and
disclose omissions as partial feed coverage; oversized advisories fail admission
and keep still-valid prior data. Browser reservations declare four times encoded
JSON for conversion, plus 3.6 MB for advisory tessellation. GPU reservations are
24 bytes per METAR point, 192 bytes per TAF diamond and 1.2 MB for bounded
SIGMET drawing. Admission includes both old and replacement collections. Never
accept user-supplied source URLs; transport uses configured TLS trust.

Normalize station points with SI winds/gusts, visibility, ceiling in meters AGL,
pressure in Pa, temperature/dewpoint in K, raw text and report/issue time. Wind
variable, missing fields and visibility lower bounds are explicit. Retain each
TAF forecast group, change/probability type and BECMG completion instant;
current summaries select the effective prevailing group. Station freshness uses
real UTC: METAR stale at 75 minutes, removed at 120 minutes; TAF source
intervals are half-open. Derive flight category only when visibility and ceiling
allow it; unknown inputs remain unknown. Source absence does not mean clear
weather.

SIGMET keeps issuer/FIR/series/revision, phenomenon, raw text, finite validity,
vertical reference and cancellation/amendment identity, including canonical
bulletin series, issue instant and declared cancellation target interval.
Cross-refresh cancellation matches that identity and preserves later revisions
and unrelated series reuse. Future cancellations take effect at valid-from UTC.
Feed completeness is unknown (400-result query cap cannot establish worldwide
absence). Invalid geometry remains an unlocated textual advisory. Never shade
expired/cancelled features. Validate/split dateline polygons including holes;
bound 500 advisories, 100,000 vertices and 5,000 METAR and 5,000 TAF station
features. Reject excessive source inputs instead of partially claiming a
complete feed. Recent cancellation lineage is bounded to 24 hours; do not drop
an active advisory merely because a refresh fails.

Publish immutable canonical JSON GeoJSON snapshots, SHA-256 IDs, one retained
current and previous snapshot per layer. Payload requests can only name an
admitted instance and known enabled layer; no filesystem/source paths. A
disabled layer invalidates acquisitions and payload access before save
acknowledgement. Store independently revisioned booleans atomically under
data/settings. Catalog and settings are no-store; payloads are private and
revalidated. Sanitize source errors. Shutdown cancels and awaits owned requests
and closes transport once.

## Browser and Configuration

Provide a Configuration card with Terminal weather METAR/SPECI and TAF and
Hazards international SIGMET. Confirm server saves, reflect changes in open
Overview views without reload, and add no Overview controls. Poll settings every
five seconds while visible and catalog every minute while enabled. Limit payload
fetches to three, deadline 45 seconds, encoded/decoded/GPU allocations 16/32/16
MiB including old and candidate snapshots. Abort on disable, hide, offline,
unmount and replacement; release geometries/materials and restore after
recovery.

Consume strict normalized envelopes and feature schemas, with no provider field
parsing in React/Three. Render station category symbols and advisories on the
native sphere above radar and beneath operational markers; preserve holes and
seam handling and tessellate globe edges. Provide passive source/type/UTC
age/validity/legend/attribution status, stale/unavailable state and unknown
coverage. TAF is visibly forecast; SIGMET is an advisory rather than observed
hazard everywhere. Limit station drawing to 5,000 points per overlay.

## Acceptance

Use contract and source fixtures for units, nulls, forecast groups, malformed
geometry, antimeridian, validity, truncation, stale/expiry, concurrent readers,
settings propagation and cancellation. Verify production FastAPI/Nginx and
native globe at desktop/fullscreen/mobile with deterministic transport fixtures;
retain screenshots and exact candidate SHA. Weather errors must leave core
health and globe controls usable. Run existing radar controls and verify scoped
runtime teardown. Keep issue 290 open for Phases 2–6.
