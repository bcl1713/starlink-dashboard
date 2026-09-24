# Final rework 7 — query-safe Create Mission fixture

- Updated `frontend/mission-planner/tests/e2e/mission-workflow.spec.ts` only: collection fixtures for `/api/v2/missions` now use `requestUrlPattern(test.info().project.use.baseURL, '/api/v2/missions')`, which accepts query-bearing collection requests while excluding detail paths.
- The explicit `/api/v2/missions/new-mission` detail fixture remains an isolated exact URL route and fulfills the mission object.
- Verification: `npx playwright test --list tests/e2e/mission-workflow.spec.ts` discovered five Chromium tests; `npx eslint tests/e2e/mission-workflow.spec.ts && npx tsc -b --pretty false` passed; one focused Chromium execution passed: `should create a new mission` (1 passed, 1.3m).
- Focused browser startup succeeded. Build emitted pre-existing/non-blocking Node `DEP0205` and Vite chunk-size warnings.

## Critical browser process-group cleanup

- `tools/acceptance/platform/health.py` now terminates the task-owned Chrome process group whenever launch PID/session ownership is known, even when the direct Chrome leader has already exited. It probes the group after `SIGTERM`, escalates surviving descendants to `SIGKILL`, and fails closed if the group cannot be proved absent.
- Cleanup verification now independently checks the process group as well as the task CDP listener, X display, and profile path; cleanup signal/verification errors convert health authority to `ENVIRONMENT_BLOCKED` instead of recording success.
- Added deterministic leader-exits-first regression coverage in `tools/tests/test_acceptance_platform_health.py`; it models an exited group leader with a surviving descendant and verifies `SIGTERM`, probe, `SIGKILL`, and final absence probe.
- Verification: `python -m pytest -q tools/tests/test_acceptance_platform_health.py` (16 passed); `python -m pytest -q tools/tests/test_acceptance_platform_*.py` (83 passed); `black --check tools/acceptance/platform/health.py tools/tests/test_acceptance_platform_health.py`; `ruff check tools/acceptance/platform/health.py tools/tests/test_acceptance_platform_health.py`; `python -m compileall -q tools/acceptance/platform/health.py`; `git diff --check`.
