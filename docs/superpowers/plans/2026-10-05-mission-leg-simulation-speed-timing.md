# Simulation Speed Plan: Timing Task

Read the [main plan](2026-10-05-mission-leg-simulation-speed.md), approved spec,
and completed
[API integration](2026-10-05-mission-leg-simulation-speed-integration.md).

## Task 4: Two time domains

**Files:** Create under `backend/starlink-location/`:

- `app/simulation/run_timing.py`: explicit mission-time context and ETA
  projection.
- `app/models/mission_time.py`: shared frozen wire context, independent of
  services.
- `tests/unit/test_simulation_run_timing.py`: real/simulated domain contracts.

Modify `app/services/flight_state/manager.py`,
`app/core/metrics/metric_updater.py`, `app/core/eta_service.py`,
`app/services/eta/calculator.py`, `app/services/eta/projection.py`,
`app/services/active_x_link.py`, `app/services/active_x_handoff.py`,
`app/api/flight_status.py`, `app/api/overview_upcoming_pois.py`,
`app/services/overview_upcoming_pois.py`,
`app/models/overview_upcoming_pois.py`, `app/api/pois/etas.py`,
`app/models/flight_status.py`, `app/api/routes/eta.py`, and Task 3's collection
bridge.

**Interfaces:**

- Frozen Pydantic `MissionTimeContext` in `app/models/mission_time.py` carries
  `runtime_id: str`, `run_id: str`, `revision: int`,
  `simulation_time: datetime`, `observed_at: datetime`,
  `phase: Literal["in_flight", "post_arrival"]`, and
  `effective_multiplier: float`. It imports no runtime/service/flight model,
  preventing circular model imports.
- `mission_time_context`:

  ```python
  mission_time_context(status: SimulationRunStatus) -> MissionTimeContext | None
  ```

  returns context for selected running/completed replay only; completed context
  stays frozen at arrival.

- `planned_poi_eta`:

  ```python
  planned_poi_eta(plan: PreparedMissionRun, frame: ReplayFrame, poi: POI) -> float | None
  ```

  returns simulated seconds to its planned projected time, zero at arrival, and
  truthful unavailable for unusable generated geometry.

- Extend

  ```python
  FlightStateManager.get_status(*, mission_now: datetime | None = None) -> FlightStatus
  ```

  optional context preserves legacy call sites. Add

  ```python
  apply_simulation_frame(plan: PreparedMissionRun, frame: ReplayFrame) -> None
  ```

  use Task 3's complete flight checkpoint for compensation.

- Add optional keyword `mission_now` to the existing ETA service/projection
  operations that use “now”; add optional `sample_time_seconds: float | None` to
  `ETACalculator.update_speed`. Defaults preserve live/ordinary behavior.
- Add optional `mission_time: MissionTimeContext | None` to Overview POI and
  flight-status responses; `calculated_at`/response timestamp stay real UTC.
- Extend `update_metrics_from_telemetry` with optional keyword-only
  `mission_context: MissionTimeContext | None`,
  `simulation_plan: PreparedMissionRun | None`, and
  `simulation_frame: ReplayFrame | None`, each defaulting to `None`. Task 3's
  publisher supplies them from the candidate `RunTick`, not the old snapshot.
- Paced active-X reads return the committed frame's handoff context; legacy
  geographic handoff tracking retains its current semantics and real freshness.

- [ ] **Step 1: Write failing time-domain tests.** Inject a planned departure in
      2025 and a real acquisition in 2026; tick once and pin these assertions:

```python
def test_old_planned_date_does_not_make_telemetry_stale(timing_fixture):
    result = timing_fixture.collect_at_simulated_elapsed(120)
    assert result.position_state == "fresh"
    assert result.flight.time_since_departure_seconds == 120
    assert result.arrival_eta_seconds == 1080
    assert result.real_completion_remaining_seconds == 108
    assert result.telemetry.position.observed_at == timing_fixture.real_now

def test_failed_observation_cannot_renew_age(timing_fixture):
    before = timing_fixture.collect()
    timing_fixture.fail_collection_and_advance_real_time(31)
    assert timing_fixture.position_state() == "stale"
    assert timing_fixture.last_observation() == before.position.observed_at
```

`test_api_estimates_and_metrics_share_simulated_now` compares Overview POIs,
flight status, POI ETA API, route ETA API, and metric projections at the same
frame with adjusted departure and a splice.
`test_simulation_arrival_is_immediate` checks final POST_ARRIVAL without the
live 60-second dwell or initial 10-second speed-persistence delay.
`test_speed_smoothing_uses_simulated_intervals` verifies planned speeds never
appear multiplied; test telemetry acquisition stamps separately.
`test_completed_mission_context_is_frozen_but_real_freshness_continues` checks
terminal elapsed/arrival and real observation timestamps independently.

`test_paced_handoff_reads_do_not_mutate_live_tracker` checks all crossed
transitions and a restarted same leg;
`test_no_context_keeps_live_eta_and_detection_behavior` compares unchanged
defaults. Source silence, future timestamps, invalid positions, and ADS-B TTL
remain governed by the real clock.

- [ ] **Step 2: Run red.** Run

  ```bash
  uv run --with-requirements requirements.txt pytest tests/unit/test_simulation_run_timing.py -q
  ```

  expect domain assertions to fail.

- [ ] **Step 3: Implement the exact context boundaries.** Keep real observation
      and response timestamps; thread mission time explicitly, never replace a
      global clock. Bypass automatic live detection only for selected paced
      frames. Use the prepared route's projected event times for paced
      generated-POI ETAs; preserve live estimators. Fill transport/handoff
      outputs from committed replay state.
- [ ] **Step 4: Run green and regressions.** Run new tests plus
      `tests/integration/test_eta_modes.py`,
      `tests/integration/test_route_eta.py`, `tests/unit/test_eta_service.py`,
      `tests/unit/test_route_eta_calculator_service.py`,
      `tests/unit/test_simulation_availability.py`, and all Task 1–3 tests.
      Expected: pass; no real source-age or live/ordinary ETA/detection
      regression.
- [ ] **Step 5: Commit**
      `feat: keep mission timing coherent during paced replay`.
