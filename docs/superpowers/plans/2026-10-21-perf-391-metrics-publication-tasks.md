# Gauge snapshot implementation tasks

Part of the [revised plan](2026-10-21-perf-391-metrics-publication.md). Tasks
1–5 have passed their mandatory review checkpoints. Task 6 verification is
underway; its
[availability-harness checkpoint](../../performance/perf-391-task-6-availability-checkpoint.md)
does not complete performance or sustained acceptance.

## Task 1: Snapshot foundation and compatibility checkpoint

**Files:** Create `app/core/metrics/frames.py`,
`tests/unit/test_metrics_frames.py`, and
`tests/unit/test_metrics_frame_views.py`. Production registration/writers are
not changed in this task.

**Interfaces:** `GaugeDefinition(name, documentation, labelnames)` is frozen
metadata. `GaugeFrame(identity, families, last_observation_publication_time)`
contains immutable family/sample tuples. `FrameIdentity` contains mode,
coordinator/observation/route/POI/phase identity, input revision and optional
replay runtime/run/revision/mission time.
`PublicationState(frame, status, reason)` is the immutable published head.

```text
FrameStore.read() -> PublicationState
FrameStore.publish(expected: PublicationState, frame: GaugeFrame) -> bool
FrameStore.invalidate(reason: str) -> PublicationState
FrameStore.fail(expected: PublicationState, reason: str) -> bool
TelemetryFrameCollector(store, schema).collect() -> Iterable[Metric]
TelemetryFrameCollector(store, schema).describe() -> Iterable[Metric]
FrameGaugeView(store, definition, labelvalues=()).labels(*args, **kwargs)
FrameGaugeView.set(value) -> None  # writes only to current preparation builder
FrameGaugeView.collect() -> Iterable[Metric]  # read-only single-family view
```

`publish` and `fail` compare the expected head; an obsolete calculation cannot
invalidate or overwrite a newer successful frame. `invalidate` changes input
revision/status without mutating stored values. No callback is accepted in the
pointer swap. Masking, collection and schema validation happen outside the
mutex.

- [ ] Write failing tests `test_old_frame_survives_pointer_and_label_change`,
      `test_reader_paused_between_families_sees_one_frame`,
      `test_all_29_schemas_and_position_alias_match_baseline`,
      `test_labels_bind_without_visible_child`, and
      `test_superseded_prepare_cannot_publish_or_fail_new_head`.
- [ ] Run these new tests with the focused command in the plan, confirm the
      intended failures, then implement the smallest store/collector/view. Use
      only public GaugeMetricFamily/registry APIs and immutable scalar data.
- [ ] Test positional/keyword labels, preparation-context writes, read views,
      aborted builders, duplicate-label last-write behavior, custom registries,
      same-object re-exports, and explicit rejection of standalone coupled
      writes. Audit every operational caller; do not emulate `_value`/`_metrics`
      or retain unregistered mutable Gauge copies.
- [ ] Test standard independent Counter/Histogram objects, label initialization,
      buckets/count/sum/exemplars/created series, and a read-only independent
      callback collector. Snapshot abort must neither restore nor repeat their
      operations. Add lock assertions proving all family construction and
      serializer work runs outside the mutex.
- [ ] Run at client 0.19.0 and deployed version; separately measure
      0/10/100/1100 POIs, one writer and concurrent readers, preparation CPU,
      pointer cost, allocations and retained frames. There must be no
      frame-history queue, whole-registry retries, or mixed coupled values.
- [ ] Commit the tested foundation, then **stop for go/no-go review**. Report
      compatibility changes and remaining limits before touching production
      producer, replay or lifecycle paths. The existing design probe does not
      replace tests using the actual schema and import surface.

## Task 2: Authoritative coupled gauges and ETA preparation

**Files:** Modify `app/core/metrics/prometheus_metrics.py`,
`app/core/metrics/metric_updater.py`, both metric import shims,
`app/core/eta_service.py`, `app/services/eta_calculator.py`,
`app/services/eta/projection.py`; create `app/core/metrics/frame_builder.py`.
Extend existing metric/ETA tests and `tests/conftest.py` after checkpoint
approval.

**Interfaces:** `FrameInputs` carries detached source/config/route/POI/phase
inputs and expected publication head.
`prepare_frame(inputs, admit_observation: bool) -> GaugeFrame` calculates all
coupled values without changing current state. The builder preparation context
is the sole target of coupled handle setters; it seals a complete validated
frame or discards all work. `prepare_unavailable_frame(inputs) -> GaugeFrame`
preserves applicable planned/state values and the old successful-observation
timestamp.

- [ ] Add failing tests for the 29-schema registry wiring, position alias and
      canonical `REGISTRY.get_sample_value`, no duplicate registration/state,
      and fixture reset without private Gauge/dictionary writes. Run red.
- [ ] Replace only the 29 coupled Gauge definitions with frame-backed handles.
      Register one full collector after the schema is complete; keep all 18
      independent Gauges, seven Counters and four Histograms unchanged. Keep
      named helper/import signatures and PositionCollector output. Convert
      `_current_position` into a read-only view; no second position dictionary.
- [ ] Prepare all coupled fields together, including five route timing values,
      source mode and original last-update meaning. Known unavailable optional
      fields become NaN in a complete frame, not an early partial publication.
      Do not reclassify per-mission/GEP instruments into this frame.
- [ ] Add a read-only `derive_eta_metrics` counterpart to `update_eta_metrics`
      with the same arguments plus keyword-only `pois` snapshot. Add optional
      keyword-only `pois` to the existing updater as well. Capture POIs before
      its computation guard; derive from detached smoothing state without speed
      append. Add `track_passage: bool = True` to calculator/projection POI
      calculation; refresh-only work passes `False`.
- [ ] Pass timed/untimed, future/past departure, fresh zero speed, missing
      speed/ position, in-flight stale inputs, anticipated/estimated labels, and
      replay clock tests. Preserve the existing 150-knot preflight fallback and
      planned duration behavior without inventing observed coordinates/speed.
- [ ] Assert failed builders publish no new labels/zeros, invalidation touches
      only the directly superseded frame, and derived refresh adds no counts,
      observations, detector/clock changes, or successful-observation timestamp.
      Run focused metric/ETA tests, then commit.

**Registration transition, approved review conditions:** Pull the pure
`metrics_export.py` serialization change forward from Task 5 before collector
registration. Mechanically include timestamp/progress in the accepted updater
and remove their standalone main/coordinator setters; preserve existing replay
callback/commit ordering until Task 3. Capture the position mapping once for the
position-table response. Full source admission, lifecycle notifications and
HTTP/health behavior remain later tasks. See the checkpoint for exact scope.

## Task 3: Source and replay publication ordering

**Files:** Modify `main.py`, `app/simulation/coordinator.py`,
`app/simulation/run_service.py`, `app/mission/leg_activation.py`, and updater
integration from Task 2. Do not change replay runtime algorithms/checkpoints or
GEP internals. Extend existing live-background and simulation-run tests.

**Interfaces:** `prepare_metrics_from_telemetry(...) -> GaugeFrame` matches
existing updater inputs and stages instead of publishing. Existing public
`update_metrics_from_telemetry(...) -> None` remains the accepted producer entry
point. `route_progress_snapshot()` returns current simulation progress without
advancing the coordinator. The replay callback returns a prepared frame; its
owner publishes only after successful existing `commit_tick`.

- [x] Write failing normal/live/replay tests for same-frame position, mode,
      route progress, timing, phase and POI values. Pause preparation across
      source/config replacement and ensure the stale result is rejected.
- [x] Remove early coordinator progress writes. Include progress in the accepted
      frame, preserve original source timestamps, availability and accounting,
      and publish a truthful unavailable frame on ordinary disconnect.
- [x] Stage the replay gauge frame during the existing callback; keep it private
      until runtime commit returns successfully under existing repository
      admission, then perform the already validated pointer swap. On failure,
      discard it and use the existing failed-run/activation recovery path plus
      unavailable publication. Add no metric journal or new runtime checkpoint.
- [x] Test failures before runtime commit and in the existing runtime commit
      path: no success scrape may expose the prepared gauge frame. Preserve
      existing independent per-mission instrument semantics and run-clock
      behavior; do not claim they share aircraft acquisition generations.
- [x] Verify one observation-accounting call per accepted sample. A CAS loss or
      derived refresh may rebuild gauges but never repeat histogram/counter
      operations. Run existing live-background ordering/cancellation, replay,
      mission, provenance and archive regressions; commit the integration.

## Task 4: Exact lifecycle refresh ownership

**Files:** Create `app/core/metrics/lifecycle.py` and
`tests/integration/test_metrics_publication_lifecycle.py`; modify `main.py`,
`app/services/route_manager.py`, `app/services/poi/manager.py`,
`app/services/flight_state/manager.py`, `app/api/config.py`, and existing
replay/ activation notification boundaries.

**Interfaces:** Optional manager
`set_metrics_change_callback(Callable[[str], None] | None)` invokes only
`MetricsRefreshOwner.mark_dirty(reason)`. Async `refresh_without_collection()`
captures/revalidates and computes in the threadpool. Async `close()` rejects new
callbacks and drains its task handle. The existing loop responds to dirty events
without moving its source collection deadline; disabled background mode owns one
coalesced one-shot task, no timer.

- [x] Write failing parametrized tests for every lifecycle row in the ownership
      contract, including timing-only corrections, active-route parse failure,
      POI bulk/projection/restore, config reset, transaction rollback, replay
      cancel/failure, source expiry, unchanged source and shutdown.
- [x] Implement the bounded notifications and complete startup frame. Refresh
      waits for repository admission after nested changes commit/restore.
      Existing periodic checks still run when telemetry is None or unchanged.
- [x] Prove external POI/route reload without telemetry updates planned/derived
      values. In disabled mode require explicit reload for unannounced disk
      edits; neither mode discovers files through scraping.
- [x] Prove dirty wakes and one-shot tasks never collect a source, advance
      replay, add speed/passage history, write evidence or add observations.
      Test producer/config/mission barriers and stale-failure rejection.
- [x] Verify at most one one-shot task, no busy retry queue, callback detachment
      and repeated-cancellation drain; run lifecycle/regression tests and
      commit.

## Task 5: Read only HTTP, compatibility and truthful health

**Files:** Modify `app/api/metrics.py`, `app/api/metrics_export.py`,
`app/api/health.py`, metrics endpoint/unit and ETA-mode integration tests.

**Interfaces:** Keep async `get_metrics(...)` and
`_prepare_metrics(route_manager=None, poi_manager=None) -> str` for legacy calls
and frozen instrumentation. Ignore old manager arguments; remove FastAPI manager
dependencies. Keep existing encoder, content type, EOF and position response
schemas; add the specified publication diagnostic to health.

- [x] Write failing 100-scrape sequential/concurrent tests asserting zero
      simulator/ETA construction, route/POI access/calculation, storage writes,
      acquisition renewal, smoothing, source/clock advancement and detector
      work.
- [x] Replace scrape preparation with standard registry serialization in the
      threadpool. Normal/fallback paths use the same registered frame collector,
      with no byte cache, epoch validation, retries or raw-live-gauge bypass.
      Read the position table from one captured frame.
- [x] Preserve source-unavailable HTTP 200 with honest NaN. Test true
      serializer/ registration failure returning 503 and degraded health despite
      recent attempts. Failed/pending publication must not look fresh; recovery
      needs successful complete publication/exposition, not another request.
- [x] Retain preflight assertions under explicit producer/lifecycle fixtures.
      Verify all metric schemas, independent client types, alias samples,
      counter/histogram contracts, empty inputs, safe fallback and one EOF. Do
      not drop tests or blanket-relax finite-value checks to hide regressions.
- [x] Run focused tests and applicable canonical gates with timeouts, record
      unchanged failures distinctly, then commit. No whole-suite success claim
      may be based only on this focused selection.

## Task 6: Matched measurement, soak, rollback and PR review

After the setup-NaN investigation, the user approved a separate
[availability-aware v2 contract](../../performance/perf-391-availability-contract-v2.md).
Keep the original strict harness and evidence frozen. Use the identical
committed v2 source for fresh original/current-dev/candidate controls, with
instrumentation off and counters separate. Do not treat strict and v2 cohorts as
equivalent. The short original/candidate pair passed; stop at the requested
checkpoint before another long soak. Three matched repetitions and the minimum
60-minute measured acceptance remain required; no performance gate is waived.

**Files:** Create `docs/performance/perf-391-results.md` during future
acceptance; retain frozen tooling, both original inventories and the
design-probe artifacts.

- [ ] Verify original #390/#391 hashes. Use clean committed application SHAs and
      the frozen harness checkout, private projects, fixed fixtures and actual
      appuser package/browser identity. Do not change comparison guards.
- [ ] Run three matched original/current-dev/candidate warmed controls, separate
      off/counters cohorts, and separate allocation/component diagnostics.
      Compare total exporter/service CPU, preparation/publication cost, latency,
      source grids/freshness, memory/storage slopes and independent instruments.
- [ ] Stop for review if import compatibility, snapshot retention or CPU cost
      invalidates the architecture. Never claim application savings from the
      disposable probe, constructor counts or unlike workloads.
- [ ] Execute matched original/candidate minimum 60-minute steady soaks and
      separate activity cases using the plan's runbook. Require actual measured
      span at least 3,600 seconds, real 1-Hz ingestion, correct
      gaps/availability, stable interactions and no new task/series/frame
      retention attributable to #391. Attribute unchanged independent label
      growth to #393.
- [ ] Run production Docker/Nginx browser acceptance and mission switch,
      restart, export and synthetic-live/disconnect regressions. Label
      live-device/GPU limits. Final integrated eight-hour acceptance remains
      #390.
- [ ] Verify owned processes, browser children, listeners, containers, networks
      and disposable volumes are gone. Retain evidence and the open PR worktree.
- [ ] Build/test a reviewed revert candidate; no durable migration is involved.
      Disclose restoration of the old synthetic scrape hazard. Rollback
      deployment remains separately authorized.
- [ ] Record evidence, review against current dev, push/update PR #403 per the
      repository workflow. Do not deploy, merge or close #391.
