# #216 source-contract tasks (approved provenance amendment)

Read this after [the main plan](2026-09-30-overview-five-metric-panels.md) and
before
[presentation/acceptance](2026-09-30-overview-five-metric-panels-presentation.md).
These are Tasks 1–2; backend paths and commands are relative to
`backend/starlink-location/`. Scope is the five Overview metrics, not general
telemetry model migration. The approved authority is
[the provenance amendment](../specs/2026-09-30-overview-metric-provenance-design.md).
Preserve unrelated position, route, ETA, environmental and signal-quality
behavior.

## Task 1: Source acquisition and nullable status contract

**Files:** Modify `app/models/telemetry.py`, `app/live/client.py`,
`app/simulation/coordinator.py`, `app/api/status.py`,
`tests/unit/test_starlink_client.py`, `tests/integration/test_status.py` and the
simulation telemetry tests/constructors located during reconnaissance. Update
`docs/api/endpoints/core.md` and `docs/api/models/health-status-models.md` in
this task; documentation impact is an additive `/api/status` contract, not a new
endpoint.

**Interface:** Add a typed `MetricAvailability` model on `TelemetryData` (field
`metric_availability`) with five explicit boolean fields: `latency_ms`,
`throughput_down_mbps`, `throughput_up_mbps`, `packet_loss_percent`,
`obstruction_percent`. Defaults for missing provenance are **false** (fail
closed). Keep internal `NetworkData` and `ObstructionData` numeric for existing
internal consumers; do not serialize compatibility fallback numbers as
observations. `/api/status` always returns the five flags and serializes
`network.*`/`obstruction.obstruction_percent` as `number | null` according to
their flags; unrelated fields stay unchanged. The `timestamp` remains the
acquisition timestamp, not request time. Reconcile every telemetry constructor
and fixture that represents _actual_ observations explicitly; do not set a
global default of true merely to preserve old tests.

**Source mapping:** `status.pop_ping_latency_ms` → `latency_ms`;
`status.downlink_throughput_bps / 1e6` → `throughput_down_mbps`;
`status.uplink_throughput_bps / 1e6` → `throughput_up_mbps`;
`status.pop_ping_drop_rate * 100` → `packet_loss_percent`;
`status.fraction_obstructed * 100`, falling back only when the key is absent to
`obstruction.fraction_obstructed * 100`, → `obstruction_percent`. Source values
must be numeric and finite (reject `bool` and unparseable strings; accept
integer/float including zero), with any explicit field-validity metadata honored
if it actually governs these readings. `obstruction.valid_s` in the observed
fixture is `None` while the status fraction is valid; do not use that
wedge-detail field as a blanket validity veto without confirming its semantics.
Check live-client extraction and library response shape on the current baseline
before committing the mapping. A missing/invalid field may retain internal `0.0`
compatibility, but its flag is false. A collection-wide exception must not
synthesize a fresh timestamped batch; preserve existing last-valid behavior.

- [ ] **Step 1 (RED):** Parameterize `tests/unit/test_starlink_client.py` for
      all five fields: measured zero, missing key, explicit `None`, malformed,
      non-finite, partial loss and next-batch recovery. Verify the obstruction
      fallback only on absent primary key, not on an explicitly invalid primary
      reading; verify documented validity metadata. Add status tests for
      available zero, one unavailable field → null/false while others remain
      numeric/true, no-provenance legacy fixture → five null/false, original
      timestamp, and unchanged position/environmental fields. Add simulation
      coverage showing generated samples explicitly mark all five available;
      identify/reconcile other construction sites by search. Run the focused
      Task 1 pytest command below to see failures for the intended new
      assertions.
- [ ] **Step 2 (GREEN):** Implement the typed flags and source parser; set flags
      independently in live/simulation sources. Extend status projection
      _without mutating telemetry_ or changing internal model units. Preserve
      genuine zero. Revise tests/fixtures that intentionally model observed
      data, but keep a no-provenance fixture to prove fail-closed behavior. Run
      the two focused test files and any affected simulation/coordinator tests
      until green.
- [ ] **Step 3 (docs + review):** Update the established endpoint/model pages
      with a concrete partial-loss JSON example, field mapping, nullable values,
      old-response limitation and collection-age interpretation. Run the Task 1
      pytest, Ruff and Markdown commands below from their respective
      directories. If a command is unavailable, install project-declared
      dependencies or report the exact blocker; do not claim green from absence
      of execution. Commit
      `feat(overview): preserve per-metric observation availability`.
      Independent task review must check that no other exporter still labels
      fallbacks as observed.

## Task 2: Prometheus and history publication contract

**Files:** Modify `app/core/metrics/metric_updater.py`, its tests
`tests/unit/test_metrics.py`, and relevant history fixtures/tests
`tests/unit/test_overview_history_prometheus.py`,
`tests/unit/test_overview_history_rollups.py` and
`tests/integration/test_overview_history_api.py` when publication/query behavior
requires it. Inspect `app/core/labels.py` for the existing `get_status_label`
behavior. No endpoint shape or Prometheus metric name change is authorized.
Documentation impact is included in Task 1's API pages and Task 5's Overview
guide; only update Prometheus operator docs here if actual exporter
behavior/configuration requires it.

**Interface:** For each unavailable five-metric field, set only its
corresponding current gauge to `math.nan`, skipping its histogram observation
(where one exists). Do not clear unrelated gauges. Resume finite gauge/histogram
updates independently on recovery. Classify connection status from _available_
latency and packet loss only: when either is unavailable use an explicit
`unknown`/unavailable classification (including histogram labels), not an
excellent class derived from compatibility zero. Check all metrics that use
these inputs before changing labels. Preserve status/position and planning
metrics.

- [ ] **Step 1 (RED):** Extend `tests/unit/test_metrics.py` with parameterized
      one-metric-at-a-time missing/zero/recovery cases, gauge NaN versus finite
      zero, unchanged other gauges, no histogram count increase for missing
      latency/downlink/uplink, and unknown network status label when latency or
      loss is absent. Test direct old telemetry lacking provenance fails closed.
      Add history-contract tests: NaN/absent raw metric at an evaluation step
      yields no finite observed point; trailing five-minute rollup alone does
      not masquerade as an observation at that step; subsequent valid step
      resumes. Recognize `query_range` timestamps are evaluation times and may
      reuse a prior sample within lookback, so inspect the current Prometheus
      adapter/projection and explicitly test the available guarantees instead of
      asserting a false source timestamp. Run the Task 2 pytest command below;
      capture failures.
- [ ] **Step 2 (GREEN):** Gate current-gauge and histogram writes independently
      by availability; reuse existing clear-to-NaN semantics. Implement unknown
      classification without mislabeling other metrics. If tests demonstrate
      Prometheus lookback/rollups filling a newly unavailable interval despite
      NaN publication, design a bounded explicit gap mask or documented
      scrape-lag boundary before continuing; **do not** claim exact
      source-observation freshness from `query_range` evaluation timestamps.
      Keep history query budget/window and five-second request default
      unchanged.
- [ ] **Step 3 (verify/review):** Run the focused Task 2 pytest and Ruff
      commands below, and the impacted full backend suite when dependencies are
      installed. Review Prometheus exporter text/fixture results for NaN on
      absent-only gauges and no new histogram observations; record any
      scraping/lookback limitation in the Overview guide. Commit
      `feat(overview): suppress unavailable metric observations`. Independent
      task review must separately check public status and Prometheus outputs for
      honest missingness before frontend work begins.

### Task 1 commands

From `backend/starlink-location/`:

```bash
python -m pytest tests/unit/test_starlink_client.py \
  tests/integration/test_status.py -q
ruff check app/models/telemetry.py app/live/client.py \
  app/simulation/coordinator.py app/api/status.py \
  tests/unit/test_starlink_client.py tests/integration/test_status.py
```

From repository root:

```bash
markdownlint-cli2 docs/api/endpoints/core.md \
  docs/api/models/health-status-models.md
```

### Task 2 commands

From `backend/starlink-location/`:

```bash
python -m pytest tests/unit/test_metrics.py \
  tests/unit/test_overview_history_prometheus.py \
  tests/unit/test_overview_history_rollups.py \
  tests/integration/test_overview_history_api.py -q
ruff check app/core/metrics/metric_updater.py app/core/labels.py \
  tests/unit/test_metrics.py
```
