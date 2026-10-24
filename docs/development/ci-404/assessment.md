# Issue #404: CI family isolation assessment and bounded next experiment

> Archived session evidence from 2026-10-24 at source commit
> `74cbff5146de973c58b5ea0a1c1c76eddb793093`. Local `/tmp` paths and tool chunk
> references below describe the original session; they are not required to use
> this committed handoff. See [the handoff](README.md) for current status.

Status: **DONE_WITH_CONCERNS**. Commits: **none**. This completes a planning
assessment only. It does not authorize measurements, pytest collection, CI
sharding, xdist, or implementation. #391/#408 remain outside scope.

Source identity: clean `docs/404-phase3-assessment`, BASE=HEAD
`74cbff5146de973c58b5ea0a1c1c76eddb793093`; worktree
`/home/oracle-worker/Work/starlink-dashboard/.worktrees/ci404-phase3-assessment`;
Git common directory `/home/oracle-worker/Work/starlink-dashboard/.git`. Source
citations below are repository-relative at that exact head. Policy:
`/tmp/orchestrate-404-20261024/policy.json`, hash
`e4ebf063bb97bbb5cffa6eb4132d4fede0752620b991e0e079da0da651ac2b84`.

## Recommendation and evidence limits

Keep the serial Backend Test Gate while measuring family costs in one unchanged
serial execution. If the distribution supports a useful split, prefer a
separately reviewed small family-job experiment over xdist initially:
independent runner filesystems avoid the known same-host bootstrap collision,
and preserve serial order inside each family. Directory names alone do not
establish isolation or balanced runtime. There is no measured family runtime,
xdist result, new benchmark, speedup, or five-minute feasibility claim in this
assessment.

Historical evidence supplied in the assignment brief, **not rerun or
independently fetched here**:

| Evidence                                     | Observed result                                                                                       | Interpretation                                                      |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Baseline CI `39516546074`                    | Backend 14m34s; 4275 passed / 20 skipped; pytest 788.74s                                              | Uncontrolled historical baseline                                    |
| Stage 1 PR409, normal green CI `40029387522` | Backend 13m55s; 4295 collected; 4275 passed / 20 skipped; pytest 811.10s                              | Interpreter alignment/durations landed; no causal speedup inference |
| Stage 2 accepted investigations              | Simulated-hour call 53–55s locally: 3588 production merges ~25.92s and 57600 fixture responses ~8.14s | Real work; retain ticks, assertions and cache semantics             |
| Stage 2 ordinary-edit fixture                | Setup 2.11–2.21s locally / 2.97–3.11s CI; owned worker 1.32–1.38s; eager exporter import .66–.69s     | Preserve function scope and worker ownership                        |

The 811.10s historical pytest time would require over 2.70× reduction to fit
300s even before setup and gate overhead. This arithmetic is not a forecast.
Current dependencies include ranges, so a commit SHA alone does not reproduce a
resolved environment (`backend/starlink-location/requirements.txt:1–34`).

## Current execution and inventory

`tools/verify:85–115` uses one uv requirement-keyed environment for a Python
3.11 assertion/distribution inventory followed by
`pytest tests/ -q --durations=50 --durations-min=0`. It runs commands
sequentially and returns the first nonzero exit (`tools/verify:258–269`). CI
wraps this unchanged backend command in a 20m timeout with 10s
forced-termination grace (`.github/workflows/lint.yml:72–89`). Top-50 durations
do not establish total per-family cost.

The required gate names currently are **Static Quality Gate**, **Backend Test
Gate**, and **Frontend Test and Build Gate**
(`.github/workflows/lint.yml:10–12,72–74,91–93`). Existing source tests
explicitly expect three thin jobs and canonical commands
(`tools/tests/test_quality_gate_workflow.py:82–107`); a later gate redesign must
deliberately update that contract without losing gate strength.

AST-only inventory (all Python sources parsed as text; no imports or pytest
collection):

| Directory family      | `test_*.py` files | `test_*` function/async definitions | Recognized fixture definitions |
| --------------------- | ----------------: | ----------------------------------: | -----------------------------: |
| unit                  |               195 |                                1811 |                             68 |
| integration           |                51 |                                 347 |                             29 |
| operator              |                62 |                                 282 |                              5 |
| planning              |                29 |                                 312 |                              8 |
| itinerary_import      |                 9 |                                  53 |                              2 |
| root conftest/helpers |                 0 |           1 (`test_client` fixture) |                             12 |

There are 346 test files and 2805 test-named definitions in the five families.
These are **not collected test counts**: parametrization, imported test
functions, plugins and discovery rules can change actual items. All 124
recognized `pytest.fixture` definitions use default function scope; this is
syntax inventory, not proof that every reachable fixture or dependency is
isolated. Discovery uses `tests`, `test_*.py`, `Test*`, `test_*`, strict markers
and automatic asyncio mode (`backend/starlink-location/pytest.ini:4–23`). No
pytest-xdist entry was found in the three backend requirement files; adding it
is a later dependency decision.

## Isolation risks grounded in source

| Surface                          | Existing protection / remaining risk                                                                                                                                                                                                                                                                                                                                                                                                                | Implication                                                                                                                                                                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bootstrap files and environment  | Root conftest creates `STARLINK_TEST_DATA_DIR` default `/tmp/test_data`, routes/POIs and relative `data/missions` before test fixtures; sets background-disable only via `setdefault` (`tests/conftest.py:9–17,25–56`).                                                                                                                                                                                                                             | Same-host concurrent interpreters can share routes/POIs. Set a unique pre-import data root; do not assume `tmp_path` fixes import-time writes. Relative paths require separate working trees or runner filesystems.          |
| Process globals                  | Manager constructors are patched process-wide before importing main; ConfigManager resets, ETA initialization and Prometheus resets repair shared state (`tests/conftest.py:19–78,149–154,179–219,222–320`).                                                                                                                                                                                                                                        | Family-only fresh startup can expose order dependencies; xdist process isolation does not isolate shared disk. No fixture-scope widening is justified.                                                                       |
| Per-test mission/planning stores | Mission root is swapped to `tmp_path` and restored; planning owns routes/POIs, replaces ETA and starts/stops workers; itinerary imports those fixtures (`tests/conftest.py:337–349`; `tests/planning/conftest.py:8–48`; `tests/itinerary_import/conftest.py:1–7`).                                                                                                                                                                                  | Useful existing ownership, retain it. Constructor monkeypatches and import order still need validation.                                                                                                                      |
| SQLite                           | Operator service opens a store under `tmp_path`, closes it, and API fixture closes runtime (`tests/operator/conftest.py:58–97`); slide cache defaults below `storage.MISSIONS_DIR` (`app/mission/slide_cache/store.py:156–157`).                                                                                                                                                                                                                    | Separate roots must include DB, WAL/SHM, lock and cache files; no shared cache/store across jobs.                                                                                                                            |
| Subprocess/ports                 | Responsiveness fixture reserves loopback port 0, passes FD, records PID/PGID and verifies listener/group removal (`tests/integration/test_customer_export_responsiveness.py:28–92`). Operator fault workers use private process sessions and cleanup records (`tests/operator/process_helpers.py:18–66`). GFS tests spawn real worker/decoder children (`tests/unit/test_gfs_worker.py:37–73,101–147`).                                             | Port-0 example is favorable, not an all-suite port audit. Outer timeout alone cannot reap children that start new sessions; record descendant ownership and verify after cancellation.                                       |
| Cross-family imports/plugins     | Integration imports planning test helpers (`tests/integration/test_planning_policy_preview.py:12`); itinerary imports planning fixtures/test helpers (`tests/itinerary_import/conftest.py:3–7`; `tests/itinerary_import/test_migration.py:7`); unit imports integration helpers (`tests/unit/test_pop_status_continuity.py:38`); exporter test loads another test module with `pytest_plugins` (`tests/unit/test_legacy_export_concurrency.py:12`). | Families are selection boundaries, not hermetic import boundaries. Keep entire checkout available and compare actual node IDs, including imported items; do not copy family directories into reduced packages.               |
| Network/cartography              | Archive reader uses MockTransport (`tests/unit/test_telemetry_archive_reader.py:50–53`); map concurrency test explicitly suppresses Natural Earth downloads (`tests/unit/test_legacy_export_concurrency.py:27–29`), while production exporter imports cartopy and adds coastlines/features (`app/mission/exporter/__main__.py:29–30,660–662`).                                                                                                      | These examples do not prove offline coverage everywhere. Fresh runners may have different map/cache/network costs; preserve existing assertions/mocks and record cache state, external I/O and unexpected download failures. |

All `tests/...` and `app/...` citations in the table are relative to
`backend/starlink-location/`.

## Alternatives

| Option                     | Benefit                                                                                                 | Cost / unresolved risk                                                                                                                                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Continue serial            | Existing canonical behavior and gate; no parallel resource collisions                                   | Keeps current latency; improved measurement alone offers no speedup                                                                                                                                                                         |
| Separate family jobs       | Fresh runner checkout, `/tmp`, globals and subprocess ownership per job; serial execution within family | Repeats setup/import/collection; scheduling overhead; unit has most source definitions and might dominate; cross-family imports remain; extra runner-minutes                                                                                |
| pytest-xdist on one runner | Potential finer-grained balancing inside a long family                                                  | New dependency/configuration; worker bootstrap shares default `/tmp/test_data` and relative files; repeated imports/collection and child-process/CPU/memory contention; needs worker-specific paths before import and scheduling validation |

Recommendation is conditional, not a finding that family jobs will be faster.
Runner time is roughly the sum of all job setup+execution+teardown, whereas
elapsed critical path is the slowest required branch plus queue/aggregate time.
Extra setup can increase billed runner-minutes while reducing elapsed time;
record both instead of claiming savings from parallelism.

## Proposed next bounded experiment — requires later authorization

**M1: measure serial costs and reconcile discovery only.** Keep
`.github/workflows/lint.yml`, `tools/verify`, requirements, application code,
fixtures and required checks unchanged. Add no xdist and run no concurrent
tests. Prospective experimental file: `tools/ci404_probe.py`, a small temporary
pytest plugin that writes collected node IDs, setup/call/teardown
durations/outcomes, collection errors and session exit code to an explicitly
supplied external artifact. It must not reorder/deselect items, modify
environment, initialize services, change tests, swallow errors or alter pytest
exit status. Prospective evidence is external JSON/logs only; not a general
sharding framework.

Before authorizing M1, review that plugin plus an owned runner command sheet and
pin the exact source, Python executable, dependency distributions, OS/CPU,
invocation and cache state. Use one disposable checkout on the same hosted
runner class as normal CI, with no shared development storage. Register task
root, command/session, PID/PGID and all descendant ownership before launch. Set
`STARLINK_TEST_DATA_DIR` before import to a unique child of that root;
explicitly set `STARLINK_DISABLE_BACKGROUND_TASKS=1`. Preserve other configured
runtime settings/credentials; do not expose environment contents. The checkout
owns relative `data/` writes; retain evidence outside cleanup targets.

Proposed exact pytest invocations from `backend/starlink-location` (variables
are recorded absolute paths; **not executed here**):

```bash
set -euo pipefail
# repo: disposable checkout; probe_out: unique precreated external evidence root
export PYTHONPATH="$repo/tools:$repo/backend/starlink-location"
# Use the Python path supplied by setup-python, matching current UV_PYTHON behavior.
export STARLINK_DISABLE_BACKGROUND_TASKS=1
export STARLINK_TEST_DATA_DIR="$probe_out/serial-bootstrap"
timeout --kill-after=10s 20m uv run --python "$UV_PYTHON" \
  --with-requirements "$repo/backend/starlink-location/requirements-dev.txt" \
  --with-requirements "$repo/backend/starlink-location/requirements-gfs.txt" \
  pytest tests/ -q --durations=50 --durations-min=0 -p ci404_probe \
  --ci404-output="$probe_out/serial.json" --basetemp="$probe_out/serial-tmp"
# Then once per family: unit integration operator planning itinerary_import
# Run sequentially, each with a fresh bootstrap root and its own output/basetemp.
export STARLINK_TEST_DATA_DIR="$probe_out/$family-collection-bootstrap"
timeout --kill-after=10s 3m uv run --python "$UV_PYTHON" \
  --with-requirements "$repo/backend/starlink-location/requirements-dev.txt" \
  --with-requirements "$repo/backend/starlink-location/requirements-gfs.txt" \
  pytest "tests/$family" --collect-only -q -p ci404_probe \
  --ci404-output="$probe_out/$family-collection.json" \
  --basetemp="$probe_out/$family-collection-tmp"
```

Caps: one serial execution and five collection invocations, no automatic
retries; one owned runner, 45m total job limit, per-command caps above.
Dependency resolution is included inside those limits; separately record uv
setup/distribution inventory with the existing `tools/verify:99–109` command in
the command sheet. Summed stage durations from the serial session attribute
setup/call/teardown to the selected node's family; they do not reproduce costs
of independently run families. Preserve exact full logs, plugin artifacts, stage
start/end times and process cleanup records. Preserve ordinary pytest behavior
within each invocation; no early-exit flags are added. The reviewed runner must
check every command's exit status (including timeout), abort before any later
invocation on nonzero, and always run its owned-resource cleanup handler.
Unexpected external I/O, changed inputs, unowned writes or survivors block
further invocations when observed. The snippet's `set -euo pipefail` is a
fail-fast shell baseline, not a complete resource-owning runner. Review explicit
status checks and exit/signal cleanup before M1; do not retry or weaken tests to
complete the sample.

Coverage requirement: compare **multisets of full parameterized node IDs**, not
AST/file counts, against all items collected in the serial full-suite session.
The five family manifests must have pairwise empty intersections and an exact
union equal to the full manifest; fail on duplicates, missing/extra nodes,
zero-item family, collection/setup errors or malformed/missing artifacts. Track
skipped and xfailed items explicitly. Do not hardcode historical 4295 as today's
discovery count. Compare terminal outcome identities and collection count to the
manifest; any discrepancy blocks progression. This is test-selection
reconciliation, not a code-coverage claim.

**Review stop after M1:** publish actual per-family stage sums, slow cases,
setup/import costs, total elapsed time and runner-minutes. If one family
dominates or predicted benefit is marginal after setup, retain serial and close
this experiment without sharding. A source/data/environment change invalidates
direct comparisons. No family execution or CI implementation follows
automatically.

**Required later isolation validation, before any gate replacement:** under
separate reviewed authorization, execute each proposed family alone on its own
fresh runner/checkout, using the same command above with `--collect-only`
removed, `20m` command cap, `-q --durations=50 --durations-min=0`, and unique
artifacts. Require two clean rounds of all five jobs at the same
source/dependency identity, actual overlapping job execution, exact manifest
equality each round, preserved outcomes/skips and zero resource survivors. A
conservative bound is 200 command-minutes plus setup across ten family
invocations; review a tighter budget from M1 before approving those runs.
Compare against serial on matching runner/environment/cache conditions; report
raw samples and noise, not statistical confidence from two rounds. xdist would
require its own worker-path/dependency/isolation experiment and is excluded
here.

## Later CI acceptance and rollback requirements

If measured evidence justifies implementation, prospective files are
`.github/workflows/lint.yml`, `tools/verify`, and their existing contract tests
(`tools/tests/test_verify.py`, `tools/tests/test_quality_gate_workflow.py`),
plus a small reviewed manifest/aggregation helper only if needed. No
application, fixture or dependency change is implied. Preserve ordinary
`./tools/verify backend` as the canonical serial fallback. Keep Static and
Frontend gates intact and **Backend Test Gate** as the single required aggregate
name.

The aggregate must run after every expected family even when dependencies
fail/cancel; require each expected result to be exactly success and validate
artifact identity/coverage. Fail closed on failed/cancelled/skipped/missing
jobs, dependency setup failures, pytest nonzero/collection errors,
empty/malformed/stale artifacts and partition mismatch. Explicitly test these
failure paths with bounded synthetic workflow/helper contract tests before gate
replacement; no `continue-on-error`, omitted family or
success-on-missing-artifact path. A green aggregate cannot be inferred solely
from another successful job or artifact upload. Preserve normal pytest exit
codes; retries, skip inflation and relaxed assertions are not fixes.

Rollback is to retain/restore the current serial Backend Test Gate invocation
and remove only the reviewed optional experiment/sharding additions. Do not
change branch protection, required names, product behavior or #391/#408. Any
coverage, isolation, cancellation, reliability or runner-minute regression stops
rollout for review; there is no automatic merge authorization.

## Verification, ownership and handoff

Actual scope: source/report reading, stdlib AST parsing of test sources, and
this external report. No test imports, pytest collection/execution, dependency
installs, benchmarks, builds, servers, containers, network requests, helpers,
Git changes or commits.

Command evidence in native tool transcript (all nontrivial reads bounded by
`timeout --kill-after=5s 60s`):

- `git status --short --branch` → exit 0, clean branch; native tool transcript
  (initial status output).
- `git rev-parse HEAD --git-common-dir` → exit 0, exact identity above; chunk
  `9394ff`.
- `nl -ba tools/verify`, workflow and conftest/config reads → exit 0; chunks
  `2e94f1`, `eb2ce4`, `bf9471`, `02f0ef`, `f24a54`, `569d73`, `d0c65f`.
- AST inventory and scope/cross-family scans → exit 0, no parse errors; chunks
  `3b7e5a`, `5a018a`. These parse text only and import no project modules.
- Additional bounded `rg`/`nl` reads support the risk table; chunks `cf01d5`,
  `8dbcd5`, `f24a54`, `659185`, `0be360`, `c16b98`, `68512f`, `1dc6e1`. Broad
  searches were truncated, so specific cited files were reread separately.
- Two guessed source paths did not exist:
  `tests/itinerary_import/production_fixture.py` read exited 1; a search
  including `tests/operator/test_lifecycle.py` exited 2. Neither affects cited
  evidence. A no-match fixture-scope `rg` exited 1; AST scope scan supersedes
  it.

Acceptance: A01 is supported by current-source inventory/risk/comparison and
explicitly attributed historical timing; A02 by bounded M1, later validation
stops and gate/rollback contract. A03 remains for independent scoped review and
primary evaluation; this report does not self-approve it.

Concerns: unknown family runtimes, order/import coupling, shared
bootstrap/relative paths, uncensused external I/O and child lifecycles,
dependency drift, extra setup/runner-minutes, and unproven five-minute
feasibility. These constrain later experiments, not the completeness of the
current assessment.

Resource cleanup: no persistent processes, listeners, containers, networks or
volumes were started. Bounded source-reading processes exited. Only owned write
is this report; retain it as evidence. Primary owns final clean-status/ownership
verification and removal of the clean task worktree after handoff.
