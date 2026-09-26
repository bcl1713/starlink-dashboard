# Tasks 1–2: Final browser lifecycle and adapter failure evidence

Companion to [2026-09-24-v2-acceptance-browser-recovery](2026-09-24-v2-acceptance-browser-recovery.md).

## Task 1: Reusable profile-owned final browser lifecycle

**Files:**

- Modify: `tools/acceptance/platform/health.py`
- Modify: `tools/acceptance/platform/runner.py`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`

**Interfaces:**

- Produces a platform-owned browser-session object containing loopback CDP URL,
  profile-pinned launch identity, task display/profile paths, neutral
  metrics/artifacts, and idempotent cleanup.

- Consumes `PlatformProfile`, task-owned root, and the existing
  `PlatformHealthExecutor` seams.

- `runner._final_steps()` receives the platform-owned session rather than
  reading `RunnerInputs.browser_session` for production final acceptance.

- [ ] **Step 1: Write failing lifecycle tests**

Add a fake profile bundle, fake Xvfb/browser processes, and fake CDP/card seams
proving that final-session provisioning:

```python
def test_final_session_uses_profile_pinned_headed_xvfb_and_requires_neutral_metrics(...):
    session = health.start_final_browser_session(profile, task_root, executor)
    assert session.cdp_url.startswith("http://127.0.0.1:")
    assert "--display=:" in fake_launch.arguments
    assert "--headless" not in fake_launch.arguments
    assert session.metrics["raster"] == [1920, 1080]


def test_final_session_rejects_mismatched_neutral_metrics_before_build(...):
    with pytest.raises(ValueError, match="neutral viewport"):
        health.start_final_browser_session(profile, task_root, mismatched_executor)
    assert build_calls == []
```

Add runner coverage proving a final lane with default dependencies starts the
platform session before `build_final`, passes its CDP URL to `_run_journey`, and
invokes browser cleanup on failure.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_health.py -k
'final_session' tools/tests/test_acceptance_platform_runner.py -k
'platform_session'`

Expected: FAIL because no reusable final browser lifecycle exists and final
still consumes caller session input.

- [ ] **Step 3: Implement the minimal platform lifecycle**

Refactor existing health resource allocation, readiness, neutral card, log
retention, and cleanup into a small session owner. It must:

```python
@dataclass
class PlatformBrowserSession:
    cdp_url: str
    metrics: Mapping[str, Any]
    artifacts: Mapping[str, bytes]
    def close(self) -> None: ...


def start_final_browser_session(profile, task_root, executor) -> PlatformBrowserSession:
    # verify bundle; allocate Xvfb/CDP/profile under task root;
    # launch headed profile executable; wait readiness; run/validate neutral card;
    # return session; on any error clean all owned resources then re-raise.
```

Keep health behavior unchanged by using the same lifecycle internally. In final
runner flow, arm a composite cleanup owner before browser or topology creation;
browser provisioning and neutral validation occur before `build_final`. Retain
browser/Xvfb logs as artifacts through the runner’s sole evidence writer. Reject
default final execution when `browser_session` is caller-supplied rather than
platform-owned; preserve injectable test seams only.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_health.py -k 'final_session
or cleanup' tools/tests/test_acceptance_platform_runner.py -k 'platform_session
or final_requires'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/health.py tools/acceptance/platform/runner.py \
  tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py
git commit -m "fix(acceptance): own final browser lifecycle"
```

## Task 2: Prompt adapter termination and bounded failure evidence

**Files:**

- Modify: `tools/acceptance/journeys/v2-mission-retirement.mjs`
- Modify: `tools/acceptance/platform/runner.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**

- Adapter CLI exits promptly after a thrown journey error and writes its
  original stack to stderr.

- `_bounded_adapter_process()` returns a typed result carrying `stdout`,
  `stderr`, `returncode`, and `timed_out`; it does not discard captured bytes.

- `_run_journey()` adds bounded `adapter.stdout.log` and `adapter.stderr.log` to
  failure evidence and distinguishes non-zero exit from deadline expiry.

- [ ] **Step 1: Write failing tests**

Use an executable temporary ESM adapter that writes `Error: exact failure` to
stderr and keeps an event-loop handle open unless its attachment is disposed.
Assert the runner reports the original error rather than `timed out` and writes
bounded logs into sealed failure evidence.

```python
def test_adapter_nonzero_exit_retains_stderr_and_is_not_classified_as_timeout(...):
    result = run(...)
    assert "exact failure" in result.manifest["primary"]["detail"]
    assert "timed out" not in result.manifest["primary"]["detail"]
    assert (failure_root / "adapter.stderr.log").read_bytes() == b"Error: exact failure\n"


def test_adapter_deadline_retains_bounded_partial_stderr(...):
    ...
    assert "adapter timed out" in result.manifest["primary"]["detail"]
    assert len(retained_stderr) <= runner._MAX_ADAPTER_STDERR_BYTES
```

Add a source-contract test requiring the adapter CLI to dispose/close its
browser attachment in `finally` and then terminate non-zero without retaining a
CDP handle.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py -k
'adapter_nonzero or adapter_deadline'
tools/tests/test_v2_acceptance_browser_contract.py -k 'dispose'`

Expected: FAIL because current timeout handling raises before returning retained
diagnostics and adapter CLI only sets `process.exitCode`.

- [ ] **Step 3: Implement the minimal adapter/runner failure contract**

In the adapter entry point, hold the Playwright browser attachment in a
variable, use `try/finally` to close/disconnect it after
`runV2MissionRetirement`, and write the original error stack before explicit
termination. Preserve the lifecycle session’s existing `finally` detach.

In Python, introduce a bounded adapter process result and a private exception
that carries captured bytes. On non-zero exit, retain allowed stdout/stderr
artifacts and raise `ValueError("product journey adapter exited non-zero:
...")`. On deadline expiry, kill/reap the child, retain bounded partial output,
and raise `ValueError("product journey adapter timed out: ...")`. Do not change
successful payload validation.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py -k 'adapter_'
tools/tests/test_v2_acceptance_browser_contract.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/journeys/v2-mission-retirement.mjs \
  tools/acceptance/platform/runner.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_v2_acceptance_browser_contract.py
git commit -m "fix(acceptance): retain prompt adapter failures"
```

[Return to the main plan](2026-09-24-v2-acceptance-browser-recovery.md).
