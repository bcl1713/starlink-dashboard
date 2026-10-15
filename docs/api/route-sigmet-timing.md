# Route SIGMET timing response

`GET /api/aviation-weather/v1/route-sigmets` now returns the strict
`route-sigmets-v2` schema. Deploy backend and frontend consumers together; v1
snapshots are rejected by the v2 client. Endpoint paths and acknowledgement /
selection request and confirmation bodies are unchanged.

Each geographic entry includes `encounter.spans`, aligned with its existing
geographic spans. Each passage provides `entry_ms`, `exit_ms`, `status`
(`overlap`, `no-overlap`, `unknown`) and a nullable `reason`. Unknown passages
carry null times and a reason: `missing-timing`, `invalid-timing`,
`ambiguous-association` or `unavailable-plan`. The aggregate supplies `status`,
`unknown_count` and `reason`; any known overlap wins while unknown counts remain
visible. Selected-only entries have no invented encounter spans.

The snapshot includes a nullable `encounter_plan` summary with revision, method
`segment-linear-utc-v1`, source, nullable source revision and precision.
`service_instance_id` and monotonic `observation_revision` order captured route
and timing changes within a service lifetime. Compare observation counters only
within the same service instance; obsolete requests remain rejected across
instance changes. Geographic and acknowledgement identity do not change when
only timing changes. Plan point arrays are internal and never serialized.

Passage intervals are closed; advisory validity is half-open. A touch at the
validity start overlaps, and a touch exactly at expiry does not. Calculations
use unrounded milliseconds. Summary display rounds to minutes. Output remains
bounded by the existing 8 MiB response and aggregate point/advisory/span limits.
No altitude status, live-altitude comparison or automatic time filter is added.
