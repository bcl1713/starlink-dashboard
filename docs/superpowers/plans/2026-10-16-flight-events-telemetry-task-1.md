# Task 1: Establish the live evidence contract and reproduce arrival failure

**Files:** Create tests/integration/test_live_flight_events.py and
app/services/flight_events/models.py; inspect the flight manager, telemetry
model, live collection entry point, Overview service, and deployment storage
settings. Record findings in
docs/reports/2026-10-16-flight-events-live-contract.md in the repository.

**Interfaces:** Define FlightObservation(observed_at, position_observed_at,
speed_observed_at, altitude_observed_at, altitude_validity_source, latitude,
longitude, speed_knots, altitude_feet, altitude_usable, source_mode, mission_id,
leg_id, route_id), FlightEvent(kind, occurred_at, detected_at, source,
confidence, evidence, revision), and DetectionPolicy. Nullable values remain
nullable. Source mode is live or simulation. altitude_usable is true only when
its own source validity and observation freshness pass; fresh position does not
make altitude fresh. Event kinds are off_blocks, takeoff, landed, on_blocks,
correction, and stop_classified.

- [ ] Trace real accepted telemetry into departure/arrival checks, through
      status and upcoming-POI snapshots into Overview. Identify exact ingestion
      call sites and mission binding ownership in the report before editing
      them.
- [ ] Add a failing integration case named test_live_arrival_away_from_endpoint:
      a previously airborne aircraft lands, taxis and stops more than 100 metres
      from the final waypoint; assert the detailed state eventually becomes
      parked and a positive landing countdown is absent.
- [ ] From backend context, run the focused integration test under a 10-minute
      timeout; record the actual failure before changing behavior.
- [ ] Define the typed contracts and synthetic observation fixtures. Preserve
      collection-time provenance: no field claims to represent receiver fix time
      unless the source supplies it.
- [ ] Document altitude validity, speed freshness, airport context availability,
      and active-leg ownership. Synthetic traces prove implementation behavior,
      not field accuracy. If usable altitude or airport context is unavailable,
      specify an uncertain/manual-confirmation path rather than claim automatic
      touchdown accuracy.
- [ ] Run model/fixture tests and commit the evidence contract separately.
