# Overview metric observation provenance — #216 design amendment

## Intent and authority

This amends the approved
[responsive Overview design](2026-09-30-responsive-overview-design.md) for the
first five-panel slice,
[#216](https://github.com/bcl1713/starlink-dashboard/issues/216). The operator
must distinguish measured zero from an unavailable metric. The existing design
requires prominent **latest valid observed** values, gaps rather than invented
points, and one truthful network freshness indicator. Brian chose `/api/status`
as the current-value source; Prometheus remains the history source. This
document defines the missing source contract. Brian approved this written
amendment; implementation is separately gated by the revised #216 plan.

Read-only baseline: `dev` `e8a004db9717d4405e6fab047e9b97932a54872e`. The live
client in `app/live/client.py` currently substitutes `0.0` for absent latency,
downlink, uplink, packet loss and obstruction before timestamping the telemetry.
`/api/status` returns these numbers without provenance; the metric updater
publishes them to Prometheus gauges and histograms. A fresh timestamp cannot
turn a substitution into an observation. Prometheus `query_range` pairs also
carry evaluation times, not guaranteed source-observation times.

## Selected contract and boundaries

1. **Acquisition:** Preserve valid finite values, including **measured zero**.
   For each of the five fields, record whether the source actually supplied a
   usable numeric observation. Missing, null, malformed or non-finite source
   values are unavailable, never an observed zero. Keep this provenance in an
   explicit, typed per-field availability structure on the collected telemetry;
   do not infer it downstream by inspecting value `0.0`. Simulation marks
   generated observations available. If the live API has a distinct validity
   flag for a particular metric, honor it rather than treating mere key presence
   as authoritative; document the accepted source field/validity mapping in the
   implementation plan.
2. **Status API:** Extend the current response additively with per-metric
   availability. For the five current values, return `null` for unavailable
   fields and finite numbers for valid observations, retaining `0` when
   measured. Keep the collection `timestamp` as the age anchor for this batch;
   request time never substitutes for collection time. Other status fields,
   including position and planning state, retain their existing contracts. A
   consumer of an old response lacking the new availability field must treat its
   five values as unverified rather than assuming they are measured.
3. **Prometheus:** For unavailable current metrics, clear the corresponding
   gauge to `NaN` (the project already has a clear-to-NaN path); do not append a
   fabricated zero to any observation histogram. Restore normal finite
   gauge/histogram updates only when that metric is actually observed again. Any
   network health classification that requires absent inputs must say
   unavailable/unknown, not classify fallback zero as healthy. The Overview
   history projector must preserve missing intervals as null gaps in observed,
   average and envelope boundaries; trailing statistics may refer to older valid
   measurements, but must not extend them through a present unavailable interval
   as though current data arrived. Do not change the metric names or
   blanket-disable unrelated position, route, signal-quality or ETA data.
4. **Presentation:** `/api/status` drives five prominent readouts and one
   network-age indicator. A fresh, verified zero displays as zero. If one field
   is unavailable, only that panel lacks a current value and the group reports
   partial availability; all unavailable yields unavailable. A stale sample,
   failed status refresh, absent provenance or future/invalid timestamp cannot
   display a prominent current value; last-known may appear separately with
   clear age and failure wording. A history failure is reported separately from
   status freshness. Keep position freshness independent.
5. **Cadence and scope:** #216 keeps its current five-second shared history
   request default and one-second status request; chart motion must tolerate
   one- and five-second history arrivals. A future **one-second history request
   default** is tracked separately in
   [#224](https://github.com/bcl1713/starlink-dashboard/issues/224) and requires
   the performance investigation in #211. This amendment does not change
   Prometheus scrape interval, query step, retained windows or source
   signal-quality semantics. #217–#220 remain distinct slices.

## Errors and compatibility

An acquisition failure affecting the whole batch keeps the last collected
telemetry timestamp; it must not create a new fresh observation. Partial source
loss is per metric, not a blanket failure of all five. The additive status
contract must be verified against existing callers and export/metric paths;
compatibility values may remain internally where changing typed numeric
consumers would be disproportionate, but **status and Prometheus may never
publish those compatibility placeholders as observations**. Invalid status
provenance is fail-closed in the new UI. No automated migration of historical
zero-valued samples is inferred: older history predates this provenance change
and must not be described as retrospectively verified.

## Acceptance and documentation

- Parameterized live-client tests for each field: measured zero, missing key,
  null, malformed/non-finite value, and recovery. Test explicit source validity
  signals where available; verify simulation's generated values remain valid.
- Status API tests cover finite/zero/null plus provenance, old cached response,
  stale/future timestamp and failed refresh; frontend tests distinguish group
  partial/stale/unavailable and per-panel current versus last-known values.
- Metric-update and history-contract tests prove missing fields clear only their
  gauges, histograms do not record substitutes, observed/average/band traces gap
  and resume without a false zero, and bounded query/poll cadence holds.
- Exact pushed-SHA browser evidence at 1920×1080 exercises measured zero,
  partial loss, recovery, and stale status while the Prometheus plot shows
  genuine gaps. Fixture evidence is not live-backend or sealed #207 evidence.
  Check sustained-load/performance impact separately; do not claim #211 fixed.
- **Documentation impact:** update Overview user guidance and `/api/status`
  response documentation for availability, null values, age and data-source
  distinctions; note the limitation of pre-change history. Update operator
  guidance if a source validity/configuration contract changes. No `main`
  release is authorized.

## Alternatives and rationale

- **Selected:** an explicit per-field source-availability sidecar with nullable
  status output and unavailable Prometheus metrics. This preserves internal
  numeric consumers while preventing fabricated values at the public sources.
- **Nullable numeric domain models throughout:** potentially cleaner in the long
  term, but broadens unrelated metric/ETA consumers beyond #216; revisit only if
  the bounded sidecar cannot guarantee truthful outputs.
- **Frontend zero heuristics or timestamp-only freshness:** rejected because a
  genuine zero is meaningful and a freshly timestamped substitute is still not
  observed.
