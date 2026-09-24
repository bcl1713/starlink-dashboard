# V2 Acceptance Browser Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make final V2 acceptance use the profile-certified headed browser lifecycle and preserve prompt, bounded adapter failures instead of masking them as timeouts.

**Architecture:** Extract a reusable platform-owned browser session lifecycle from health so final acceptance can allocate, prove, retain, and clean a headed Xvfb/CDP session without accepting caller-controlled browser authority. Make adapter subprocess failures carry bounded stdout/stderr into sealed failure evidence. Ensure the V2 adapter explicitly disconnects its CDP attachment after either success or failure.

**Tech Stack:** Python 3.11, pytest, subprocess/Xvfb/Chromium CDP, Node ESM, Playwright, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-24-v2-acceptance-browser-recovery-design.md`

## Global Constraints

- Use only the administrator-provisioned profile executable; do not download, install, or substitute a browser.
- Final browser evidence must be headed Xvfb, native 1920×1080 viewport/raster, DPR 1; no headless or emulated substitution.
- Product contracts remain product-only and cannot contain browser/process/port/cleanup authority.
- Preserve original adapter errors in bounded sealed diagnostics; do not replace an exited adapter failure with a timeout.
- Final runner execution is one tracked 900-second monitored process with durable logs; no automatic final retry.
- All temporary browser, display, Compose, profile, task-root, listener, and process cleanup must be verified; retain volumes and durable evidence.
- Documentation impact is in scope; no product UI or mission semantics change.

## Review Focus

- A caller provides a loopback CDP URL for final acceptance: the runner must not accept it as a substitute for the profile-owned headed session.
- The browser starts and `/json/version` responds but neutral screenshot/metrics are not exact 1920×1080/DPR 1: fail before final build claim.
- The adapter writes a useful error then leaves a CDP socket open: the process must terminate promptly and runner evidence must retain that exact bounded error.
- Adapter stdout/stderr exceeds its retention budget: fail closed without unbounded memory/file growth.
- Browser/Xvfb or Compose cleanup fails after an adapter failure: preserve the primary failure, downgrade the claim, and record cleanup independently.

---

### Task 1: Reusable profile-owned final browser lifecycle

**Files:**
- Modify: `tools/acceptance/platform/health.py`
- Modify: `tools/acceptance/platform/runner.py`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`

**Interfaces:**
- Produces a platform-owned browser-session object containing loopback CDP URL, profile-pinned launch identity, task display/profile paths, neutral metrics/artifacts, and idempotent cleanup.
- Consumes `PlatformProfile`, task-owned root, and the existing `PlatformHealthExecutor` seams.
- `runner._final_steps()` receives the platform-owned session rather than reading `RunnerInputs.browser_session` for production final acceptance.

- [ ] **Step 1: Write failing lifecycle tests**

Add a fake profile bundle, fake Xvfb/browser processes, and fake CDP/card seams proving that final-session provisioning:

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

Add runner coverage proving a final lane with default dependencies starts the platform session before `build_final`, passes its CDP URL to `_run_journey`, and invokes browser cleanup on failure.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_health.py -k 'final_session' tools/tests/test_acceptance_platform_runner.py -k 'platform_session'`

Expected: FAIL because no reusable final browser lifecycle exists and final still consumes caller session input.

- [ ] **Step 3: Implement the minimal platform lifecycle**

Refactor existing health resource allocation, readiness, neutral card, log retention, and cleanup into a small session owner. It must:

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

Keep health behavior unchanged by using the same lifecycle internally. In final runner flow, arm a composite cleanup owner before browser or topology creation; browser provisioning and neutral validation occur before `build_final`. Retain browser/Xvfb logs as artifacts through the runner’s sole evidence writer. Reject default final execution when `browser_session` is caller-supplied rather than platform-owned; preserve injectable test seams only.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_health.py -k 'final_session or cleanup' tools/tests/test_acceptance_platform_runner.py -k 'platform_session or final_requires'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/health.py tools/acceptance/platform/runner.py \
  tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py
git commit -m "fix(acceptance): own final browser lifecycle"
```

### Task 2: Prompt adapter termination and bounded failure evidence

**Files:**
- Modify: `tools/acceptance/journeys/v2-mission-retirement.mjs`
- Modify: `tools/acceptance/platform/runner.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**
- Adapter CLI exits promptly after a thrown journey error and writes its original stack to stderr.
- `_bounded_adapter_process()` returns a typed result carrying `stdout`, `stderr`, `returncode`, and `timed_out`; it does not discard captured bytes.
- `_run_journey()` adds bounded `adapter.stdout.log` and `adapter.stderr.log` to failure evidence and distinguishes non-zero exit from deadline expiry.

- [ ] **Step 1: Write failing tests**

Use an executable temporary ESM adapter that writes `Error: exact failure` to stderr and keeps an event-loop handle open unless its attachment is disposed. Assert the runner reports the original error rather than `timed out` and writes bounded logs into sealed failure evidence.

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

Add a source-contract test requiring the adapter CLI to dispose/close its browser attachment in `finally` and then terminate non-zero without retaining a CDP handle.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py -k 'adapter_nonzero or adapter_deadline' tools/tests/test_v2_acceptance_browser_contract.py -k 'dispose'`

Expected: FAIL because current timeout handling raises before returning retained diagnostics and adapter CLI only sets `process.exitCode`.

- [ ] **Step 3: Implement the minimal adapter/runner failure contract**

In the adapter entry point, hold the Playwright browser attachment in a variable, use `try/finally` to close/disconnect it after `runV2MissionRetirement`, and write the original error stack before explicit termination. Preserve the lifecycle session’s existing `finally` detach.

In Python, introduce a bounded adapter process result and a private exception that carries captured bytes. On non-zero exit, retain allowed stdout/stderr artifacts and raise `ValueError("product journey adapter exited non-zero: ...")`. On deadline expiry, kill/reap the child, retain bounded partial output, and raise `ValueError("product journey adapter timed out: ...")`. Do not change successful payload validation.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py -k 'adapter_' tools/tests/test_v2_acceptance_browser_contract.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/journeys/v2-mission-retirement.mjs \
  tools/acceptance/platform/runner.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_v2_acceptance_browser_contract.py
git commit -m "fix(acceptance): retain prompt adapter failures"
```

### Task 3: Operator workflow and regression suite

**Files:**
- Modify: `docs/operations/acceptance-platform.md`
- Modify: `tools/tests/test_acceptance_platform_docs.py`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**
- Documents final browser ownership, neutral preflight, 900-second monitored execution, diagnostic log paths, and recovery authorization/ledger rules.
- Leaves product contracts unchanged and browser operational authority platform-owned.

- [ ] **Step 1: Write failing documentation assertions**

Add assertions requiring the operator guide to contain the concepts and literal terms:

```python
assert "headed Xvfb" in guide
assert "900-second" in guide
assert "adapter.stderr.log" in guide
assert "explicit authorization" in guide
assert "final build ledger" in guide
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_docs.py`

Expected: FAIL because the guide does not yet prescribe the new final-browser and recovery behavior.

- [ ] **Step 3: Update the operator guide**

Document this concrete order:

1. run and checksum-verify health;
2. run static only after health;
3. issue final through one tracked process, 900-second budget, durable stdout/stderr;
4. runner owns headed Xvfb/CDP browser resources and pre-journey native metrics;
5. inspect sealed `adapter.stdout.log`/`adapter.stderr.log` on failure;
6. after interruption, inspect ledger/images/task resources and obtain explicit human authorization before a recovery attempt;
7. verify cleanup without deleting volumes.

State explicitly that callers must not hand-launch a headless browser as final acceptance evidence.

- [ ] **Step 4: Run all platform regression tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_*.py tools/tests/test_v2_acceptance_browser_*.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/operations/acceptance-platform.md tools/tests/test_acceptance_platform_docs.py
git commit -m "docs(acceptance): document final browser recovery"
```

### Task 4: Exact-head acceptance evidence

**Files:**
- Modify: no tracked files.
- Evidence: external SHA-qualified health, static, final, and report roots only.

**Interfaces:**
- Consumes the published candidate SHA, platform profile, and V2 contract.
- Produces sealed health/static/final evidence and a human-readable report attachment.

- [ ] **Step 1: Publish and verify candidate identity**

Push commits, fetch `origin/feat/v2-mission-retirement`, and require exact local/remote SHA equality. Preserve existing named untracked review reports. Confirm no task-owned resources are present and final ledger root is absent for the new `(SHA, profile checksum, contract checksum)` tuple.

- [ ] **Step 2: Run exact-head health and verify its sealed evidence**

Run the repository wrapper from repository root with the provisioned profile. Verify fingerprint, candidate manifest/discovery authority, browser identity, native metrics/raster, checksums, and health cleanup.

Expected: health passes before static/build/product work.

- [ ] **Step 3: Run exact-head static and verify its sealed evidence**

Run the declared static lane using the current health fingerprint. Verify every declared command and static checksums.

Expected: static passes before final issuance.

- [ ] **Step 4: Run exactly one final lane as a monitored process**

Launch the runner as a background tracked process with `notify=true`, a 900-second budget, durable stdout/stderr under the final evidence root, and no caller-supplied headless browser/CDP setup. The runner itself must own browser/Xvfb lifecycle. Do not retry the final build.

- [ ] **Step 5: Independently inspect evidence and cleanup**

Verify final manifest outcome, image IDs, control results, browser metrics/raster, journey pre/post artifacts, adapter diagnostics if failed, all checksum envelopes, and absence of task containers/networks/listeners/processes/profile/task root. Retain volumes. Write and attach the human-readable final report.

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 implement each platform and adapter requirement; Task 3 documents the new contract; Task 4 supplies fresh exact-head runtime/browser proof.
- **Shared files/interfaces:** Task 1 introduces the final browser lifecycle consumed by Task 2’s journey launch and Task 4; Task 2 changes only adapter/runner error transport; Task 3 consumes established behavior without changing code interfaces; Task 4 changes no tracked files.
- **Placeholder scan:** no omitted implementation or test steps remain.
- **Review focus coverage:** Task 1 covers caller browser authority and viewport mismatch; Task 2 covers exit-versus-timeout and diagnostic budgets; Task 1/4 cover cleanup; Task 3 documents the monitored recovery rule.
