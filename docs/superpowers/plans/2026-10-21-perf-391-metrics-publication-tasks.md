# Metrics publication implementation tasks

Unstarted tasks for the
[implementation plan](2026-10-21-perf-391-metrics-publication.md). Both written
artifacts require separate approval before execution.

## Task 1: Registry transactions and optimistic capture

**Files:** Create `app/core/metrics/publication.py` and
`tests/unit/test_metrics_publication.py`; modify
`app/core/metrics/prometheus_metrics.py` only to bind the coordinator and
position store. Existing producer wiring waits until Task 3.

**Interfaces:**

- `PublicationCoordinator(registry: CollectorRegistry, position: dict[str, float])`.

```text
commit(batch: PreparedMetricBatch, *, finalize: Callable[[], None] | None = None, rollback: Callable[[], None] | None = None) -> int  # committed even epoch
```

```text
capture(*, max_attempts: int = 3, contention_timeout_seconds: float = 0.05) -> CapturedRegistry  # raises PublicationUnavailable on failure
```

- `mark_dirty(reason: str) -> int` increments input revision and notifies; it
  performs no domain work.
- `CapturedRegistry.collect() -> Iterable[Metric]` yields only detached accepted
  samples.
- `capture_position() -> tuple[float, float, float]` validates the three-value
  position copy using the same epoch/revision/failure protocol, for the
  compatibility table endpoint.

- [ ] Write failing tests `test_capture_never_accepts_mixed_generation`,
      `test_collect_and_serialize_run_outside_mutex`,
      `test_rollback_restores_all_supported_client_state`, and
      `test_failed_undo_quarantines_registry`. Assert old/new tuple equality,
      rejection of a reader spanning an odd epoch, original counter/bucket/sum/
      exemplar/created values after undo, removal only of newly created
      children, and explicit unavailability after restoration failure.
- [ ] Run the new unit file with a hard wall-clock timeout. Confirm assertion
      failures or missing-interface errors establish the intended red state.
- [ ] Implement normalized operation validation, startup shape checks, short
      metadata admission/finalization, outside-mutex journal/application/undo,
      and three-attempt/50-ms capture admission. Use the existing client encoder
      for tests. Do not implement public metric proxies, a new encoder, or a
      persistent sample cache.
- [ ] Add and pass `test_client_floor_and_deployed_histogram_layout`,
      `test_custom_registry_has_independent_epoch`,
      `test_created_and_counter_values_do_not_change_on_read`,
      `test_unknown_collector_shape_fails_closed`, and
      `test_registration_is_sealed_after_initialization`. Test the declared
      client floor and deployed version in separate test environments, recording
      actual versions without changing production dependency manifests.
- [ ] Exercise simultaneous writers, reader retry exhaustion, dirty revision
      during preparation, and smaller transactions failing to clear full-frame
      faults. All waits must release the publication mutex.
- [ ] Commit only Task 1 files after focused tests and formatting pass.

## Task 2: Full frame preparation and read only ETA derivation

**Files:** Create `app/core/metrics/frame_builder.py`,
`tests/unit/test_metrics_frames.py`; modify `app/core/eta_service.py`,
`app/services/eta_calculator.py`, `app/services/eta/projection.py`, and existing
`tests/unit/test_eta_service.py`.

**Interfaces:**

- `FrameInputs` contains detached telemetry/config/route/POIs/flight status,
  optional replay plan/frame, identity, and producer wall/mission clocks.
- `prepare_frame(inputs: FrameInputs, *, admit_observation: bool) -> PreparedMetricBatch`
  performs no registry mutation.
- `prepare_unavailable_frame(inputs: FrameInputs) -> PreparedMetricBatch`
  preserves valid planned/state values and clears observation-dependent values.

```text
derive_eta_metrics(latitude, longitude, speed_knots, active_route=None, eta_mode=None, flight_phase=None, poi_manager=None, *, mission_now=None, pois: tuple[POI, ...] | None = None) -> dict  # read-only counterpart to update_eta_metrics
```

- Existing `update_eta_metrics` remains the accepted-observation operation. Add
  the same optional keyword-only `pois` snapshot argument while preserving all
  existing positional arguments and defaults. Builders supply the captured
  tuple, so neither path rereads managers during calculation. Both capture POIs
  before the ETA computation guard. Derivation copies the calculator's
  smoothing/passage state under that guard, then computes on the detached copy,
  without appending speed. Add keyword-only `track_passage: bool = True` to
  compatibility calculator/projection POI calculation; derivation passes `False`
  to suppress passage mutation/logging.

- [ ] Write failing tests for fresh preflight position with zero speed,
      timed/untimed routes, future/past departure, missing position, in-flight
      stale speed, no route/POIs, and replay mission time. Assert the existing
      150-knot preflight estimate and planned-duration semantics, NaN unknown
      distances, anticipated/estimated labels, and no fictional observed
      position/speed.
- [ ] Run the new frame/ETA tests to establish failure before changing code.
- [ ] Extract existing calculation-to-operation preparation, including all five
      route timing fields and coupled position/phase/progress/POI state. Pass an
      explicit POI snapshot into preparation instead of re-reading managers
      inside the computation guard. Extract position-independent anticipated
      waypoint timing from the existing projection logic without changing
      formulas.
- [ ] Add and pass `test_derived_refresh_does_not_append_speed_or_passage`,
      `test_derived_refresh_preserves_acquisition_and_last_update`,
      `test_unchanged_observation_is_not_observed_twice`, and
      `test_superseded_active_frame_only_is_invalidated`. Keep unrelated
      historical labels, mission clear-helper behavior, and cumulative totals
      unchanged.
- [ ] Confirm preparation creates no registry child, changes no metric, and
      leaves client shapes/buckets unchanged. Commit the cohesive frame/ETA
      change.

## Task 3: Producer and replay integration

**Files:** Modify `app/core/metrics/metric_updater.py`, both metric import
shims, `main.py`, `app/simulation/coordinator.py`,
`app/simulation/run_service.py`, `app/simulation/run_runtime.py`,
`app/mission/leg_activation.py`, and `app/services/ground_entry_point.py`;
extend existing metrics, live-background, replay and mission-activation tests.

**Interfaces:** Existing public updater/clear/service/mission helper signatures
remain unchanged. Add internal
`prepare_metrics_from_telemetry(...) -> PreparedMetricBatch` for replay callers;
its arguments match the current telemetry updater.
`SimulationRunRuntime.checkpoint_publication() -> ReplayPublicationCheckpoint`
and `restore_publication(checkpoint) -> None` preserve previous status, plan,
frame, and start-monotonic state.
`SimulationCoordinator.route_progress_snapshot()` returns optional
`(route_name, progress_percent, waypoint_index)` from its current accepted
observation without advancing it.

- [ ] Write failing tests proving legacy simulation and replay position,
      progress, route timing, phase and ETA enter the same generation. Inject a
      replay finalizer failure both before and after runtime mutation; assert
      the original run revision/clock, coordinator, flight state and registry
      are restored and no success scrape exposes a prepared tick.
- [ ] Run those tests red, then route all existing gauge/counter/histogram
      mutations through coordinator transactions. Remove early progress mutation
      in `_generate_telemetry`; do not call a simulator to fill missing live
      data.
- [ ] Join existing replay collection and leg activation to the prepared batch
      transaction. Keep the epoch odd until runtime finalization succeeds, with
      in-memory replay/flight/coordinator rollback hooks outside the publication
      mutex. Do not run mission writes in the publication section.
- [ ] Group GEP clear/set mutations in one transaction and preserve resolver,
      PoP, identity removal, and network behavior. Keep its observation identity
      independent from telemetry acquisition.
- [ ] Preserve producer duration/error/last-update meanings and all historical
      counter behavior. Publish ordinary disconnection as a complete unavailable
      frame rather than a publication error. A failed full frame remains
      unavailable despite successful GEP or error-accounting transactions.
- [ ] Run existing metrics, live-background ordering/cancellation, replay,
      mission lifecycle, provenance, and archive tests. Search all production
      `.set/.inc/.observe/.remove/.clear` sites for metric objects and verify
      each writer participates. Compatibility test helpers may still manipulate
      private fixture registries outside concurrent runs.
- [ ] Commit after focused regressions pass; HTTP integration is Task 5.

## Task 4: Lifecycle refresh without a new periodic worker

**Files:** Create `app/core/metrics/lifecycle.py` and
`tests/integration/test_metrics_publication_lifecycle.py`; modify `main.py`,
`app/services/route_manager.py`, `app/services/poi/manager.py`,
`app/services/flight_state/manager.py`, `app/api/config.py`, and replay/leg
integration points from Task 3.

**Interfaces:**

- Managers receive optional
  `set_metrics_change_callback(callback: Callable[[str], None] | None) -> None`;
  no callback dependency is required for standalone tests.
- `MetricsRefreshOwner.mark_dirty(reason: str) -> None` records a bounded reason
  set, increments the coordinator input revision, and signals the event loop
  without reading inputs.
- `MetricsRefreshOwner.refresh_without_collection() -> None` is asynchronous,
  captures inputs under existing repository admission and prepares/commits in a
  threadpool; it never calls coordinator collection/update.
- `MetricsRefreshOwner.close() -> None` is asynchronous; close admission before
  draining work and detaching callbacks.
- The normal loop retains an absolute collection deadline; dirty wakes cannot
  move it or count as an accepted update. Disabled-background mode owns at most
  one one-shot drain task and no timer.

- [ ] Write failing parametrized tests for every lifecycle row in the spec:
      route mutation/reload/parse failure, all POI publication and
      bulk/projection/ restore paths, phase and timing-only changes, config
      reset, mission switch/ rollback, replay cancellation, startup, source
      expiry, and shutdown.
- [ ] Include `test_timing_only_correction_refreshes_without_phase_callback`,
      `test_external_poi_reload_refreshes_while_telemetry_is_none`,
      `test_dirty_wake_preserves_next_collection_deadline`,
      `test_disabled_background_coalesces_refresh_and_never_collects`, and
      `test_shutdown_bulk_poi_callbacks_cannot_resurrect_task`. Use explicit
      reload in disabled-background mode for unannounced disk edits.
- [ ] Run the lifecycle file red. Implement only the notification and refresh
      boundaries in the spec. Notifications may occur inside an existing
      repository transaction, but preparation waits until admission can capture
      its final committed/restored inputs. Coalesce nested/bulk notifications.
- [ ] Publish a complete actual/unavailable startup frame after managers are
      ready. Keep production periodic checks running with `telemetry is None` or
      unchanged, so external reloads and planned/countdown values still change.
- [ ] Add source/config/mission race barriers. Assert stale batches cannot
      commit, no lock-order deadlock occurs, and source
      acquisition/replay/smoothing/ event/archive state is untouched by
      refresh-only work.
- [ ] Run lifecycle and existing mutation/recovery tests; verify all owned task
      handles are drained on repeated cancellation. Commit the lifecycle change.

## Task 5: Read only HTTP scraping and complete contracts

**Files:** Modify `app/api/metrics.py`, `app/api/metrics_export.py`,
`tests/unit/test_metrics_export.py`,
`tests/integration/test_metrics_endpoint.py`,
`tests/integration/test_eta_modes.py`; extend new publication tests.

**Interfaces:** `_prepare_metrics(route_manager=None, poi_manager=None) -> str`
and async `get_metrics(...) -> str` retain direct-call compatibility and frozen
probe interception, but ignore old manager arguments. FastAPI no longer resolves
route/POI dependencies for `/metrics`. `PublicationUnavailable` maps to 503;
normal/fallback paths both use validated capture.

- [ ] Write failing 100-scrape sequential/concurrent tests spying on simulator
      construction, ETA construction/calculation, manager lookup/list/get,
      storage writes, replay advancement, smoothing and flight/event state.
      Assert all scraper-side counts are zero and accepted upstream publication
      still changes the exported values as expected.
- [ ] Run them red. Replace scrape preparation with capture, existing client
      serialization, and single EOF handling in the threadpool. Preserve
      health's last-scrape-attempt timestamp, content type, position table
      behavior, and `_prepare_metrics` probe compatibility. Do not fall back to
      raw registry reads.
- [ ] Move old tests that relied on synthetic scrape publication to explicit
      startup/lifecycle/producer fixtures. Retain preflight assertions at the
      new owner; do not simply delete them or blanket-relax finite-value checks.
- [ ] Verify dedicated and custom registry schemas, PositionCollector, all
      metric names/labels/types/buckets, created and counter semantics,
      NaN/unknown, no active mission, empty data, normal/fallback serialization,
      contention 503, and producer-failure recovery. Test two viewers and
      independent scrapers.
- [ ] Run canonical backend/static gates with hard timeouts. Record known
      unchanged failures separately, including the previously documented stale
      Dockerfile tests if still present. Do not claim a green full suite from a
      focused pass. Commit the HTTP change only after its contracts pass.

## Task 6: Measurement, sustained acceptance, rollback and review

**Files:** Create
`tools/acceptance/performance/metrics_publication_diagnostics.py` and
`docs/performance/perf-391-results.md`; update the performance rollup only with
reviewed evidence. Preserve the frozen runner and all original artifacts.

**Interfaces:** The diagnostic tool accepts `--sha`, `--output`,
`--pois {0,10,100,1100}`, `--scrapes`, and `--total-timeout`. It uses isolated
processes and fixture registries to report constructor/calculation counts,
allocation samples, collection retries, actual mutex hold time versus logical
reservation time, and write journal bytes. Never run it inside primary timing
windows. Match original/candidate probe revision for allocation comparisons.

- [ ] Write tool argument/ownership/result-integrity tests before implementing
      the standalone diagnostic. Record its owner, command, PID/group, private
      registry/process lifetime, timeout and cleanup. No production endpoint or
      always-on instrumentation is added.
- [ ] Run the component matrix separately; stop for design review if the undo
      adapter or optimistic retries erase CPU savings or require a different
      client support/API contract. Do not add a byte cache as an unreviewed
      workaround.
- [ ] Verify the retained #390 and #391 inventories before new runs. Preserve
      original images/bundle and use a clean frozen harness checkout for all
      matched system cases. Commit candidate application changes before
      archiving its SHA.
- [ ] Run at least three original and candidate warmed off controls serially,
      then matched counter controls. Also compare candidate with immediately
      preceding dev; never replace the original reference or aggregate unlike
      workloads. Keep successful and rejected comparisons, errors, all samples,
      hardware/browser/dependency identity, and run-to-run ranges.
- [ ] Run matched original/candidate minimum 60-minute steady soaks and separate
      transition/activity controls. Verify finite/NaN meaning, actual 1-Hz
      ingestion, grids and freshness, status/Operator interactions,
      memory/storage slopes, counter monotonicity, and absence of recurring
      task/series growth.
- [ ] Run existing production Docker/Nginx rendered acceptance for Overview and
      Operator, plus mission switch, restart and export under load. Add
      deterministic synthetic-live acquisition/disconnect tests separately from
      the simulation benchmark. State physical-GPU/live-device limitations
      explicitly; do not claim those unexecuted gates passed. The final
      eight-hour integration stays #390.
- [ ] Verify task PID/groups, browser children, listeners, Compose containers,
      networks, and disposable volumes are gone on the host. Preserve evidence
      and open-PR worktree, not runtime resources.
- [ ] Build and test a clean revert candidate for rollback evidence. Revert only
      #391 implementation commits, preserving these documents and evidence.
      There is no schema migration. Document restoration of the old synthetic
      scrape hazard; rollback deployment is not authorized.
- [ ] Record results and limitations, run applicable canonical checks, review
      the diff against latest dev, push the feature branch and open a PR against
      `dev` per repository workflow. Do not merge, modify production deployment,
      or close #391. Keep the worktree for review; remove branches/worktree only
      after a separately authorized merge and verified cleanup.
