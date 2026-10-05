# Simulation Speed Plan: Integration Tasks

Read the [main plan](2026-10-05-mission-leg-simulation-speed.md), approved spec,
and [core interfaces](2026-10-05-mission-leg-simulation-speed-core.md). Tasks 1
and 2 must be committed/reviewed before these tasks begin.

## Task 3: API and lifecycle

**Files:** Under `backend/starlink-location/`, create:

- `app/simulation/run_service.py`: serialized
  preparation/start/cancel/collection.
- `app/api/simulation_run.py`: preview and status router, using app-state
  dependencies.
- `app/mission/leg_activation.py`: extracted existing activation transaction.
- `app/services/flight_state/checkpoint.py`: typed complete flight/detection
  snapshot.
- `tests/integration/test_simulation_run_api.py`: HTTP and lifecycle contracts.
- `tests/unit/test_simulation_run_service.py`: failure/collection compensation.

Modify `app/services/flight_state/manager.py`, `app/mission/routes_v2.py`,
`app/mission/dependencies.py`, `app/api/routes/management.py`,
`app/api/config.py`, `app/simulation/coordinator.py`, and `main.py`. Extend
existing V2 activation regression tests; preserve routes, clock overrides,
legacy response fields, and bodyless callers.

**Interfaces:**

- `SimulationRunService`:

  ```python
  SimulationRunService(runtime: SimulationRunRuntime, route_manager: RouteManager, poi_manager: POIManager, coverage_sampler: CoverageSampler | None = None)
  ```

  owns the runtime reference.

- `preview`:

  ```python
  preview(mission_id: str, leg_id: str, pacing: PacingInput) -> SimulationPreview
  ```

  resolves stored inputs under the active-leg boundary.

- `prepare_start`:

  ```python
  prepare_start(mission_id: str, leg: MissionLeg, request: SimulationStart) -> RunTick
  ```

  revalidates mode, token, route, and event plan before side effects.

- `collect`:

  ```python
  collect(coordinator: SimulationCoordinator, publish: Callable[[TelemetryData, RunTick], None]) -> TelemetryData | None
  ```

  prepares a tick, collects telemetry from its frame, invokes publication, and
  commits only on success. It returns `None` for idle/no paced selection; the
  caller then uses existing collection. Completed selection holds its frame.

- `cancel_owned(mission_id: str, leg_id: str | None, reason: str) -> None`,
  `assert_plan_edit_allowed(mission_id: str, leg_id: str | None) -> None`,
  `status() -> SimulationRunStatus`, and `close() -> None` delegate owned
  lifecycle.
- `activate_leg_transaction`:

  ```python
  activate_leg_transaction(mission_id: str, leg_id: str, route_manager: RouteManager, poi_manager: POIManager, clock_settings_store: OverviewClockSettingsStore, run_service: SimulationRunService, simulation: SimulationStart | None = None, coverage_sampler: CoverageSampler | None = None) -> dict
  ```

  preserves the current transaction, uses prepared artifacts for paced starts,
  and commits run last.

- `SimulationCoordinator.update`:

  ```python
  SimulationCoordinator.update(replay_frame: ReplayFrame | None = None) -> TelemetryData
  ```

  uses the frame for paced position and legacy behavior otherwise. Paced
  collection errors propagate to the service; legacy graceful fallback stays.

- `checkpoint_telemetry() -> TelemetryData | None` and
  `restore_telemetry(checkpoint: TelemetryData | None) -> None` on the
  coordinator preserve its last valid observations if a prepared
  tick/publication fails.
- `FlightStateManager.checkpoint() -> FlightStateCheckpoint` and
  `restore_checkpoint(checkpoint: FlightStateCheckpoint) -> None`
  capture/restore status plus every departure/arrival detection field; Task 4
  consumes these.

The router defines the exact endpoints/types in the main plan. Initialize one
runtime/service per process in `main.py`, including live mode; expose them
through app state after startup reconciliation. Wire the existing background
loop as the sole replay producer. Preserve current Uvicorn single-worker
production command; verify actual worker count during acceptance, never claim
cross-worker sharing. Serve selected effective geometry through the run-specific
route endpoint using the existing route-detail serializer; never overwrite the
stored source route.

- [ ] **Step 1: Write failing API/lifecycle tests.** Use a temporary mission,
      route, POI and clock store, injected runtime, and the Task 1 fixture
      builders.

```python
def test_live_mode_rejects_pacing_before_mutation(api_fixture):
    api_fixture.set_mode("live")
    before = api_fixture.lifecycle_snapshot()
    assert api_fixture.preview(multiplier=10).status_code == 409
    assert api_fixture.start_saved_preview().status_code == 409
    assert api_fixture.lifecycle_snapshot() == before

def test_failed_start_preserves_running_leg(api_fixture):
    api_fixture.start_valid_run()
    before = api_fixture.lifecycle_snapshot()
    api_fixture.fail_target_timeline_publication()
    assert api_fixture.start_other_leg().status_code == 500
    assert api_fixture.lifecycle_snapshot() == before

def test_restart_has_new_incarnation(api_fixture):
    old = api_fixture.start_valid_run().json()["simulation_run"]
    api_fixture.restart_service()
    new = api_fixture.get_status().json()
    assert new["runtime_id"] != old["runtime_id"]
    assert new["state"] == "idle" and new["run"] is None
    assert api_fixture.active_leg_count() == 0
```

`test_preview_and_repeated_get_have_no_writes` asserts no producer/cursor
change. `test_changed_plan_token_rejects_before_activation` checks a route/event
edit. `test_start_failure_restores_affected_pois_route_flight_and_flags` injects
failures at persistence, route selection, POI/timeline writes, and first-frame
publication. `test_unavailable_runtime_and_missing_leg_errors` checks 503/404;
strict input tests check 422 detail fields.
`test_bodyless_activation_retains_legacy_contract` covers ordinary simulation
and live paths, including `{}` compatibility.

`test_cancellation_ownership_and_edit_guards` checks active/non-owning mission
deactivation, selected leg/mission deletion, leg updates, route replacement,
timeline-affecting edits, direct route activation/deactivation, simulation
reset, configuration replacement, and mode changes. Reject destructive plan
edits before writes while running; allow ordinary editing after termination.
Direct route or mode selection cancels safely, clearing paced selection before
legacy movement.

`test_publication_failure_is_failed_not_completed` injects first/final
collection and metric-publication errors; last confirmed observation/cursor
stays intact. `test_later_collection_error_preserves_completed_result` keeps an
already finished run completed while independently retaining stale
telemetry/error feedback. `test_many_readers_share_one_producer` runs two
readers and one loop; collection and event counts match the one-reader control.
`test_shutdown_leaves_no_replay_work` checks tasks/timers and leaves independent
services operational until their own stop.

- [ ] **Step 2: Run red.** From backend root:

  ```bash
  uv run --with-requirements requirements.txt pytest tests/integration/test_simulation_run_api.py tests/unit/test_simulation_run_service.py -q
  ```

  expect unmet API/behavior contracts.

- [ ] **Step 3: Implement the interfaces.** Use existing global active-leg lock
      ordering and parent locks. Prepare with no writes, checkpoint affected
      flags, routes, generated POIs, flight state and timeline publication,
      perform existing activation steps, publish the initial frame, then commit
      the runtime. Restore prior state on any earlier failure. Ordinary
      successful activation clears prior paced selection; failed ordinary
      activation preserves it. Add narrow checkpoint helpers to the owning
      stores rather than assigning their private fields here. No synchronous
      lock is held across asynchronous provider/network work.

The background loop calls `collect` with its telemetry/metrics publication
callback and uses deadline-aware delay only while running. A failed collection
must not become a fresh observation. Cancellation stops paced advancement before
switching the coordinator to legacy updates. Config PUT/POST and route lifecycle
paths use the same guards, including same-route changes and coordinator reset.
Update confirmed service mode only after configuration succeeds; reject paced
start whenever actual coordinator/configuration is incompatible with simulation.
Status/preview responses use `Cache-Control: no-store`. The callback receives
the proposed `RunTick` so every published value has its candidate
clock/identity. Restore coordinator/flight checkpoints and clear failed
candidate metrics on publication failure before marking the existing run failed.
Initial start failure compensates to the prior run rather than installing a
failure.

- [ ] **Step 4: Run green and regressions.** Repeat new tests plus
      `tests/integration/test_mission_routes_v2.py`,
      `tests/unit/test_active_mission_context.py`, and
      `tests/unit/test_mission_clock_service.py`; run Task 1/2 contracts too.
      Expected: pass with ordinary activation/compensation and startup flags
      preserved.
- [ ] **Step 5: Commit** `feat: integrate paced run APIs and mission lifecycle`.
