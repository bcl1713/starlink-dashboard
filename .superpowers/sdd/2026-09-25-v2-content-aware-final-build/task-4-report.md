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

## Review repair 1 — sealed Task 3 projection in cross-boundary regression

- Extended only `test_stalled_candidate_build_never_reaches_startup_or_final_authority`; production code, Compose behavior, documentation, and isolated Task 3 projection tests were left unchanged.
- The real stalled path now asserts the complete strict Task 3 `build_supervision` mapping:
  - `policy_version: build_supervision.v1`
  - `stall_window_seconds: 600`
  - `hard_deadline_seconds: 1800`
  - `elapsed_seconds: 600.0`
  - `last_progress_kind: stage`
  - `last_progress_elapsed_seconds: 0.0`
- The expected progress kind is `stage` because the controlled cross-boundary executor raises `BuildSupervisionFailure` with `BuildProgressEvent("stage", 0.0, ...)`; the closed-ledger projection must preserve that actual event classification rather than invent `run_output`.
- RED: the new sealed-supervision assertion was first run with `last_progress_kind: run_output`; the focused command failed exactly on the new manifest assertion (`stage != run_output`). This confirmed the test observes the real closed-ledger projection. The expectation was corrected to the executor's actual `stage` event before GREEN.
- The same test now reads the retained SHA-qualified candidate `runner-manifest.json`, asserts its non-final authority and identical strict supervision mapping, and calls `verify_manifest(candidate)` to recompute the retained manifest inventory and `SHA256SUMS` checksums.
- Existing candidate build-argument binding, final build argv policy, closed ledger reason, startup blocking, primary classification, and discoverability assertions remain intact.

## Repair verification

- `python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py -k 'stalled_candidate_build'` → RED: `1 failed, 90 deselected` on the deliberately incorrect `run_output` expectation; GREEN: `1 passed, 90 deselected in 1.36s`.
- `python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py tools/tests/test_v2_acceptance_browser_contract.py` → `131 passed in 15.60s`.
- `python -m compileall -q tools/acceptance/platform && node --check tools/acceptance/journeys/v2-mission-retirement.mjs` → success.
- `git diff --check` and `git diff --check 774b3c6e17b465ad713017f2a217e07b0f8eb653..HEAD` → success.
- No Docker acceptance run, push, PR, final acceptance claim, or diagnostic runtime run was performed.
