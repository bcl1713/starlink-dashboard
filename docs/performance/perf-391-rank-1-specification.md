# 391 rank 1: operation-scoped producer consolidation

**Proposed specification; approval required before application work.** Prepared
2026-10-22 for a NEW, LOW-reasoning implementation session. This document and
its [implementation plan](../superpowers/plans/2026-10-22-perf-391-rank-1.md)
form one review candidate. Neither document authorizes execution.

## Evidence and decision

Inputs: [AGENTS.md](../../AGENTS.md), PR #405 diagnostic commit
[`f2a5b439`](https://github.com/bcl1713/starlink-dashboard/commit/f2a5b4394a6000b0bcaa87ae2ac6697531aed1be),
its [investigation](perf-391-independent-investigation.md),
[corrective ranking](perf-391-corrective-plan.md),
[diagnostic findings](perf-391-diagnostic-phase.md), and PR #403 source at
[`e1f65798`](https://github.com/bcl1713/starlink-dashboard/tree/e1f657986f7b988a967ddd2bef8ca4626e30b5de).
Task 6's
[report](https://github.com/bcl1713/starlink-dashboard/blob/e1f657986f7b988a967ddd2bef8ca4626e30b5de/docs/performance/perf-391-results.md)
and
[review](https://github.com/bcl1713/starlink-dashboard/blob/e1f657986f7b988a967ddd2bef8ca4626e30b5de/docs/performance/perf-391-task-6-review.md)
retain the NO-GO: producer CPU 2.898 → 5.760 ms, backend paired CPU +0.21% with
an interval crossing zero, and capture gaps 1.754899/1.583978 seconds. Short
diagnostics reached 1.254532 seconds, without reproducing those failures.

Choose private admitted updater/preparer functions plus one source read per
validation boundary. Keep the public guarded APIs. Reuse a successful check only
across an immediate synchronous handoff under the same repository gate. The live
event block is a separate boundary: retain a check after it. This is smaller
than introducing an admission-token framework or moving calculation outside
admission; both alternatives add race/lifecycle decisions without measured
justification. Do not pursue those alternatives here.

Expected benefit is fewer lookups, nested acquisitions, serializations and
route-profile resolutions. No percentage saving is promised. This is CPU/work
optimization; completion delivery, observer scheduling and historical cadence
attribution remain independent unresolved work. Short success cannot clear Task
6 or prove a cadence fix.

## Scope and exact source map

All application paths below are relative to `backend/starlink-location/` in the
application PR. Line anchors refer to `e1f65798`, not this documentation branch.

| File and anchor                                                                                                                                                                                                                             | Change                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| [`main.py:989`](https://github.com/bcl1713/starlink-dashboard/blob/e1f657986f7b988a967ddd2bef8ca4626e30b5de/backend/starlink-location/main.py#L989), `_background_update_tick`, nested `source_is_current`                                  | Keep operation-local binding; consolidate active-route reads; use private admitted updater; retain pre/post-event checks. |
| [`app/core/metrics/metric_updater.py:216`](https://github.com/bcl1713/starlink-dashboard/blob/e1f657986f7b988a967ddd2bef8ca4626e30b5de/backend/starlink-location/app/core/metrics/metric_updater.py#L216), `prepare_metrics_from_telemetry` | Retain decorated public wrapper; move existing body verbatim to `_prepare_metrics_from_telemetry_admitted`.               |
| Same file, [`update_metrics_from_telemetry:297`](https://github.com/bcl1713/starlink-dashboard/blob/e1f657986f7b988a967ddd2bef8ca4626e30b5de/backend/starlink-location/app/core/metrics/metric_updater.py#L297)                             | Retain public entry check/gate; move preparation/final-check/CAS/error body to `_update_metrics_from_telemetry_admitted`. |

Read but do not modify: `source_admission.py` identity functions and
`frame_inputs_are_current`; `frame_builder.py`/`FrameInputs`/`prepare_frame`;
`frames.py`; `input_admission.py`; `repository_gate.py`; `storage.py`;
`services/route_manager.py`; `services/flight_events/live_adapter.py`;
`simulation/run_service.py`; `refresh_inputs.py`; metrics exports and registry.
The [regression specification](perf-391-rank-1-tests.md) fixes test paths.

No cross-tick cache, #392 mission-context cache, #398 geometry optimization,
POI-copy ownership change (rank 2), trusted sealed-frame shortcut (rank 4), new
worker, polling/deadline change, metric/schema/registry/publication change,
1.5-second relaxation, deployment, merge, issue closure or new 60-minute soak.
Preserve standard Prometheus instruments and every defensive copy.

## Before and after call graphs

`G` means existing repository admission; nested G still performs gate lookup.
`S` means source validation, including config serialization, route-source hash,
runtime binding and current telemetry. Coordinator-internal reads are omitted.

```text
BEFORE: ordinary new non-paced observation
_background_update_tick
  G: capture head/coordinator/config/route/service + baseline identities
  coordinator.update()                         # live I/O outside outer G
  G: active_route = get_active_route()          # read A
    S1: source_is_current -> get_active_route() # read B duplicates A
    live mission resolve/record/observe/sync, if configured
    route_progress_snapshot, if simulation
    update_metrics_from_telemetry
      nested G; S2 -> get_active_route()        # adjacent duplicate if no events
      prepare_metrics_from_telemetry
        decorator nested G
        observe instruments/phase; POI capture; read expected head
        FrameInputs copy; prepare_frame; seal + schema validation
      S3 -> get_active_route()                  # required final source read
      frame_inputs_are_current                 # route/POI/phase hashes
      FrameStore.publish -> schema validation + expected-head CAS

AFTER: same boundaries, same accepted-observation work
_background_update_tick
  G: same baseline capture
  same coordinator.update()
  G: active_route = source_route                # reference, no fresh lookup
    progress snapshot before acceptance check, for simulation
    S1: source_is_current() -> one fresh current route
    live event block, if executed
      S2: source_is_current() -> fresh read     # keep after event mutations
    _update_metrics_from_telemetry_admitted(final_validation=source_is_current)
      _prepare_metrics_from_telemetry_admitted  # no redundant nested G
        same observation/copies/head capture/frame/seal validation
      source_is_current(frame)
        Sfinal -> one fresh current route
        frame_inputs_are_current(frame, that_route, poi_manager)
      same publish/schema validation/CAS
```

Only ordinary NEW telemetry takes this optimized route. Retained acquisition,
disconnect, derived refresh and replay keep their existing control flow and
guarded APIs. The shared closure's no-frame calls must preserve those branches.

## Ownership and permitted reuse

| Input/value                                                                 | Authoritative owner and operation lifetime                                           | Reuse rule                                                                                                                |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `source_expected`                                                           | `FRAME_STORE` initial head captured under baseline G                                 | Only failure targeting before preparation; never force publication against it.                                            |
| `coordinator`, `source_lifecycle`                                           | Initial `_coordinator` reference and `coordinator_identity`                          | Stable comparison targets; re-read current reference/lifecycle each check.                                                |
| `current_config`, `source_config`                                           | `_current_runtime_config()` object and its initial JSON                              | Reuse baseline JSON only; reserialize current config at every required check.                                             |
| `source_routes`, `source_route`, `source_route_id`, `source_route_revision` | Initial route manager, resolved active object, active ID, `route_source_identity`    | Pass `source_route` to preparation after verifying it remains current. Never substitute a route from a different binding. |
| `source_service`, `source_revision`                                         | Initial service object and `(runtime_id, revision)`                                  | Compare fresh service/status each check, including cancellation/reset.                                                    |
| `telemetry`                                                                 | Result from the captured coordinator's collection                                    | Check current telemetry object identity; detached frame identity still hashes full payload. No timestamp-only shortcut.   |
| `source_mission`                                                            | Existing live context resolution supplies known parent ID and semantic hash          | Keep per-operation only. Final check reloads this known mission and hashes it; no enumeration/cache redesign.             |
| `active_route` local                                                        | Alias of baseline `source_route`                                                     | New observation path only; current route resolved inside checks must be this object.                                      |
| `checked_route` local                                                       | Each invocation of `source_is_current` resolves the authoritative manager route once | Reuse only inside that invocation, including its final frame-input check. Never reuse S1's value at Sfinal.               |
| POIs, status, progress, replay ETA, clocks                                  | Existing preparer and detached `FrameInputs`                                         | Preserve capture/copy/hash order. Do not reuse pre-detection phase or pre-observation expected head.                      |
| Preparation `expected`                                                      | `FRAME_STORE.read()` after observation/POI reads, delivered via `_captured_head`     | Sole CAS/failure head for prepared frame; reads may have invalidated earlier heads.                                       |
| `FrameIdentity`                                                             | `prepare_frame` from detached inputs                                                 | Unchanged telemetry/full-route/POI/phase hashes and clock rules; no new precomputed identity override.                    |

The planned-source route hash excludes actual arrival/departure/status and
normalizes absent timing profiles. The frame route hash includes the full route.
These are different calculations; retain both. Phase identity excludes only its
existing advancing countdown fields. Fresh final hashes cannot be replaced with
input revision, an earlier success boolean, or detached hashes.

## Exact API changes

Retain public signatures/defaults, decorator, return values, imports and
`app.core.metrics` exports. Introduce private functions in `metric_updater.py`:

```python
def _prepare_metrics_from_telemetry_admitted(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *, flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    _captured_head=None,
) -> "GaugeFrame | None": ...

def _update_metrics_from_telemetry_admitted(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *, flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    final_validation: Callable[["GaugeFrame"], bool],
) -> None: ...

# Nested in main._background_update_tick; no retained callback or new object.
def source_is_current(frame: "GaugeFrame | None" = None) -> bool: ...
```

Private functions require the calling thread to hold the canonical repository
gate. They do not acquire/release it. The update helper additionally requires
successful immediate entry validation by its caller. Do not export these
functions, add bypass flags to public APIs, call `__wrapped__`, or change the
general decorator/gate. Approved call sites: public wrappers and this one main
new-observation block. Replay continues calling public preparation.

Pseudocode (retain existing exception boundaries and reason strings):

```text
public prepare(...): [existing @model_input_write]
  return private_prepare(...all arguments...)   # existing body, unchanged
public update(..., source_is_current=None):
  with canonical gate:
    if callback exists and not callback(): return
    final(frame): return (callback absent or callback()) and
                         frame_inputs_are_current(frame, active_route, poi_manager)
    private_update(..., final_validation=final)
private_update(..., final_validation):
  expected = FRAME_STORE.read()
  captured(head): expected = head
  try:
    frame = private_prepare(..., _captured_head=captured)
    if frame is None: return
    if not final_validation(frame): fail(expected, existing superseded reason); return
    FRAME_STORE.publish(expected, frame)
  except Exception: [existing fail/log/mission_context rethrow behavior]
```

`source_is_current` must read the current route manager once into a local,
resolve its route once, then compare manager identity, route object, active ID
and planned-source hash against baseline. Preserve every other existing check:
coordinator/lifecycle, config reference/JSON, service/runtime revision, known
mission identity, current telemetry reference or disconnected status. Evaluate
these after route resolution, which may trigger external profile reload. The
legacy non-`SimulationConfig` branch keeps its two reference checks and does not
add domain-model reads. In either branch, when `frame` is supplied, also call
`frame_inputs_are_current` with that branch's checked route (legacy: the
existing `active_route` argument). Return false on mismatch; preserve existing
exception propagation into the updater's failure handler.

In main, keep the initial pre-event check. For simulation, obtain progress
before that check. For live event handling, preserve context resolution,
`source_mission`, recovery logging and all event calls; after the entire block
(including caught failures), run another source check before the private
updater. On this second rejection use the existing updater-entry semantics:
return without observation accounting or a new fail transition. First rejection
still fails `source_expected` with `source changed during collection`. Between
the last successful entry check and private update there may be only argument
binding and the function call: no source readers, event callbacks, progress
getter, clock read, await, lock release or user code.

## Ordering, failure and final authority

Keep repository gate → existing model locks → short FrameStore pointer lock.
Never hold the pointer lock during capture/calculation/validation. Live I/O
remains outside the outer publication gate. Computation stays inside it.
Repository writers still wait fairly; scrapes still read one immutable head
without admission. No new cancellation token or force-release mechanism.

Final source check and fresh full route/POI/phase checks run after preparation
and immediately before existing publish validation/CAS, under uninterrupted G.
Keep complete validation at both seal and publish, stale-head identity CAS,
input-revision matching, unavailable handling and independent instruments.
Actual source acquisition, frame wall publication time and replay mission time
remain separate clocks. No retry repeats observation accounting.

Preparation failure, identity-read failure and lost CAS retain old head/failure
semantics, captured-head handling and exactly-once accepted counters. Failure
after accepted observation does not roll back histograms/smoothing/detection.
Before acceptance rejection counts zero. `None` retains detection reset and
disconnect behavior. Retained-source refresh never becomes an observation.

Config/route/service replacement or reset during collection is rejected before
acceptance. Reentrant edits during events or preparation still encounter the
next applicable fresh check. External file changes still use real route/POI/
mission readers; no revision-only substitute. This preserves existing detection
boundaries, not a new transaction over arbitrary editors bypassing file locks.

Cancellation of an async waiter cannot kill the synchronous worker: existing
draining/shutdown must finish before managers close. Obsolete workers cannot
overwrite newer heads. Replay retains prepare → commit_tick → authoritative
runtime/config/telemetry/mission/input checks → CAS; precommit compensation and
postcommit metric failure remain distinct. Do not optimize its identity reads.

## Stop and return for design review

Stop if any proposed reuse spans admission release, an await, source mutation,
live event callback, replay commit, unknown hook, or another producer. Stop if
the private path needs callers beyond those listed, a general token/cache,
changes to capture/observation order, gate fairness, lock order, public API,
registry/frame validation, replay, or any excluded subsystem. Also stop on
source-reader side effects that invalidate the specified one-read boundary,
unexplained accounting/clock/test differences, missing baseline dependencies, or
an inability to prove cleanup. Preserve evidence; do not broaden the patch.
