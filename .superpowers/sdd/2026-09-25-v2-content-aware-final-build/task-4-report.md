# Task 4 report — stalled candidate cross-boundary regression

## Scope completed

- Added the production-path regression `test_stalled_candidate_build_never_reaches_startup_or_final_authority`.
- The regression drives the real final runner through `render_task_override` → `resolve_topology` → `build_final` → Task 2 ledger closure → manifest serialization using a controlled stalled Compose executor.
- It proves the exact candidate SHA is rendered as the only private `ACCEPTANCE_CANDIDATE_SHA` build argument for both contract services, final build argv contains `--pull` and excludes `--no-cache`, the stalled ledger record is `closed`, Compose `up --no-build` is never called, final authority is not discoverable, and the manifest is non-final with `build_stalled:` primary detail.
- Tightened the existing Compose stall regression to use a distinct exact candidate SHA and matching ledger key, preserving the isolated candidate-binding and startup-block assertions at the Compose boundary.
- Final runner wiring now propagates the closed Task 2 ledger reason into `BuildSupervisionFailure` so the sealed primary detail retains the classified `build_stalled:`/`build_deadline_exceeded:` failure context while Task 3 continues to project only validated supervision metadata.
- Updated the operations contract and its test to state explicitly that a stalled or deadline-exceeded candidate never reaches no-build startup or final authority.

## TDD evidence

- RED cross-boundary contract:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py -k 'stalled_candidate_build'`
  failed because the production manifest primary detail was only `build_stalled`, rather than the ledger-backed `build_stalled:` classification required by the cross-boundary contract.
- RED documentation contract:
  `python -m pytest -q tools/tests/test_acceptance_platform_docs.py -k 'content_aware_final_build_supervision'`
  failed because the operations documentation did not explicitly state that a stalled candidate cannot reach no-build startup or final authority.
- GREEN focused regressions:
  - `python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py -k 'stalled_candidate_build'` → `1 passed, 90 deselected in 0.95s`.
  - `python -m pytest -q tools/tests/test_acceptance_platform_docs.py -k 'content_aware_final_build_supervision'` → `1 passed, 10 deselected in 0.03s`.

## Final verification

- `python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py tools/tests/test_v2_acceptance_browser_contract.py` → `131 passed in 9.02s`.
- `python -m compileall -q tools/acceptance/platform` completed successfully.
- `node --check tools/acceptance/journeys/v2-mission-retirement.mjs` completed successfully.
- `git diff --check` completed successfully.
- Inspected the final diff; it contains only the stalled-build cross-boundary wiring, Compose/runner/docs regressions, the corresponding operations wording, and this report.

## Scope boundaries

- Did not run Docker final or diagnostic acceptance, push, or create a PR.
- Preserved all pre-existing modified and untracked workspace artifacts, including the pre-existing Task 2 report modification and review files.
