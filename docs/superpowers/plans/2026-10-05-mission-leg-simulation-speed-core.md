# Simulation Speed Plan: Core Tasks

Read the [main plan](2026-10-05-mission-leg-simulation-speed.md), wire contract,
and both approved spec documents first. These tasks establish the contracts used
by [integration](2026-10-05-mission-leg-simulation-speed-integration.md).

## Task 1: Pacing and effective plan

**Files:** Create the following backend files under
`backend/starlink-location/`:

- `app/models/simulation_run.py`: closed request/response models from the main
  plan.
- `app/simulation/run_plan.py`: validation, normalization, and content identity.
- `app/mission/timeline_preparation.py`: pure timeline artifacts and effective
  route.
- `tests/unit/test_simulation_run_plan.py`: numerical, route, and preview
  contracts.
- `tests/unit/simulation_run_fixtures.py`: shared injected clocks and timed-leg
  data.

Modify `app/mission/timeline_service.py` and
`app/mission/timeline_builder/pois.py` to delegate shared calculation and
separate POI construction from publication. Preserve `build_mission_timeline`'s
existing signature, returned tuple, POI behavior, and caller tests.

**Interfaces:** All paths below use the same backend root.

- `simulation_run.py` produces `PacingInput`, `NormalizedPacing`,
  `SimulationPreview`, `SimulationStart`, `ActivationRequest`, `RunSnapshot`,
  and `SimulationRunStatus`, exactly matching the main plan.
- `timeline_preparation.py` produces frozen `TimelineArtifacts` with effective
  `route: ParsedRoute`, `projector: RouteTemporalProjector`,
  `events: tuple[MissionEvent, ...]`, `timeline: MissionLegTimeline`,
  `summary: TimelineSummary`, and `generated_pois: tuple[POICreate, ...]`.
- `prepare_mission_timeline`:

  ```python
  prepare_mission_timeline(mission: MissionLeg, route_manager: RouteManager, poi_manager: POIManager | None = None, coverage_sampler: CoverageSampler | None = None, parent_mission_id: str | None = None, include_samples: bool = False) -> TimelineArtifacts
  ```

  reads sources and never writes POIs/files/runtime state. Add keyword-only
  `normalize_for_simulation: bool = False`; the paced preparation passes `True`,
  and the legacy wrapper retains `False`.

- `publish_mission_pois`:

  ```python
  publish_mission_pois(artifacts: TimelineArtifacts, poi_manager: POIManager, mission_id: str, route_id: str) -> None
  ```

  owns the existing generated-POI replacement and satellite cleanup; called only
  by mutation paths.

- `normalize_pacing`:

  ```python
  normalize_pacing(pacing: PacingInput, duration_seconds: float) -> NormalizedPacing
  ```

  preserves precision and enforces the approved limits.

- Frozen `PreparedMissionRun` carries `mission_id`, `leg_id`, `route_id`
  (strings), `artifacts`, normalized pacing, `preview: SimulationPreview`,
  `replay_events: tuple[MissionEvent, ...]`, and a privately owned route/event
  copy. Replay events preserve pre-start clamping and events at arrival; events
  strictly after arrival are outside the flight. Preserve canonical equal-time
  order when constructing this schedule.
- `prepare_mission_run`:

  ```python
  prepare_mission_run(mission_id: str, leg: MissionLeg, pacing: PacingInput, route_manager: RouteManager, poi_manager: POIManager, coverage_sampler: CoverageSampler | None = None) -> PreparedMissionRun
  ```

- `SimulationValidationError(field: str, message: str)` identifies semantic
  validation errors; Task 3 maps these to field-specific 422 responses.
- Test helpers `multiplier_input(value: float) -> PacingInput` and
  `target_input(value: float) -> PacingInput` construct validated requests.

- [ ] **Step 1: Establish the baseline.** After plan approval, set up the
      declared runtime and run `./tools/verify backend` and
      `./tools/verify frontend` before product edits. Expected: both existing
      gates pass; record environment failures separately and preserve a
      comparable baseline.

- [ ] **Step 2: Write failing contract tests.** The fixture factory creates a
      valid 1200-second, three-point route with an adjusted departure, two timed
      speeds, canonical transition/outage events, and optional feasible splice.
      Inject monotonic/UTC clocks independently. Pin these representative
      assertions:

```python
def test_120_seconds_matches_10x(timed_leg):
    a = normalize_pacing(multiplier_input(10), 1200)
    b = normalize_pacing(target_input(120), 1200)
    assert a.effective_multiplier == b.effective_multiplier == 10
    assert a.expected_runtime_seconds == b.expected_runtime_seconds == 120

def test_preview_is_read_only_and_stable(preview_fixture):
    a = preview_fixture.prepare()
    b = preview_fixture.prepare()
    assert a.preview.plan_token == b.preview.plan_token
    preview_fixture.assert_no_poi_file_route_clock_or_runtime_writes()

def test_adjusted_effective_route(preview_fixture):
    plan = preview_fixture.prepare(with_splice=True)
    assert plan.artifacts.projector.start_time == preview_fixture.adjusted_departure
    assert plan.artifacts.route == preview_fixture.expected_effective_route
```

Add parametrized tests named `test_strict_pacing_rejects_invalid_input` for
booleans, numeric strings, NaN/infinity, zero/negative values, both modes,
unknown keys, multiplier 0.099/1000.001, and runtime 0.999. Accept exact
0.1/1000/1 limits when the derived multiplier is valid. Test unsupported target
derivation without clamping; no division underflow/overflow accepted as a valid
run.

`test_rejects_invalid_effective_timing` covers untimed/zero-duration routes,
decreasing/equal conflicting anchors, nonfinite coordinates, zero distance,
timing outside the declared flight window, and contradictory segment speeds.
`test_sparse_anchors_share_timeline_interpolation` pins duration-based gaps.
`test_plan_token_changes_only_with_semantic_inputs` covers route/events/pacing
edits while excluding newly generated POI IDs and creation timestamps.

- [ ] **Step 3: Run red.** From the backend root:

  ```bash
  uv run --with-requirements requirements.txt pytest tests/unit/test_simulation_run_plan.py -q
  ```

  Expect missing new contracts or failing assertions; record the actual cause.

- [ ] **Step 4: Implement the defined contracts.** Reuse the current rule engine
      and effective-route preparation once; separate all satellite/POI deletions
      and writes from pure calculation. Canonical events preserve Python's
      stable sort insertion order for equal timestamps. Freeze/copy accepted
      artifacts; preview cannot mutate cached source routes or depend on the
      current aircraft position. On the private paced route, retain explicit
      ordered time anchors and add declared departure/arrival endpoint anchors;
      fill intervening missing timestamps by cumulative distance within their
      bounding anchors. Feed this same normalized copy to event generation and
      `RouteTemporalProjector`, avoiding a discontinuous whole-flight fallback
      in the middle of an anchored segment. Reject conflicts; zero-distance
      timed segments remain stationary rather than dividing by zero. Stored
      routes and legacy preparation are unchanged.
- [ ] **Step 5: Run green and regressions.** Repeat the focused command plus

  ```bash
  uv run --with-requirements requirements.txt pytest tests/unit/test_mission_timeline.py tests/unit/test_mission_generated_pois.py tests/unit/test_mission_state.py tests/unit/test_timing_aware_simulation.py -q
  ```

  Expected: all pass; legacy returned timeline/statistics and POIs remain equal.

- [ ] **Step 6: Commit** `feat: prepare validated paced mission runs` using only
      the listed product/test files. Review this task before continuing.

## Task 2: Replay runtime

**Files:** Create under `backend/starlink-location/`:

- `app/simulation/run_runtime.py`: transactional owner and lifecycle revisions.
- `app/simulation/run_replay.py`: clock-to-position and event-state projection.
- `app/mission/replay_state.py`: shared incremental transport-condition reducer.
- `tests/unit/test_simulation_run_runtime.py`: deterministic runtime contracts.

Modify `app/mission/state.py` to share reducer semantics with replay; retain
existing interval output. Use Task 1's models, prepared plan, and fixtures.

**Interfaces:**

- Frozen `ReplayFrame` carries `simulation_time: datetime`,
  `position: PositionData`, `progress_percent: float`, `phase: FlightPhase`,
  `transport_states: dict[Transport, TransportState]`,
  `processed_event_count: int`, `x_context: ActiveXContext`, and private
  `reducer_state: TransportReplayState` for overlapping active conditions.
- `TransportReplayState` and

  ```python
  apply_transport_event(state: TransportReplayState, event: MissionEvent) -> TransportReplayState
  ```

  live in `app/mission/replay_state.py`. Share them with `app/mission/state.py`;
  replay does not reduce from status labels.

- `project_run_frame`:

  ```python
  project_run_frame(plan: PreparedMissionRun, simulation_time: datetime, previous: ReplayFrame | None) -> ReplayFrame
  ```

  computes movement and consumes only events after the previous cursor. Share
  transport reducer functions with the planning state machine; preserve its
  pre-start event clamping.

- `SimulationRunRuntime`:

  ```python
  SimulationRunRuntime(monotonic: Callable[[], float], utc_now: Callable[[], datetime], service_mode: str)
  ```

  owns one incarnation.

- `prepare_start(plan: PreparedMissionRun) -> RunTick` returns an uncommitted
  departure frame and new run ID, leaving the existing run intact.
- `prepare_tick() -> RunTick | None` computes the current running frame without
  publishing or advancing its committed cursor; terminal/idle returns `None`.
- Frozen `RunTick` carries `expected_revision: int`, `plan: PreparedMissionRun`,
  `frame: ReplayFrame`, and proposed `status: SimulationRunStatus`.
- `commit_tick(tick: RunTick) -> SimulationRunStatus` validates its revision and
  atomically installs the frame/cursor/snapshot. No external writes inside it.
- `cancel(reason: str) -> SimulationRunStatus`, `clear_selection() -> None`,
  `fail(code: str, message: str) -> SimulationRunStatus`,
  `status() -> SimulationRunStatus`, `frame() -> ReplayFrame | None`,
  `selected_plan() -> PreparedMissionRun | None`, and
  `seconds_until_next_tick() -> float` expose the owned state.
- `set_service_mode(mode: Literal["simulation", "live"]) -> None` changes the
  confirmed mode/revision after accepted configuration changes, cancelling any
  incompatible run. `frame`/`selected_plan` return `None` when
  idle/cancelled/failed; snapshots retain terminal context independently.
- `seconds_until_next_tick` uses the smaller of one real second and remaining
  deadline time; never busy-spins after a terminal state. Reads never tick.

- [ ] **Step 1: Write failing deterministic runtime tests.** The helper
      `tick_and_commit(runtime)` prepares and commits one tick without external
      work.

```python
def test_runtime_uses_monotonic_clock(runtime, clocks, plan_10x):
    runtime.commit_tick(runtime.prepare_start(plan_10x))
    clocks.advance_monotonic(12)
    clocks.jump_utc(-3600)
    tick_and_commit(runtime)
    assert runtime.status().run.simulation_time == (
        plan_10x.artifacts.projector.start_time + timedelta(seconds=120)
    )

def test_completion_holds_exact_endpoint(runtime, clocks, plan_120s):
    runtime.commit_tick(runtime.prepare_start(plan_120s))
    clocks.advance_monotonic(120)
    tick_and_commit(runtime)
    assert runtime.status().state == "completed"
    assert runtime.frame().progress_percent == 100
    assert runtime.frame().phase == FlightPhase.POST_ARRIVAL
    position = runtime.frame().position
    endpoint = plan_120s.artifacts.route.points[-1]
    assert (position.latitude, position.longitude) == (endpoint.latitude, endpoint.longitude)
    assert runtime.prepare_tick() is None

def test_reads_do_not_process_events(runtime, clocks, running_fixture):
    before = runtime.status()
    clocks.advance_monotonic(10)
    assert runtime.status().revision == before.revision
    assert runtime.status().run.processed_event_count == before.run.processed_event_count
```

Tests named `test_all_crossed_events_are_processed_once` and
`test_simultaneous_events_keep_canonical_order` compare emitted event IDs and
transport/handoff state to a full reference reducer, including pre-start,
departure/end events, two X transitions in one tick, and overlap/outage
recovery. Expose processed event IDs to tests through an injected reducer
observer; keep only counts/state in production snapshots.
`test_uncommitted_tick_is_invisible` asserts old cursor/snapshot remains
published; `test_stale_tick_cannot_commit` rejects a tick superseded by
cancellation or a new run.

`test_segment_speed_is_per_simulated_second` covers different timed segment
speeds, sparse anchors, antimeridian interpolation, 0.1× and 1000× without noise
or overshoot. `test_terminal_error_does_not_certify_completion` preserves the
last observation/time/cursor; `test_late_completion_reports_actual_lateness`
uses a 125-second publication for a 120-second target and expects five seconds.
`test_same_leg_restart_has_new_cursor_and_handoff_state` starts again at zero.

- [ ] **Step 2: Run red.** From backend root:

  ```bash
  uv run --with-requirements requirements.txt pytest tests/unit/test_simulation_run_runtime.py -q
  ```

  expect the new runtime missing or contract assertions failing, not
  environment/import failures elsewhere.

- [ ] **Step 3: Implement the interfaces.** Use the prepared temporal projector
      and its longitude interpolation; clamp final sampling without calling the
      wrapping legacy follower. Event reducer state belongs to the prepared
      tick; keep event identity/ordinal and bounded cursor rather than a growing
      history. Treat snapshot publication as the commit point for processing and
      completion.
- [ ] **Step 4: Run green.** Repeat Task 1/2 focused tests and
      `tests/unit/test_mission_state.py`; expect all pass, including a
      full-reference comparison at every event boundary and random bounded
      monotonic tick gaps.
- [ ] **Step 5: Commit** `feat: replay paced mission time and canonical events`.
      Review core interfaces against the main plan before API integration.
