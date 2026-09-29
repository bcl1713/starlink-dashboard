# Overview metric-history graphs — Backend tasks 1–2

> This task file extends
> [the implementation plan](./2026-09-29-overview-metric-history.md). Read its
> spec, global constraints, interfaces, and Review Focus first.

## Task 1: Prometheus rolling-series planner and projector

**Files:** Create
`backend/starlink-location/app/services/overview_history_rollups.py`; create
`backend/starlink-location/tests/unit/test_overview_history_rollups.py`. Inspect
`app/services/overview_history_prometheus.py` for `OverviewHistoryQueryPlan`,
existing allowlist and `project_overview_history_matrix` before coding.

**Interfaces:** Consumes `OverviewHistoryQueryPlan` (start/end seconds, step
seconds, metric names) and `httpx.AsyncClient`. Produces `ROLLUP_METRICS` (tuple
of the five exact metric names),
`rolling_promql(metric: str, statistic: str) -> str`, and
`query_overview_history_rollups(client, plan) -> dict[str, dict]`, with
`client: httpx.AsyncClient` and `plan: OverviewHistoryQueryPlan` with
`{state, min, avg, max}` per metric. Use PromQL functions `min_over_time`,
`avg_over_time`, `max_over_time` over `[5m]`; project finite timestamp/value
pairs only, rejecting non-matrix or non-success payloads as unavailable for that
metric. Use the plan's identical start/end/step for every range query and a
bounded internal query concurrency. Account for the maximum 1,801 samples per
series and 15 aggregate traces.

- [ ] **Step 1: RED tests for query construction, common plan, empty and invalid
      matrices, and partial failure.** Write parameterized assertions such as:

```python
@pytest.mark.parametrize("statistic,function", [("min", "min_over_time"), ("avg", "avg_over_time"), ("max", "max_over_time")])
def test_rollup_uses_trailing_five_minutes(statistic, function):
    assert rolling_promql("starlink_network_latency_ms_current", statistic) == (
        f"{function}(starlink_network_latency_ms_current[5m])"
    )

@pytest.mark.parametrize("window", [300, 900, 1800, 3600, 86400])
def test_shared_bounded_plan(window):
    plan = plan_overview_history_query(end_timestamp_seconds=1_782_000_000, window_seconds=window)
    assert (plan.end_timestamp_seconds-plan.start_timestamp_seconds) == window
    assert (window // plan.step_seconds) + 1 <= MAX_OVERVIEW_HISTORY_SAMPLES
```

Build `httpx.MockTransport` responses keyed by `query` for all 15 range
expressions: one empty result, one non-finite value, one invalid payload, one
HTTP 503, others real samples. Assert 15 bounded requests with identical
start/end/step, finite samples only, no invented zeros, and only the failed
metric `state='unavailable'`. Include an unexpected extra series in one response
and assert it is not accepted.

- [ ] **Step 2: Run RED.**
      `uv run --with-requirements requirements-dev.txt pytest`
      `tests/unit/test_overview_history_rollups.py -q` from
      `backend/starlink-location`; expect missing module/functions.
- [ ] **Step 3: GREEN implementation.** Implement an explicit five-name tuple
      and three-function map, validate metric/statistic against these
      allowlists, use `asyncio.Semaphore(3)` around each query_range, reusing
      the lifecycle-managed `httpx.AsyncClient`. For example, the planner core
      is:

```python
ROLLUP_METRICS = (
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
)
ROLLUP_FUNCTIONS = {"min": "min_over_time", "avg": "avg_over_time", "max": "max_over_time"}

def rolling_promql(metric: str, statistic: str) -> str:
    if metric not in ROLLUP_METRICS or statistic not in ROLLUP_FUNCTIONS:
        raise ValueError("Unsupported overview rollup")
    return f"{ROLLUP_FUNCTIONS[statistic]}({metric}[5m])"
```

Use the existing `project_overview_history_matrix` only if its name-matching
behavior applies to function output; otherwise project the one expected series
defensively in this new module. Initialize every metric to
`{state:'available', min:[], avg:[], max:[]}` and mark a metric unavailable if
any of its three aggregates fails; do not confuse a valid empty matrix with an
error. Return only finite pairs within the planned window, max 1,801 per trace.
Keep error catches scoped to httpx/known response or shape exceptions, never
mask cancellation. The maximum accepted overall raw-plus-rollup output is 46,826
sample pairs (11 existing raw names plus 15 rollup traces, each at 1,801);
reject/trim duplicate or unexpected Prometheus series rather than exceeding this
bound.

- [ ] **Step 4: Verify and commit.** Run the focused pytest command,
      `uv run --with-requirements requirements-dev.txt ruff check`
      `app/services/overview_history_rollups.py`
      `tests/unit/test_overview_history_rollups.py`, `git diff --check`; inspect
      staged paths, commit `feat(overview): query five-minute metric rollups`.

## Task 2: Extend the existing shared history bundle without breaking the trail

**Files:** Modify
`backend/starlink-location/app/services/overview_history_prometheus.py`; modify
`backend/starlink-location/tests/unit/test_overview_history_prometheus.py` and
`backend/starlink-location/tests/integration/test_overview_history_api.py`.
Consume Task 1 module without adding an API router.

**Interfaces:** `query_overview_history_bundle` takes `client` and keyword-only
integer `end_timestamp_seconds` and `window_seconds`; it returns a dict. It
retains `series`, `window_seconds`, start/end/step keys and adds `rolling_5m`.
`OverviewHistoryReader.read()` and `/api/overview-history` keep their signatures
and existing single-flight behavior.

- [ ] **Step 1: RED for expanded contract and failure isolation.** In unit
      tests, mock the raw query's current response and the 15 aggregate
      responses through `httpx.MockTransport`. Assert existing raw `series`
      equals its pre-change shape; assert a real rollup timestamp/value:

```python
assert bundle["series"]["starlink_dish_latitude_degrees"] == [[1782000000.0, 41.2566]]
assert bundle["rolling_5m"]["starlink_network_latency_ms_current"]["min"] == [[1782000000.0, 24.0]]
assert bundle["step_seconds"] == plan_overview_history_query(end_timestamp_seconds=1782000000, window_seconds=1800).step_seconds
```

Simulate one aggregate HTTP error and assert raw latitude/longitude survives
with only that metric's aggregates unavailable; simulate raw HTTP error and
assert the existing 503 behavior. Assert only one `OverviewHistoryReader.read()`
flight for concurrent identical requests despite aggregate queries. For a custom
86,400-second window, assert every request shares `start`, `end`, `step` and
respects the 1,801-point per-series bound. In API integration test, return a
bundle with `rolling_5m` and assert the same GET exposes it without any new
route. Update older tests that assert a single **internal Prometheus** request;
retain the one **browser** request contract.

- [ ] **Step 2: Run RED.**
      `uv run --with-requirements requirements-dev.txt pytest`
      `tests/unit/test_overview_history_prometheus.py`
      `tests/integration/test_overview_history_api.py -q`; expect missing
      `rolling_5m`.
- [ ] **Step 3: GREEN bundle integration.** In `query_overview_history_bundle`,
      create the existing `plan` once, fetch/project raw first, then call
      `query_overview_history_rollups(client, plan)`:

```python
plan = plan_overview_history_query(end_timestamp_seconds=end_timestamp_seconds, window_seconds=window_seconds)
raw = project_overview_history_matrix(await fetch_overview_history_from_prometheus(client, plan))
rollups = await query_overview_history_rollups(client, plan)
return {"window_seconds": window_seconds, "start_timestamp_seconds": plan.start_timestamp_seconds,
        "end_timestamp_seconds": plan.end_timestamp_seconds, "step_seconds": plan.step_seconds,
        "series": raw, "rolling_5m": rollups}
```

Keep raw failure propagating to the existing API error mapping; a rollup failure
is represented by the Task 1 projector. Avoid a second persistent setting,
router or frontend endpoint.

- [ ] **Step 4: Verify and commit.** Run focused tests and
      `uv run --with-requirements requirements-dev.txt pytest`
      `tests/unit/test_main_overview_history.py`
      `tests/unit/test_overview_history_deployment.py -q`; run
      `git diff --check`, review staged diff, commit
      `feat(overview): expand shared history bundle`.
