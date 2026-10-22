# 391 rank 1 regression specification

Companion to the [proposed specification](perf-391-rank-1-specification.md). All
paths below are relative to `backend/starlink-location/` in PR #403. These are
requirements for future tests, not tests executed in this planning session.

## Fixture and barrier protocol

Reuse `background_runtime` from
`tests/integration/test_live_background_route.py`. In the new integration file,
close `main.app.state.metrics_refresh_owner` in an autouse async fixture, as in
`test_metrics_source_admission.py`; tests explicitly own publication. Restore
the original coordinator before fixture teardown. Use the real standard registry
and `FRAME_STORE`, isolated mission/POI storage, frozen fixture clocks and real
writer APIs. Do not globally mock source validation or replace the registry.

Every race uses `threading.Event` named `entered`, `release`, `writer_started`,
`writer_finished`; wrap only the specified boundary. Producer enters a
`ThreadPoolExecutor(max_workers=2)` once. Await `entered` via
`asyncio.to_thread(entered.wait, 3)`; blocked worker asserts `release.wait(5)`;
future results have `timeout=5`. Always `release.set()` in `finally` before
joining workers. Restore monkeypatches after workers finish. Never sleep to
establish ordering or leave a thread alive after a failed assertion.

Snapshots: old publication object and frame pointer; update counter; sum of
network histogram `_count` samples; calculator stats; detection checkpoint;
source telemetry pointer/timestamp. NaN assertions use `math.isnan`. A failed
old CAS must preserve the entire newer publication object, including status.

## Unit tests: admitted wrappers and immutable preparation

Create `tests/unit/test_metrics_admitted_update.py`.

| Exact test name                                                | Setup and required assertions                                                                                                                                                                                                                                                                                                                  |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_public_prepare_acquires_gate_and_forwards_all_arguments` | Spy on canonical gate lookup/acquire and stub private preparer; pass distinct sentinels for all positional/keyword arguments, including `_captured_head`. Assert one wrapper acquisition, identical argument objects/default behavior, identical return object; private exception escapes and gate releases.                                   |
| `test_public_update_keeps_entry_and_final_checks`              | Stub private preparer with a valid existing frame and capture callback. Source callback outcomes `(False,)`, `(True, False)`, `(True, True)`: preparation calls 0/1/1, source calls 1/2/2, publish calls 0/0/1. The second case fails the captured head with existing superseded reason.                                                       |
| `test_private_update_adds_no_admission`                        | Caller holds real G. Stub private preparer and final validator, spy only direct updater/preparer gate lookups. Assert zero extra lookup/acquire from these helpers, one final check after prepare, one publish after final. Do not count nested domain-reader gates as removable wrappers.                                                     |
| `test_private_update_targets_post_observation_head`            | Private preparer invalidates initial head, calls `_captured_head(new_head)`, then returns frame for new revision. Assert publish receives new head, not initial one. Repeat with builder exception after capture: fail targets new head.                                                                                                       |
| `test_private_update_failure_and_stale_cas_count_once`         | Parameterize `builder`, `final_false`, `final_raises`, `stale_cas`. Use real preparation with accepted telemetry. Assert update counter +1 and each applicable histogram +1; no repeated detection/smoothing; old frame retained on failure. For stale CAS, publish a newer head inside wrapped prepare and assert it remains identical/ready. |
| `test_none_preparation_resets_detection_without_observation`   | Public and private preparers with None: return None, reset detection once, counters/histograms unchanged, no final check/publish. Private call is under G.                                                                                                                                                                                     |
| `test_final_validation_cannot_be_omitted`                      | Calling private updater without required `final_validation` raises TypeError before any accounting. No permissive default or public skip-validation flag.                                                                                                                                                                                      |
| `test_detached_frame_ownership_is_unchanged`                   | Use real public preparer. Mutate original telemetry/config/route/POI/status after `FrameInputs` creation through a wrapped `prepare_frame`. Assert detached values/identity remain original; subsequent fresh authoritative final check rejects changed inputs. Reuse ownership assertions in `test_metrics_frame_builder.py`.                 |

Use exact optional-error behavior from the old updater: ordinary errors logged
and failed, `mission_context is not None` errors re-raised. Parameterize that
test across both contexts. Do not convert BaseException into Exception.

## Integration tests: source boundaries and operation counts

Create `tests/integration/test_metrics_operation_capture.py`. Its first test
uses a validated `SimulationConfig`, new non-paced telemetry and no live event
runtime, for both live/simulation fixture modes. Disable unrelated GEP refresh
with the fixture's existing switch. Scope spies to source reads made by
`main._background_update_tick`, excluding coordinator internals and startup.

| Exact test name                                                     | Required assertions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_new_tick_reuses_only_immediate_entry_validation`              | Trace call order with spies around main's imported `route_source_identity`, runtime config JSON and route getter. Assert 3 source-route hashes/config JSON calls: baseline, entry, final; 3 main source route reads at the same boundaries. Baseline source validation has 4 hashes/dumps and 5 main route reads; assert RED there. One final `frame_inputs_are_current`, one complete prepare, two schema validations (seal/publish), one publish, counter +1. Instrument outside coordinator/event code; no asserted global profile count. |
| `test_live_events_require_another_entry_check`                      | Install real live event runtime; spy on event methods without disabling them. Assert ordered entry check → resolve/record/observe/sync → fresh entry check → private update → final check. Four main source checks including baseline hashing; no fast path across events. Repeat with `record_live` raising OSError: caught recovery still reaches fresh entry check.                                                                                                                                                                       |
| `test_live_event_source_replacement_is_rejected_before_accounting`  | In wrapped `record_live`, replace config via real coordinator API after initial check. Assert private prepare never called, update/histogram deltas zero, no coupled publication. Preserve event recovery behavior and current head (which mutation may invalidate); no additional fail transition for second entry rejection.                                                                                                                                                                                                               |
| `test_two_ticks_recapture_every_source`                             | Run tick, replace config and activate second route under G, run next tick. Assert second tick's baseline, entry and final identities are freshly calculated, new route/config used; no retained success bit/model/identity across calls.                                                                                                                                                                                                                                                                                                     |
| `test_planned_route_identity_and_full_frame_identity_stay_distinct` | Parameterize untimed route versus empty timing profile, actual departure/arrival updates, and planned timing/geometry changes. Existing planned-source exclusions remain; full frame hashes actual fields. Planned/geometry mutation during collection rejects before acceptance; producer phase actuals during preparation permit matching full final frame.                                                                                                                                                                                |
| `test_legacy_adapter_keeps_reference_only_source_checks`            | Reuse adapters from `test_flight_event_isolation.py`; no new domain serializers/status/route checks in legacy early branch. Private publication callback still called once, final frame validation still required if a real frame is built.                                                                                                                                                                                                                                                                                                  |

Counts describe successful fixed fixtures. Early mismatch may short-circuit; do
not require expensive hashes after a proven mismatch. POI/telemetry/phase hash
counts must remain unchanged. Do not claim all 9 extra gate lookups or all 4
extra route reads in the investigation disappear.

## Race cases with exact barriers

Add the following to the new integration file. Run live and simulation unless a
row specifies live only. Each parameter is a separate test case.

| Test and parameter                                                                                                                                                                   | Barrier and mutation                                                                                                                                                                                                                        | Expected result                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_collection_race_rejects_before_acceptance`, `config`, `coordinator`, `reset`, `route_activate`, `route_remove`, `route_planned_timing`, `service_revision`                     | Wrap coordinator.update: collect first, signal entered, wait release before returning. While outer G is absent, apply real writer under G; coordinator replacement uses monkeypatch as existing source test does.                           | Counter/histogram deltas zero; no prepared frame; old frame retained with failed/pending source status. Repeat with a newer head published by mutator: entire newer head remains identical.                                                               |
| `test_writer_waits_through_final_check_and_publication`, `config`, `route`, `poi`, `phase`, `mission`                                                                                | Wrap prepare_frame: build, signal entered, block before return. Second worker signals writer_started before attempting G, then performs writer API and signals writer_finished.                                                             | After writer_started, writer_finished is false; 20 concurrent HTTP `/metrics` calls complete within 3 seconds with 200 and EOF, all use old head. Release; producer publishes once before writer enters; writer then finishes. No torn frame or deadlock. |
| `test_reentrant_preparation_change_rejected`, `config_replace`, `config_inplace`, `route_replace`, `route_inplace`, `poi`, `phase`, `telemetry_replace`, `reset`, `service_revision` | Wrapped prepare_frame first builds frame, then mutates on same producer thread (under reentrant G), returns staged frame.                                                                                                                   | Final source/coupled-input check fails, staged frame never publishes, counter +1 exactly; newer head injected after mutation remains untouched. Current full route/POI/phase reads run where applicable.                                                  |
| `test_known_live_mission_is_reloaded_before_publish` (live only), `edit`, `delete`, `read_failure`                                                                                   | Use active mission fixture from existing persisted-mission test; after frame build, save changed mission/delete its file or make final `load_mission_v2` raise OSError.                                                                     | Final known-ID load attempted; old frame retained, publication failed or newer head preserved; accepted counter +1. No mission enumeration added or identity reuse across event resolution/final load.                                                    |
| `test_external_route_reload_invalidates_prepared_head`, `planned_edit`, `invalid_profile`                                                                                            | Configure actual profile resolver/SourceStore as in existing lifecycle source tests; after build, atomically edit its persisted profile or corrupt it without local metrics notification. Release final check to actual `get_active_route`. | Resolver detects edit/failure on final read, stale prepared frame cannot publish; reload invalidation is not overwritten by fail(old_expected). Next existing refresh recovers after valid source restored.                                               |
| `test_external_poi_reload_is_not_bypassed`, `edit`, `invalid`, `lock_failure`                                                                                                        | After frame build, edit real POI JSON, corrupt it, or inject POI file-lock failure as existing reload tests do. Final validator uses actual metrics_input_identity.                                                                         | Changed/unavailable POI input rejects staged frame; one accepted count; valid restoration plus existing refresh recovers without new periodic worker.                                                                                                     |
| `test_final_validation_uses_new_route_read`                                                                                                                                          | Source route getter returns baseline at initial/entry reads; wrapped prepare then makes resolver return second route at final read.                                                                                                         | Final source rejection, old frame retained; final read was performed rather than reusing entry route.                                                                                                                                                     |

For writer barriers, instrument gate acquire to set an `attempting_gate` event
immediately before the writer's actual acquire; await it too. A flag set before
launching a writer alone does not prove lock contention. Check the recorded
order `producer publish < writer acquired`, rather than timing tolerances. For
external-edit cases, use thread/file barriers, not mtime sleeps; force distinct
content/stat identity using fixture mechanisms already used by reload tests.
Stop if real reload behavior cannot be reproduced; do not mock success.

## Cancellation, replay and existing regressions

Add `test_cancelled_loop_drains_admitted_tick_before_shutdown` to the new file:
enable the fixture's background loop as in the existing concurrency test; block
after frame preparation, start existing shutdown, cancel it twice and assert
manager close has not run while the tick remains owned. Before release,
explicitly invalidate the frame head from the test thread to exercise obsolete
completion. Release, await drain, then assert no worker/owner task or held gate
survives and the staged obsolete frame was never published. Use the existing
shutdown test's drain idiom; do not invent worker interruption semantics.

Keep these existing tests and assertions; rerun their complete files:

- `test_metrics_source_admission.py`: replacement, normal frame clocks, retained
  source, disconnect and persisted mission tests.
- `test_metrics_route_admission.py`: changed collection route cannot relabel old
  progress; `test_metrics_publication_lifecycle.py` and all
  `test_metrics_lifecycle_*.py`: refresh/deadline/cancel/reload behavior.
- `tests/unit/test_metrics_source_ordering.py`: cancelled prepared replay,
  accepted failure counts, replay visibility, external input changes and newer
  owner preservation; `tests/integration/test_metrics_replay_commit.py`: failed
  commit never publishes and postcommit errors preserve committed domain state.
- `test_metrics_http_purity.py`, `test_metrics_http_contracts.py`,
  `test_metrics_exposition_ordering.py`, `test_metrics_endpoint.py`, and
  `tests/unit/test_metrics_frames.py`: read-only scrapes, schema, alias,
  independent instruments, unavailable fields and CAS.

Adjust only interception targets in these existing test files:
`tests/integration/test_live_background_route.py` (three updater spies) and
`tests/unit/test_flight_event_isolation.py` (one spy). Target
`app.core.metrics.metric_updater._update_metrics_from_telemetry_admitted` for
the main new-observation path; preserve every route, thread-order, call-count
and flight_events_managed assertion. Public API contract tests stay on public
APIs. If additional broken spies appear, inspect and enumerate them for review;
do not weaken behavioral assertions to fit the refactor.

Regression exit criteria: new tests demonstrate intended failures before each
change, then pass with real final checks enabled; all retained suites pass; no
arbitrary external-frame validation test is removed. Run the full canonical
backend once on the final candidate and required lint/CI. Failures or timeouts
remain failures; verify worker/process cleanup before retrying.
