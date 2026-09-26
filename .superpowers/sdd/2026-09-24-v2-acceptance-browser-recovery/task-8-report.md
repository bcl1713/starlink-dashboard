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

## Review-fix round 1 — identity-safe X socket cleanup and default path

### RED

```text
python -m pytest \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_does_not_unlink_a_socket_rebound_at_the_x_display_path \
  tools/tests/test_acceptance_platform_runner.py::test_default_final_runner_passes_the_exact_runner_owned_origin_to_final_steps -q
```

Result: `1 failed, 1 passed in 0.34s`.

- The X-display race test failed before implementation because no atomic pathname-claim primitive existed (`AttributeError: _rename_exchange`).
- The default final-path origin test passed against the prior Task 8 origin implementation, recording the exact generated `http://127.0.0.1:23456`; it closes the previously missing coverage gap rather than changing already-correct runner behavior.

### GREEN

```text
python -m pytest \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_removes_owned_xvfb_socket_only_after_xvfb_exits \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_does_not_unlink_a_socket_rebound_at_the_x_display_path \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_keeps_xvfb_socket_when_owned_xvfb_is_still_alive \
  tools/tests/test_acceptance_platform_runner.py::test_final_runner_replaces_caller_origin_with_its_exact_loopback_frontend_port \
  tools/tests/test_acceptance_platform_runner.py::test_default_final_runner_passes_the_exact_runner_owned_origin_to_final_steps -q
```

Result: `5 passed in 0.30s`.

- The session records the task-owned Xvfb socket device/inode identity after readiness.
- Cleanup atomically exchanges the contested X-display pathname with a task guard before checking identity. A replacement is restored and retained; only the parked, recorded task socket is removed.
- The default `final_steps is None` path now has direct coverage for the exact runner-owned origin.

### Review-fix verification

```text
python -m pytest tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_health.py -q
python -m compileall -q tools/acceptance/platform tools/tests
git diff --check
```

Result: `69 passed in 3.16s`; compile and diff checks exited `0`.

## Review-fix round 2 — private final disposition

### RED

```text
python -m pytest \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_keeps_replacement_bound_during_private_final_disposal -q
```

Result: `1 failed in 0.16s`.

- The exchange-guard implementation had no private final-disposal path; its
  final cleanup never entered a task-private `.task-xvfb-*` parent, so the
  regression assertion that injected a replacement at that phase failed.

### GREEN

- Cleanup atomically renames the public display entry into a newly created
  mode-`0700` task quarantine, then checks the recorded socket identity there.
- A matching task socket is unlinked only below that private parent. A server
  that binds the public display path after the atomic rename is never an unlink
  target for this task.
- A nonmatching entry is left quarantined and the cleanup error reports its
  location for later trusted-parent handling; it is not restored over any
  potentially new public display binding.

```text
python -m pytest \
  tools/tests/test_acceptance_platform_health.py::test_session_cleanup_keeps_replacement_bound_during_private_final_disposal -q
```

Result: `1 passed in 0.06s`.

### Verification

```text
python -m pytest tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_acceptance_platform_health.py -q
python -m compileall -q tools/acceptance/platform tools/tests
git diff --check
```

Result: `70 passed in 11.08s`; compile, Black, and diff checks exited `0`.
