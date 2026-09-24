# Task 8 report — runner-owned origin and Xvfb cleanup

## Scope completed

- Final execution now rejects any caller-supplied browser session before either default or test-seam final execution.
- After the runner starts its owned browser session, it replaces any caller-provided deployed origin with exactly `http://127.0.0.1:{frontend_port}`.
- Xvfb cleanup now terminates/reaps the owned process before it considers the display socket. It removes only a surviving Unix socket, and fails closed without removing it when the owned Xvfb process remains alive.
- The documented final-run authority and cleanup sequence now state both invariants.
- No Docker/Compose runtime, health/static/final/browser lane, push, external cleanup, or retained-evidence deletion was performed.

## Strict TDD evidence

### RED

```text
python -m pytest \
  tools/tests/test_acceptance_platform_runner.py::test_final_runner_replaces_caller_origin_with_its_exact_loopback_frontend_port \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_removes_owned_xvfb_socket_only_after_xvfb_exits \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_keeps_xvfb_socket_when_owned_xvfb_is_still_alive -q
```

Result: `3 failed`.

- The browser-card seam received `https://caller.invalid` rather than the exact loopback origin.
- The Xvfb socket-cleanup seam did not exist, so both lifecycle tests failed at that missing behavior.

### GREEN

```text
python -m pytest \
  tools/tests/test_acceptance_platform_runner.py::test_final_runner_replaces_caller_origin_with_its_exact_loopback_frontend_port \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_removes_owned_xvfb_socket_only_after_xvfb_exits \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_keeps_xvfb_socket_when_owned_xvfb_is_still_alive -q
```

Result: `3 passed in 1.57s`.

## Verification

```text
python -m pytest tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_health.py -q
```

Result: `67 passed in 6.89s`.

```text
python -m compileall -q tools/acceptance/platform tools/tests
git diff --check
```

Result: both commands exited `0`.
