# Flight runtime recovery (#423)

The live movement detector and durable archive must be present when live mode is
selected, recover after transient storage initialization failures, and disclose
unavailability without substituting the obsolete endpoint arrival rule. The
production incident's initiating fault remains unconfirmed.

## Approach

Use one application-owned lifecycle around the existing runtime. Reconcile it at
startup, configuration changes and background ticks. Rate-limit failed
initialization with exponential backoff (5 seconds, capped at 60 seconds),
retaining one runtime and existing durable records across mode changes. Keep raw
sample recording, event processing and archive maintenance failure domains
separate. A storage-only permission fix would leave mode changes and recovery
broken; replacing the existing event/archive system would unnecessarily risk its
evidence.

These are implementation choices made to fulfill the requested fix. Preserve the
existing configurable detection policy and capture tail/finalization semantics.
Do not claim aircraft calibration or recovery of this incident's missing traces.

## Behavior and boundaries

- Both POST and PUT config handlers select an actual coordinator for the
  requested mode, rebind API/metric owners, and reconcile recording. Simulation
  data must never enter the live archive. Cancel selected simulation runs on
  config changes.
- Initialization is idempotent; validation occurs before acquiring
  clients/workers, and partial initialization releases acquired resources. Shut
  down owned resources.
- A failed raw sample write must not suppress supported detector observations.
  Failed event persistence must not produce new phase confirmation. Mark
  degraded stages explicitly; a succeeding stage recovers its own health.
- Expose sanitized actionable readiness, failure category and retry state in
  health and a status API. Show detailed messages only in mission planning. Keep
  Overview a distance-readable map with its existing uncertainty treatment.
- An unavailable live detector preserves confirmed phase and marks movement
  uncertain. Never run automatic legacy departure/arrival inference in live
  mode.
- Initialize the archive mount root for appuser without recursively changing
  operational files. Honor custom FLIGHT_ARCHIVE_ROOT, retaining existing data.
- Landing remains inferred from established flight, descent, sustained fresh
  ground-like movement and bounded altitude stability in destination context.
  The existing 10 km destination vicinity is supporting context, not a parking
  radius or a claim of airport boundary accuracy. It is configurable and does
  not require an external airport service. Retain distinct landing, taxi,
  on-blocks.
- Estimated event occurrence and later confirmation stay separate; do not add
  speculative touchdown backdating. Correct times manually in mission planning.
  Repeated stale altitude timestamps must not satisfy landing dwell; sustained
  altitude trends or renewed climb/acceleration must prevent confirmation.

## Validation and delivery

Regression tests cover real POST/PUT/lifecycle transitions, writable/restored
and permanently invalid storage, failed sample/event writes, history and
simulation isolation, and full flight with landing/taxi/parking outside the
endpoint circle. Retain controls for go-around, overflight,
stale/missing/repeated altitude, startup airborne, delayed samples, gaps, holds,
noise and runway slope. Verify phase/ETA, archive boundary/provenance,
unavailable/empty/included exports and planner status. Run required quality
gates and isolated exact-SHA production/browser acceptance; report limitations
accurately. Open a PR against dev; do not deploy or merge.
