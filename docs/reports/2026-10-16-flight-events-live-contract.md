# Live flight-event evidence contract

## Verified path

Live client get_telemetry collects location, defaults missing altitude to zero,
and assigns collection-time position provenance. Live coordinator replaces speed
with a GPS-position-derived estimate and timestamps it only after a usable
movement sample. Metrics update calls observe_detection, check_departure and
check_arrival. Arrival checks actual distance to the last route coordinate,
requires 100 metres for 60 seconds, and does not use speed. Overview reads the
manager phase, obtains route-aware estimates and formats any positive interval
below a minute as less than one minute. This confirms the endpoint restriction
can keep the phase in flight and permit continued countdown presentation.

The accepted ingestion integration is main.py background metric update. Bind
operational events using resolve_active_mission_leg_context under the repository
active-leg gate; never infer ownership from route name alone. Startup currently
clears active-leg flags, so recovery must retain capture ownership independently
and wait for explicit activation before binding new observations.

## Signal limits

Position times are collection times, not receiver fix timestamps. Speed is
inferred from sequential GPS positions. Altitude lacks validity provenance
today; missing zero must not establish ground state. Add altitude-specific
collection time and finite-value validity at the live source. No
weight-on-wheels signal or verified runway elevation is available. A 10-km route
endpoint vicinity is only an engineering proxy, not a surveyed airport boundary.
Missing or conflicting altitude/context requires uncertainty and manual events.

## Initial policy for synthetic acceptance

Use configurable defaults: movement above 3 knots for 15 seconds; airborne above
80 knots for 20 seconds with a 200-foot climb relative to observed parked
altitude; landing after descent of at least 200 feet from observed airborne
maximum, below 35 knots with altitude stable within 75 feet for 20 seconds;
parking below 1 knot within 50 metres for 300 seconds. Destination vicinity is
10 km. Prior confirmed airborne state is required. These are conservative
software defaults awaiting real-trace calibration, not validated aircraft
operating limits. Unknown initial state cannot invent an off-blocks event.

## Storage and acceptance

Use data/flight-events for ledger and capture data on the existing backend data
volume. Event/outbox/candidate-pin commits are atomic. Capture ownership
survives mission active-flag reset. Keep operational and simulated sources
separate. Synthetic replay establishes algorithm behavior only; field accuracy
remains unvalidated. The first confirmed destination park includes DV offload
and is terminal for automatic arrival even if subsequent repositioning occurs.

## Independent code review and regression fixes

The independent branch review identified three important archive defects. New
regressions first reproduced each failure, then passed after correction:
post-retention event corrections reuse preserved sealed samples; raw extraction
has independent leased interval jobs even with uninterrupted native telemetry;
and incomplete successful query responses retry before a bounded, explicitly
incomplete finalization. Sealed snapshots preserve data while releasing rolling
retention. Missing metrics and raw coverage remain separate manifest fields.

The broad suite exposed a legacy background test that expected route-endpoint
dwell to land without a bound mission. Its assertion now requires uncertainty
rather than inventing an arrival. Synthetic live tests use isolated archive
roots. Rendered/browser acceptance has not been performed: the current execution
environment lacks its provisioned acceptance browser. Field calibration of
inference thresholds also remains outside synthetic verification.
