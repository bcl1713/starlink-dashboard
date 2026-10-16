# Route SIGMET timing response

> Release boundary: this page describes post-v1.0.0 development behavior. Route
> SIGMET matching, attention and timing changes landed after the v1.0.0 tag; see
> [release notes](../release-notes.md).

`GET /api/aviation-weather/v1/route-sigmets` now returns the strict
`route-sigmets-v2` schema. Deploy backend and frontend consumers together; v1
snapshots are rejected by the v2 client. Endpoint paths and acknowledgement /
selection request and confirmation bodies are unchanged.

Each geographic entry includes `encounter.spans`, aligned with its existing
geographic spans. Each passage provides `entry_ms`, `exit_ms`, `status`
(`overlap`, `no-overlap`, `unknown`, `passed`) and a nullable `reason`. Unknown
passages carry null times and a reason: `missing-timing`, `invalid-timing`,
`ambiguous-association` or `unavailable-plan`. The aggregate supplies `status`,
`unknown_count` and `reason`; any known overlap wins while unknown counts remain
visible. Passed passages carry null projected times and no reason. An entirely
passed advisory has aggregate `passed` status. Selected-only entries have no
invented encounter spans.

The snapshot includes a nullable `encounter_plan` summary with revision, method
`segment-linear-utc-v1` (pre-departure), `route-estimated-utc-v1` (active
flight), or `mission-replay-utc-v1` (published replay), source, nullable source
revision and precision. `service_instance_id` and monotonic
`observation_revision` order captured route and timing changes within a service
lifetime. Compare observation counters only within the same service instance;
obsolete requests remain rejected across instance changes. Geographic and
acknowledgement identity do not change when only timing changes. Plan point
arrays are internal and never serialized.

Passage intervals are closed; advisory validity is half-open. A touch at the
validity start overlaps, and a touch exactly at expiry does not. Calculations
use unrounded milliseconds. Summary display rounds to minutes. Output remains
bounded by the existing 8 MiB response and aggregate point/advisory/span limits.
Before departure, timing interpolates planned UTC timestamps. In flight, it
anchors at current UTC and current route progress, blends measured and planned
speed on the first remaining segment, and uses planned speeds on future
segments, matching route-aware POIs. Timed points remain usable when optional
timing-summary metadata is absent, regardless of route title. Position and speed
must both pass the existing ten-second freshness policy; unusable live inputs
produce unknown timing instead of a schedule fallback. A currently occupied
passage starts at now and projects its exit. Already completed passages are
marked passed. Published replay uses its mission clock and planned route timing,
matching replay POIs; advisory eligibility remains based on actual UTC.

Live computation is linear in route points plus admitted spans and runs in an
owned worker. Live results receive ordered observation revisions; timing and
progress changes reuse geometry and preserve acknowledgement identity.
