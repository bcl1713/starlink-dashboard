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
