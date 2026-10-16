# Task 2: Persistent event ledger and conservative movement detection

**Files:** Create app/services/flight_events/detector.py, store.py,
live_adapter.py and tests/unit/test_flight_events.py; modify
app/services/flight_state/manager.py and checkpoint.py; modify the accepted live
ingestion call sites identified in Task 1.

**Interfaces:** advance_detection(state: DetectionState, observation:
FlightObservation, policy: DetectionPolicy) -> DetectionResult;
FlightEventStore.apply_observation(observation: FlightObservation) ->
DetectionResult; FlightEventStore.correct_event(event_id: str, occurred_at:
datetime, reason: str) -> FlightEvent. DetectionResult contains detailed_state,
uncertainty, emitted_events, candidate_changes, and leg_completion.
candidate_changes contains candidate identity, lifecycle action
(created/reset/confirmed), evidence start and required history start. Persist
candidate state and durable pin references atomically in the event store;
capture buffer garbage collection respects these references even before
confirmed-event delivery. DetectionState persists event candidates and their
observation-time continuity. Stores transact on one observation identity at a
time. Persist every event and an outbox entry in the same SQLite transaction.
The capture consumer acknowledges an event only after idempotently persisting
its work, keyed by event identity and revision; replay unacknowledged entries
after restart.

- [ ] Add failing parametrized traces for
      parked→taxi_out→airborne→landed/rollout→taxi_in→parked, with event
      occurrence time distinct from confirmation time. Assert confirmed events
      retain the beginning of their qualifying evidence interval.
- [ ] Add test cases for go-around, airport overflight, slow airborne motion,
      GPS loss, stale speed, duplicate/out-of-order samples, airport-coordinate
      offset, and absent usable altitude. Assert no invented landing or parking.
- [ ] Add test_dv_offload_then_reposition: after a qualifying destination stop
      and subsequent 45-minute pause, later movement leaves the first on_blocks
      event unchanged. Assert the capture end remains on_blocks + 1800 seconds.
      Add a brief taxi-hold case that resets before confirmation.
- [ ] Add test_fuel_stop_keeps_leg_open and
      test_route_change_preserves_ownership. Away-from-destination parking
      cannot complete the leg; explicit diversion completion can. Restart
      restores confirmed state and resets any candidate whose continuity cannot
      be established.
- [ ] Run tests and record expected failures. Implement the pure detector,
      transactional SQLite ledger, deduplication, and live adapter. Preserve
      existing public phase values; add detailed states separately. No detector
      writes operational routing controls.
- [ ] Set initial policy values only after Task 1 evidence review. Proposed
      engineering defaults for test evaluation: movement above 3 knots for 15
      seconds, airborne above 80 knots for 20 seconds with supporting altitude
      evidence, parking below 1 knot with positions within 50 metres for 300
      seconds. These are configurable, unvalidated defaults, not universal
      aircraft rules. Landing evidence requires prior airborne state, coherent
      descent/leveling, and ground-speed behavior; speed alone is insufficient.
      Missing evidence produces uncertainty. Record the exact selected values
      and rationale in the live-contract report before implementation review.
- [ ] Add manual event correction and stop classification using persisted
      evidence and immutable revision records. Define
      FlightEventStore.record_manual_event(mission_id: str, leg_id: str, kind:
      EventKind, occurred_at: datetime, reason: str, actor: str) -> FlightEvent
      and classify_stop(stop_id: str, classification: StopClassification,
      reason: str, actor: str) -> FlightEvent. Supported stop classifications
      are intermediate and destination_complete. Validate authenticated operator
      identity, mission/leg ownership, timestamp ordering and allowed event
      transitions; reject conflicts explicitly. Manual creation must work when
      no inferred event exists. Feed manual events through the same durable
      outbox. Reconcile existing departure/arrival meanings with all consumers;
      retain their existing meanings and add explicit event timestamps rather
      than silently repurpose fields.
- [ ] Add startup-during-taxi and startup-airborne cases: restore persisted
      events when present; otherwise expose unknown departure/off-blocks and
      request manual historical events. Never derive an actual off-blocks time
      from process startup or route activation; unknown boundaries mean
      incomplete capture. Test fresh position and speed with stale altitude,
      asserting altitude cannot confirm airborne or landed.
- [ ] Run focused state, checkpoint, and flight-status regression tests; commit
      the event subsystem.
