# Task 2 report — streaming BuildKit supervision

## Scope completed

- Added `BuildProgressMonitor` and `BuildSupervisionFailure` to classify only qualifying BuildKit progress: a new stage, a new `DONE`, monotonic transfer bytes, or distinct output from an active `RUN` stage.
- Added deterministic fake-clock coverage for repeated spinner/byte frames, qualifying progress classes, the exact 1800-second deadline precedence, stall ledger closure, and startup blocking.
- Reworked final-build execution in `SubprocessComposeExecutor` to stream combined stdout/stderr through a reader queue. Every received line is retained through the existing callback and bounded, credential-redacted diagnostics before supervision consumes it.
- Enforced a 600-second inactivity limit and 1800-second hard deadline. The executor sends SIGTERM to the dedicated process group, waits five seconds, then sends SIGKILL when required.
- Changed the final build invocation to `build --pull --progress=plain`; it no longer supplies `--no-cache`.
- On a supervision failure, `build_final` closes the ledger as unusable with a `build_stalled:` or `build_deadline_exceeded:` reason and a bounded redacted supervision summary. `start_no_build` therefore remains blocked by its existing usable-ledger gate.

## Verification

- RED observed before implementation:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py -k 'progress or stall or deadline'`
  failed because `BuildProgressMonitor` did not exist.
- GREEN/focused suite:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py`
  → `29 passed`.
- Formatting/import checks:
  `python -m black --check tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py`
  and `python -m ruff check --select I ...` both passed.
- Full ruff still reports pre-existing `TRY004` at `compose.py:700` (`ValueError` for an invalid build mapping); it is outside this task's behavior and was not changed.

## Boundaries observed

- No Dockerfiles, runner manifests, documentation, or final-lane invocation were changed.
- No final/diagnostic Docker acceptance execution was run.

## Review-fix round 1

### Corrections

- `_terminate_process_group` now checks dedicated process-group liveness through the full five-second grace period rather than treating leader exit as group exit. It sends `SIGKILL` to a surviving group, then always calls `wait()` for the leader, including `ProcessLookupError` races.
- Supervision failure handling now terminates/reaps first, drains the reader queue through its EOF sentinel, and joins the reader. Each drained line is appended to command output, retained by the runner callback, and retained in bounded/redacted diagnostics exactly once before the raised `BuildSupervisionFailure` is rebuilt.
- RUN-stage progress classification now rejects elapsed/status/spinner-shaped frames and the compose truncation sentinel; changing such frames cannot reset the 600-second inactivity clock. Distinct non-status RUN output remains qualifying progress.
- Added behavioral subprocess coverage for a leader that exits on `SIGTERM` while its same-session child ignores it, asserting a bounded completion, no surviving child PID, and complete once-only retained diagnostics. Added a `ProcessLookupError` race test proving the leader is reaped, plus adversarial parser cases for changing status frames and truncation input.

### Verification

- RED observed before the repair:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py -k 'changing_run_status or surviving_group_descendant or reaps_leader'`
  → `4 failed, 1 passed`; the parser accepted each non-qualifying frame and the surviving child remained alive.
- Focused behavioral regression suite after the repair:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py -k 'changing_run_status or surviving_group_descendant or process_lookup_race'`
  → `5 passed`.
- Focused Compose suite:
  `python -m pytest -q tools/tests/test_acceptance_platform_compose.py`
  → `34 passed`.
- Static checks:
  `python -m black --check tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py`,
  `python -m ruff check --select I tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py`,
  `python -m py_compile tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py`, and `git diff --check` all passed. Full ruff reports only the pre-existing `TRY004` at `compose.py:697`; the new test-file `PLR0402` findings were corrected before final verification.

### Boundaries preserved

- The production limits remain exactly 600 seconds stalled, 1800 seconds hard deadline, and five seconds termination grace.
- No Task 3 runner manifest or documentation was changed.

## Review-fix round 2

### Correction

- Extended `_RUN_STATUS_FRAME` to recognize the BuildKit elapsed status form with an intermediate bracketed stage descriptor (for example, `600.0s [builder 6/7] RUN npm run build`). These changing progress frames are now rejected before distinct active-RUN output is recorded, so they cannot reset the 600-second liveness clock. Genuine non-status command output remains eligible.

### Regression evidence

- Added a deterministic fake-clock regression that feeds three elapsed BuildKit RUN status frames while varying elapsed value, bracketed stage progress, and command text. Before the parser correction, the first frame was incorrectly emitted as `run_output`:
  `python -m pytest -q tests/test_acceptance_platform_compose.py::test_progress_parser_does_not_count_elapsed_buildkit_run_status_frames`
  → `1 failed` with `BuildProgressEvent(kind='run_output', elapsed_seconds=100.0, ...)`.
- After the correction, the same focused regression passed:
  `python -m pytest -q tests/test_acceptance_platform_compose.py::test_progress_parser_does_not_count_elapsed_buildkit_run_status_frames`
  → `1 passed`.
- Focused Compose suite:
  `python -m pytest -q tests/test_acceptance_platform_compose.py`
  → `35 passed`.
- Formatting/import checks:
  `python -m ruff check --select I acceptance/platform/compose.py tests/test_acceptance_platform_compose.py` and
  `python -m ruff format --check acceptance/platform/compose.py tests/test_acceptance_platform_compose.py`
  → both passed.
- `python -m compileall -q acceptance/platform/compose.py tests/test_acceptance_platform_compose.py` and `git diff --check` passed.
- Full ruff still reports the pre-existing out-of-scope `TRY004` at `acceptance/platform/compose.py:697`; no broad lint-cleanup was made.

### Boundaries preserved

- Only the parser and its focused regression coverage changed. No Docker/Compose runtime acceptance was run, per task scope.
