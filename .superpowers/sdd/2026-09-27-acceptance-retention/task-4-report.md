# Task 4 report — scoped Docker, workspace, and Git-worktree lifecycle

## Delivered

- Added `AcceptanceOwnershipLabels` in `tools/acceptance/platform/compose.py` with the required owner, lane, SHA, and task labels. Its `as_docker_args()` exposes the complete exact label set for scoped Docker operations.
- Threaded the label set through rendered Compose services, build image labels, named networks, and named volumes. The sealed topology validator rejects any service, build, network, or volume whose label set differs from the exact task ownership set.
- Added `scoped_docker_inventory(...)` in `maintenance.py`. It inventories containers, images, networks, and volumes only through four exact label filters. It contains no prune operation; volume handling is read-only inventory.
- Added `DockerImage`, `DockerRetentionReport`, `remove_scoped_docker_resource(...)`, and `retain_docker_resources(...)`. Image deletion is conditional on all of the following:
  - an unchanged exact re-inspected ID;
  - all four required ownership labels and owner value `runner`;
  - an eligible SHA supplied by the Task 2 selection boundary;
  - no remaining container or protected-ledger reference.
  Removal is by exact inspected image ID and is verified afterwards; uncertainty or a surviving ID is recorded as an anomaly rather than deleted.
- Left Task 3’s validated exact-worktree cleanup intact. It uses `git worktree remove --force <exact checkout>` after liveness, marker, detached-HEAD, SHA, and clean-tree proof; it does not invoke broad `git worktree prune`.

## TDD evidence

1. Added the ownership/no-prune test and observed RED because `AcceptanceOwnershipLabels` did not exist:
   `ImportError: cannot import name 'AcceptanceOwnershipLabels'`.
2. Implemented labels and inventory; the focused test passed.
3. Added the exact-ID/reference-refusal test and observed RED because `DockerImage` did not exist:
   `ImportError: cannot import name 'DockerImage'`.
4. Implemented inspected-ID retention checks; both scoped-resource tests passed.
5. Added a final-topology tampering regression and observed RED (`Failed: DID NOT RAISE ValueError`); implemented exact ownership-label validation; focused label/tampering tests passed.

## Verification

- `PYTHONPATH=tools pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_retention.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_scoped_resources.py`
  - `175 passed in 6.96s`
- `python -m py_compile tools/acceptance/platform/compose.py tools/acceptance/platform/maintenance.py tools/tests/test_acceptance_platform_scoped_resources.py && git diff --check`
  - passed.
- `ruff check` found two pre-existing findings in untouched `compose.py` (`TRY004` and `F402`); the new-test import-order finding was fixed before commit.

## Commit

- `f20dd3bb feat: bound runner-owned acceptance resources`

## Changed files

- `tools/acceptance/platform/compose.py`
- `tools/acceptance/platform/maintenance.py`
- `tools/tests/test_acceptance_platform_compose.py`
- `tools/tests/test_acceptance_platform_scoped_resources.py` (new)

No publish workflow, user documentation, plan, or retention ledger files were modified.

## Review repair (Task 4 follow-up)

- Added required `--acceptance-task` parsing and wrapper forwarding. The runner now validates the wrapper-compatible task identifier and passes the exact task plus `inputs.lane.value` into `render_task_override`; labels no longer derive task identity from the task-root basename or default every lane to `final`.
- Wired the normal final cleanup boundary to exact-label inventory and exact-ID image retention/removal. The runner adapter lists only its complete label set, re-inspects every candidate, blocks images named by a build ledger or container, removes only eligible exact IDs, and treats a retained/unsafe resource as cleanup failure. No global Docker or Git prune is used.
- Made the fake Docker removal stateful, so successful removal proves post-removal reinspection absence. Added refusal coverage for changed IDs, incomplete labels, ineligible SHAs, and protected ledger references.

### RED → GREEN evidence

- Focused RED initially failed because `--acceptance-task` was not accepted by runner argument parsing; it became accepted and required after the runner/wrapper change.
- Focused GREEN: `pytest -q tools/tests/test_acceptance_platform_scoped_resources.py tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py` → `121 passed in 15.61s`.
- Broad suite: `pytest -q tools/tests` → `1381 passed, 1 skipped, 3 failed`. The failures are outside this change set: missing Grafana Infinity plugin declaration and two `tools/verify` tests blocked by required `ACCEPTANCE_POLICY_BASE_SHA`.
- `git diff --check` passed.

## Review repair round 2

- Passed the configured `RunnerInputs.ledger_root` into the final cleanup resource. `_ScopedDocker` now reads that exact ledger root, so a protected image referenced only by an alternate ledger is retained and no exact-ID image removal is issued.
- Added a task-owned Buildx lifecycle through `_ScopedDocker`: the final path creates and selects deterministic `acceptance-<task>-<sha12>` `docker-container` builder before the final build, applies all four ownership labels through BuildKit daemon flags, bootstraps it, and validates the builder-container labels.
- Cleanup re-inspects the exact builder and its labels, runs only `docker buildx rm <exact-name>` (which removes that builder's local cache), then verifies the named builder is absent. It never invokes a Docker/Buildx prune command. Wrong labels refuse removal; unsupported Buildx produces a bounded cleanup failure rather than a broad fallback.

### RED → GREEN evidence

1. Alternate-ledger cleanup test RED: `_cleanup_default` unpacked only `(topology, executor)`, producing `too many values to unpack (expected 2)` when passed the configured ledger root.
2. After threading `inputs.ledger_root` through the resource, that regression passed and confirmed no `docker image rm sha256:protected` command.
3. Buildx lifecycle tests RED: `_ScopedDocker` had no `create_task_builder` / `remove_task_builder` methods (`AttributeError`).
4. Implemented the adapter lifecycle; deterministic creation, four-label validation, exact removal/absence, unsupported Buildx, and no-prune assertions pass without calling local Buildx.

### Verification

- `pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_scoped_resources.py` → `79 passed in 5.39s`.
- `pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_retention.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_scoped_resources.py` → `184 passed in 8.90s`.
- `python -m compileall -q tools/acceptance/platform/runner.py tools/tests/test_acceptance_platform_runner.py && git diff --check` → passed.
- Repository-wide `pytest -q` remains blocked at collection by pre-existing environment/test-root problems: missing `spacex_api`, incompatible protobuf runtime for `grpc_reflection`, and `test_bounds.py` requiring `/app`.
