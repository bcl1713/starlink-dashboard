# Task 3: Additive API and departure/arrival presentation

**Files:** Modify backend app/models/flight_status.py, app/api/flight_status.py,
app/models/overview_upcoming_pois.py, app/services/overview_upcoming_pois.py and
corresponding existing tests. Modify frontend
src/services/overview-upcoming-pois.ts, src/pages/overview-arrival.ts,
OverviewArrivalPanel.tsx and their existing tests.

**Interfaces:** Add movement_state, movement_uncertain, movement_observed_at,
off_blocks_at, takeoff_at, landed_at, on_blocks_at, and capture_state as
optional response fields. Existing clients continue using unchanged flight_phase
values. All fields in one Overview response refer to the same mission/leg
snapshot.

- [ ] Add failing backend contract tests for the new fields, absent-field
      compatibility, and consistent mission binding.
- [ ] Add failing frontend cases: taxi out displays taxi status separately from
      scheduled takeoff; supported landing replaces the positive landing
      countdown; taxi in and parked have distinct labels; uncertainty/freshness
      suppress unsupported current-state certainty. Legacy responses retain
      current fallback behavior.
- [ ] Run focused tests to verify failures, then implement additive
      serialization and projection. Reuse the existing observation-age checks;
      do not treat an API refresh timestamp as proof of source freshness.
- [ ] Add authenticated POST
      /api/v2/missions/{mission_id}/legs/{leg_id}/flight-events accepting kind,
      occurred_at and reason, and POST
      /api/v2/missions/{mission_id}/legs/{leg_id}/stops/{stop_id}/classification
      accepting classification and reason. Resolve actor from the existing
      authenticated request context rather than user-supplied text; if this
      deployment has no authentication, use the existing authorized operator
      boundary and document that limit without claiming authenticated identity.
      Add operator controls for off-blocks, takeoff, landed, parked, event-time
      correction, intermediate stop and diversion completion. In this increment,
      show uncertainty and the target event revision; archive impact previews
      are introduced only after the capture service exists in Task 4. Add PATCH
      /api/v2/missions/{mission_id}/legs/{leg_id}/flight-events/{event_id}
      accepting expected_revision, occurred_at and reason. Resolve actor at the
      operator boundary. Validate event ownership and ordering across the leg,
      reject stale expected_revision with a conflict, preserve the original
      event identity and append an immutable correction revision through the
      outbox. Never select a correction target by event kind alone. Add a
      multi-segment leg test that corrects the second landing without modifying
      the first, plus stale-revision and cross-leg rejection tests.
- [ ] Test a wholly manual event sequence with unusable altitude/context,
      including creation of previously absent events, ownership rejection,
      ordering validation and durable outbox persistence. History recovery and
      missing-data assertions belong to Task 4, where the capture service is
      introduced.
- [ ] Run focused backend and frontend tests, then the applicable canonical
      verification tiers. Commit events/display as the first shippable
      increment.
