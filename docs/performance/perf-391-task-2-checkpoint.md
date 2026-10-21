# Issue 391 Task 2 checkpoint

Task 1 was approved at `b2c90832` in
[review comment 6305647846](https://github.com/bcl1713/starlink-dashboard/pull/403#issuecomment-6305647846).
This change implements Task 2 only on PR #403. Stop for review before Task 3; no
deployment, merge or issue closure is authorized.

## Implementation and ownership

The existing registry now registers one `TelemetryFrameCollector` for all 29
coupled families and the position alias. Frozen definitions preserve name, help,
type/unit and label order against the retained Task 1 schema fixture. Coupled
handles stage writes only inside a complete preparation scope; there are no
mutable Gauge shadows or private-client dependencies. All 18 independent Gauges,
seven Counters and four Histograms retain identical constructor expressions and
standard client classes. The registry and encoder are unchanged.

`FrameInputs` detaches telemetry, config, route, POIs, phase and replay clock
inputs. `prepare_frame(inputs, admit_observation)` fills all coupled fields,
including route timing, mode, phase, observation timestamp and explicit unknown
values. It seals without publishing. The existing accepted updater observes
independent instruments once and publishes with its captured expected head.
Failed preparation marks that head failed; obsolete completion/failure cannot
replace a newer head. No retry restores or replays independent measurements.

Derived preparation uses a calculator copy captured under the ETA computation
guard. Manager inputs are captured before that guard; detached calculation runs
outside it. It appends no speeds, tracks/logs no passage, changes no accepted
counts/histograms, and renews neither acquisition timestamps nor the
successful-update timestamp. Accepted preparation retains producer-owned ETA
history/tracking. The strict internal service preparation propagates failures to
the complete-frame owner; the existing public `update_eta_metrics` retains its
logged empty-result fallback for compatibility.

Preflight preserves 150-knot distance fallback with usable position, planned
anticipated waypoint timing without fabricated coordinates, and planned-duration
fallback after scheduled departure. Missing/stale in-flight speed or position
and measured stationary in-flight speed yield unavailable ETA. The assumed
preflight speed never overwrites an observed speed. Replay retains its explicit
mission clock and planned ETA source; source UTC stays separate. Original route
Unix conversion is retained, including its existing local-time `mktime`
behavior.

`_current_position` is a read-only view of the authoritative frame. The full
collector emits the position alias from its own captured head; the compatibility
PositionCollector remains unregistered. `/position-table` captures the mapping
once for its three dimensions. Bound gauge `.collect()` intentionally returns
the whole family, now tested with two distinct children.

## File and API changes

| File under backend/starlink-location                              | Change                                                                                                                |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| app/core/metrics/prometheus_metrics.py                            | Frozen 29 schemas/views, one collector, read-only position view; independent definitions unchanged                    |
| app/core/metrics/frame_builder.py                                 | Detached inputs; complete accepted/derived/unavailable frame preparation                                              |
| app/core/metrics/metric_updater.py                                | Preserve named producers; atomically publish frames; independent accounting and phase observation stay producer-owned |
| app/core/eta_service.py                                           | Guard accepted ETA state, detached derivation, explicit POI snapshots, strict internal preparation                    |
| app/services/eta_calculator.py and app/services/eta/projection.py | Optional keyword-only track_passage=False for read-only derivation                                                    |
| app/api/metrics_export.py                                         | Pure standard serialization; remove simulator, ETA and all coupled registry writes                                    |
| app/api/metrics.py                                                | Capture position once; retain outer HTTP dependencies/fallback/health for Task 5                                      |
| main.py and app/simulation/coordinator.py                         | Necessary mechanical migration of standalone progress/timestamp writes into the accepted complete frame               |
| tests/conftest.py                                                 | Explicit complete frame reset; public independent Gauge resets, no private registry/child access                      |
| Existing and new metric/ETA/replay tests                          | Retain assertions, explicitly publish fixture observations, cover source/failure/derivation contracts                 |

Both compatibility import shims remain unchanged; their existing test checks all
70 exported objects by identity, including the 29 handles. No new exports are
needed. Existing helper positional/keyword arguments remain supported. Additive
internal APIs are `FrameInputs`, the two preparation functions,
`derive_eta_metrics`, optional keyword-only `pois` on ETA service functions,
`track_passage` on the calculator/projection, and optional `route_progress` on
the accepted updater. No manifest, Dockerfile or deployment configuration
changes.

## Required coordination and scope deviations

The review identified an ordering dependency: old scrape code looked up ETA and
distance Gauges through `REGISTRY._names_to_collectors`. Registering the new
collector with those writers active would be invalid. Therefore the pure
serializer portion of Task 5 is pulled forward into this coherent Task 2 change.
The old helper signatures and EOF format remain. No fake collector mutation
interface or dual registry is introduced.

Two other standalone writers required migration at the registration boundary:
main's successful-update timestamp and the coordinator's early route progress.
The timestamp is now part of the accepted complete frame. Main passes its
existing simulation progress alongside telemetry; the coordinator no longer
publishes an early partial frame. This is the minimum runnable adaptation; Task
3 source admission/revalidation and post-runtime-commit replay publication are
**not** implemented. The existing replay callback/commit order is unchanged, so
Task 2 is not a release candidate for the final replay correctness claim.

The position-table one-capture change also moves forward from Task 5 because
three separate mapping reads would defeat the new view's consistency boundary.
Outer HTTP manager dependencies, final failure/health response behavior and
source-unavailable response policy remain Task 5.

Two existing coupled private test reads were found during integration: route
progress and replay POI ETA. Their original value assertions remain, now through
`REGISTRY.get_sample_value`. This corrects the earlier audit summary that
classified remaining private reads as independent-only. Independent mission
private-read tests are untouched. Fixtures use explicit producers in disabled
background tests; no finite/value assertion was weakened or test silently
skipped.

No general label cleanup is added. Only current coupled-frame replacement drops
superseded coupled labels; independent mission/GEP label lifecycle remains #393.

## Verification and failures

**Client matrix:** 410 passed and 18 existing skips on each of prometheus-client
0.19.0 and 0.26.0 in a private declared-dependency environment. The 18 skips
require the absent external real-KML fixture directory in the unchanged
`test_route_eta.py`; generated timed/untimed route cases run and pass.

Coverage includes exact actual schemas/alias and import identities, two-child
whole-family collection, standard independent types/constructors, detached
source data, smoothing/passages/acquisition/count preservation, missing/stale
and zero inputs, future/past scheduled departure, unavailable preflight
position, source invalidation during preparation, failed completion after a
first staged POI label, and coupled route-label replacement without independent
cleanup. One hundred concurrent exporter calls prove no manager access,
ETA/history mutation or publication during helper exposition.

Independent review found two Important regressions. Both were reproduced RED and
fixed, with three new passing cases: naive actual/scheduled departure must
retain UTC countdown interpretation, and failed live/legacy gauge preparation
must still count its admitted observation once. Histogram observation ordering
was restored ahead of optional phase/preparation work. Replay failure/count
behavior stays unchanged. The fixes were verified by the implementer in the
complete passing relevant matrix; no Critical or additional Minor findings.

The first integration run had three failures: obsolete failure-injection site,
and two scrape-dependent fixtures. These were fixed by moving injection to the
preparation boundary and explicitly publishing source observations, retaining
all assertions. A later run found the replay ETA private read and two planning
worker errors caused by launching pytest from stdin. The private read was
migrated; standard `python -m pytest` resolved both worker errors. All original
failure logs are retained. A reviewer sandbox AnyIO stall was stopped/cleaned;
its host exporter rerun passed all three tests.

**Complete backend suite:** 4,329 passed, 20 skipped, one warning in 579.63
seconds, exit 0, under the explicit 20-minute limit. All 58 previously failing
GFS cases passed with declared scientific dependencies; no GFS source changes.
The skips are unchanged real-route fixture requirements and explicitly
incomplete route-upload test cases. The warning is Cartopy's existing facecolor
notice in the PPTX exporter test. The earlier incomplete Task 1 run and its
failure inventory remain retained; this is new passing evidence rather than a
rewrite of that record.

Black/Ruff pass for all changed Python files. Document format/lint/link and
final Git checks are recorded with the checkpoint evidence. No application CPU
or RSS savings are claimed from these tests or from Task 1 component figures.

## Evidence, cleanup and next gate

Frozen original and before-change #390/#391 inventories, comparison methodology
and Task 1 component evidence remain unchanged. The 60-minute matched acceptance
and application CPU/RSS measurement remain Task 6; no shortened component run
substitutes for them. The declared test environment includes `eccodes==2.49.0`,
`eccodeslib==2.49.0.30`, `eckitlib==2.3.0.30` and the repository-pinned
scientific dependencies. Shared environments and manifests are untouched.

Raw test logs, review, independent-constructor audit, package inventory,
baseline verification and resource ownership/cleanup are retained in
`.superpowers/sdd/2026-10-21-perf-391-metrics-publication-tasks/evidence/task2/`.
The committed compact results inventory links the final outcomes and
limitations. Rollback has no durable migration: revert the Task 2 source/test
changes to the approved unwired Task 1 state. Actual rollback build/acceptance
remains Task 6.

Host process verification after the full suite found no task-owned runtimes,
servers or detached workers. Final test/client/cache directories are removed
after exact-commit verification; no Compose project, network/volume, browser or
persistent service is retained. Open worktree and hashed evidence are retained.

Stop here. Task 3 replay/source ordering, Task 4 lifecycle invalidation/refresh,
remaining Task 5 HTTP/health and Task 6 operational/performance acceptance all
remain required. PR #403 stays draft, open and unmerged; #391 stays open.
