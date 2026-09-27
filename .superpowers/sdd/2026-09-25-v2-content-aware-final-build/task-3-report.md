# Task 3 report — sealed final build supervision

## Scope completed

- Added a final-manifest `build_supervision` projection for typed `BuildSupervisionFailure` values. Its only serialized keys are `policy_version`, `stall_window_seconds`, `hard_deadline_seconds`, `elapsed_seconds`, `last_progress_kind`, and `last_progress_elapsed_seconds`.
- The projection uses the Task 2 build-reconciliation supervision record when the production final path catches a build supervision failure, and deliberately excludes event detail and Compose output from the manifest.
- Added allowlist validation before serialization: exact key set, fixed policy and limits, allowed progress kinds, finite numeric values in range, and a 128-byte UTF-8 limit for every string field. Invalid metadata raises rather than being emitted.
- Updated the final-build operator contract to describe lockfile-keyed dependency-layer reuse, candidate-SHA application/output rebuilding, `--pull`, the 600-second meaningful-progress stall limit, the 1800-second deadline, sealed `build_stalled`/`build_deadline_exceeded` evidence, and no automatic retry without fresh health/static and operator approval.

## TDD evidence

- RED runner contracts:
  `python -m pytest -q tools/tests/test_acceptance_platform_runner.py -k 'allowlisted_stall_supervision or excludes_oversize_supervision_event_detail'`
  failed with two expected `KeyError: 'build_supervision'` failures.
- RED documentation contract:
  `python -m pytest -q tools/tests/test_acceptance_platform_docs.py -k content_aware_final_build_supervision`
  failed because the prior documentation did not contain the required content-aware build policy.

## Final verification

- `python -m pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py` → `62 passed in 4.01s`.
- `python -m compileall -q tools/acceptance/platform` completed successfully.
- `python -m ruff check --select I tools/acceptance/platform/runner.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py` → `All checks passed!`.
- `git diff --check` completed successfully.
- Added-line security scan found no hardcoded credentials, shell execution, dynamic evaluation, or unsafe deserialization patterns.

## Scope boundaries

- Changed only the Task 3 runner, runner/docs contract tests, operations documentation, and this report.
- Did not modify Compose supervision, Dockerfiles, run final/diagnostic Docker acceptance, push, or create a PR.
- Preserved all pre-existing modified and untracked workspace artifacts.

## Review correction — Task 2 ledger validation

- Replaced synthetic `RunnerDependencies.final_steps` supervision tests with production-path tests that execute the default `_final_steps` flow through controlled Task 2 `build_final`/`BuildLedger` seams.
- `_final_steps` now requires a closed Task 2 supervision record with exactly `kind` and `last_event`. The failure kind must match the raised `BuildSupervisionFailure`; `last_event` must be `None` or exactly `kind`, `elapsed_seconds`, and `detail`.
- The validator rejects absent records, extra fields, unsupported progress kinds, non-finite or out-of-range timings, and strings over 128 UTF-8 bytes. The final six-field manifest projection is derived only from this validated ledger record.
- Invalid Task 2 metadata is converted to a classified finalization failure. It writes sealed non-final evidence under `failures/<sha>`, never writes a candidate root or discovery authority, and retains no `build_supervision` value or arbitrary ledger detail.
- Production-path regression coverage includes valid `build_stalled` and `build_deadline_exceeded` records, plus absent, extra-field, non-finite, and oversize ledger metadata.

## Review-correction verification

- RED: `python -m pytest -q tools/tests/test_acceptance_platform_runner.py -k 'production_final_steps'` initially failed 4 tests: valid ledger input was reconstructed from the exception while absent/malformed ledger metadata still published normal candidate evidence.
- GREEN: `python -m pytest -q tools/tests/test_acceptance_platform_runner.py -k 'production_final_steps'` → `5 passed, 51 deselected`.
- Focused runner/docs suite: `python -m pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py` → `65 passed in 8.43s`.
- Static/import and compilation: `python -m ruff check --select I tools/acceptance/platform/runner.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py && python -m compileall -q tools/acceptance/platform` → `All checks passed!`.
- `git diff --check` passed. A full `python -m pytest -q` collection remains blocked by pre-existing environment failures: missing `spacex_api`, incompatible protobuf generated/runtime versions, and `test_bounds.py` requiring `/app`.
