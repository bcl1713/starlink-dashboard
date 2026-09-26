# Tasks 2–4: Build supervision, evidence, and cross-boundary verification

Companion to
[2026-09-25-v2-content-aware-final-build](2026-09-25-v2-content-aware-final-build.md).

## Task 2: Stream and classify BuildKit progress under bounded supervision

**Files:**

- Modify: `tools/acceptance/platform/compose.py:21-117, 350-397`
- Modify: `tools/tests/test_acceptance_platform_compose.py`

**Interfaces:**

- Consumes: combined plain BuildKit output bytes from
  `SubprocessComposeExecutor.run`.

- Produces: `BuildProgressEvent(kind: Literal["stage", "done", "bytes",
  "run_output"], elapsed_seconds: float, detail: str)` and
  `BuildSupervisionFailure(kind: Literal["build_stalled",
  "build_deadline_exceeded"], last_event: BuildProgressEvent | None, output:
  str)`.

- Produces: `BuildReconciliation(..., reason: str, supervision: Mapping[str,
  object])`, with closed ledger records carrying a bounded supervision summary.

- [ ] **Step 1: Write failing progress-classification and bounded-supervision
  tests**

```python
def test_progress_parser_ignores_repeated_spinner_and_unchanged_byte_frames():
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)
    assert monitor.observe("#31 [builder] RUN npm run build\n") is not None
    clock.advance(599)
    assert monitor.observe("#31 [builder] RUN npm run build\n") is None
    assert monitor.observe("#24 transferring context: 53.65MB 25.2s\n") is not None
    clock.advance(1)
    assert monitor.observe("#24 transferring context: 53.65MB 25.2s\n") is None


def test_build_stall_closes_ledger_and_blocks_startup(tmp_path):
    executor = StreamingFakeExecutor(lines=["#31 [builder] RUN npm run build\n"], clock=FakeClock())
    with pytest.raises(BuildSupervisionFailure, match="build_stalled"):
        build_final(TOPOLOGY, PROFILE, CONTRACT, KEY, BuildLedger(tmp_path), executor)
    assert BuildLedger(tmp_path).read(KEY)["state"] == "closed"
```

Add tests for a new stage, `DONE`, monotonically increased transfer bytes, and
distinct active `RUN` output resetting the stall clock. Add a continuously
progressing sequence that reaches exactly the 1800-second outer limit and raises
`build_deadline_exceeded` rather than `build_stalled`.

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py -k 'progress or stall or deadline'
```

Expected: FAIL because the current executor buffers output until process
completion and uses only the fixed 1200-second timeout.

- [ ] **Step 3: Implement streaming monitoring without weakening retained
  diagnostics**

Replace `process.communicate(timeout=...)` for final-build execution with a
line-streaming loop using the already imported subprocess process group
semantics. Retain every line through `BoundedComposeDiagnostics.retain` while
passing it to `BuildProgressMonitor.observe`.

Use exact constants:

```python
_FINAL_BUILD_STALL_SECONDS = 600.0
_FINAL_BUILD_HARD_DEADLINE_SECONDS = 1800.0
```

Terminate the process on the first exceeded bound, wait five seconds, then kill
if necessary. Raise `BuildSupervisionFailure` containing only the failure kind,
bounded last event, and collected output. In `build_final`, close the claim with
an unusable `BuildReconciliation` and a reason beginning exactly
`build_stalled:` or `build_deadline_exceeded:`.

Build argv must be:

```python
(*topology.argv, "build", "--pull", "--progress=plain", *contract.services)
```

It must not contain `--no-cache`.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py
```

Expected: PASS, including original build reconciliation, timeout/ledger,
startup, redaction, and new progress/deadline behavior.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py
git commit -m "fix(acceptance): supervise final build progress"
```

## Task 3: Seal supervision metadata and document the operator contract

**Files:**

- Modify: `tools/acceptance/platform/runner.py:688-715, 922-958`
- Modify: `tools/tests/test_acceptance_platform_runner.py`
- Modify: `tools/tests/test_acceptance_platform_docs.py`
- Modify: `docs/operations/acceptance-platform.md:70-105`

**Interfaces:**

- Consumes: a `BuildSupervisionFailure` and the
  `BuildReconciliation.supervision` mapping from Task 2.

- Produces: final runner manifest `build_supervision` object with exactly
  `policy_version`, `stall_window_seconds`, `hard_deadline_seconds`,
  `elapsed_seconds`, `last_progress_kind`, and `last_progress_elapsed_seconds`
  keys; all string values remain bounded to 128 UTF-8 bytes.

- [ ] **Step 1: Write failing manifest and documentation contract tests**

```python
def test_final_manifest_seals_stall_supervision_without_final_authority(tmp_path):
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            final_steps=lambda *_: (_ for _ in ()).throw(
                BuildSupervisionFailure("build_stalled", elapsed_seconds=601.0,
                    last_event=BuildProgressEvent("run_output", 1.0, "npm run build"), output="")
            )
        ),
    )
    manifest = result.manifest
    assert manifest["outcome"] == "failed"
    assert manifest["final_acceptance"] is False
    assert manifest["build_supervision"]["stall_window_seconds"] == 600
    assert manifest["build_supervision"]["last_progress_kind"] == "run_output"
```

Add a byte-limit test using a 129-byte event detail and assert the manifest
retains no unbounded detail. Add docs-source contracts requiring `--pull`,
lockfile-keyed dependency reuse, `600`-second stall, `1800`-second hard
deadline, `build_stalled`, and `build_deadline_exceeded`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py
```

Expected: FAIL because final manifests have no `build_supervision` object and
operations documentation still describes a fixed 1200-second no-cache build.

- [ ] **Step 3: Add bounded manifest projection and operator documentation**

Have `_final_steps` attach a strictly typed, allowlisted `build_supervision`
mapping to the raised build failure. Extend `_manifest` to serialize it only
after validating exact keys, numeric bounds, allowed progress kinds, and maximum
string size. A failure to validate supervision metadata must fail final evidence
publication rather than serialize arbitrary values.

Replace the fixed no-cache build documentation with this operational sequence:

```markdown
Final builds reuse content-addressed dependency layers only when their lockfile inputs are unchanged. The runner injects the exact candidate SHA after dependency installation so application/output layers rebuild for every candidate. Build supervision stops after 600 seconds without meaningful BuildKit progress or at the 1800-second total deadline, recording `build_stalled` or `build_deadline_exceeded` in sealed evidence.
```

State explicitly that neither outcome authorizes automatic retry and that a
later final requires fresh health/static and operator approval.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py
python -m compileall -q tools/acceptance/platform
```

Expected: PASS and no compile errors.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/runner.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py docs/operations/acceptance-platform.md
git commit -m "docs(acceptance): record final build supervision"
```

## Task 4: Verify end-to-end non-final build classification

**Files:**

- Modify: `tools/tests/test_acceptance_platform_compose.py`
- Modify: `tools/tests/test_acceptance_platform_runner.py`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**

- Consumes: the Task 1 private candidate binding, Task 2 streaming supervisor,
  Task 3 manifest projection.

- Produces: an executable test contract proving final build argv, topology build
  args, ledger closure, startup blocking, manifest sealing, and documentation
  agree.

- [ ] **Step 1: Write a failing cross-boundary regression test**

```python
def test_stalled_candidate_build_never_reaches_startup_or_final_authority(tmp_path, monkeypatch):
    started = False
    def forbidden_start(*_):
        nonlocal started
        started = True
    monkeypatch.setattr(compose, "start_no_build", forbidden_start)
    result = run_stalled_candidate_final(tmp_path, candidate_sha="b" * 40)
    assert result.manifest["primary"]["detail"].startswith("build_stalled:")
    assert result.manifest["final_acceptance"] is False
    assert started is False
```

Include assertions that the exact candidate SHA appears in the private rendered
override, `--pull` is present, `--no-cache` is absent, and the candidate build
ledger is closed.

- [ ] **Step 2: Run the cross-boundary test to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py -k 'stalled_candidate_build'
```

Expected: FAIL until all Task 1–3 interfaces are wired consistently.

- [ ] **Step 3: Implement only the wiring needed for the cross-boundary
  contract**

Pass the candidate SHA and validated `BuildSupervisionFailure` metadata through
the existing `render_task_override` → `build_final` → `_final_steps` →
`_manifest` path. Do not add a second cache policy, alternate launch path,
caller input, or a non-final build retry.

- [ ] **Step 4: Run final focused verification**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py tools/tests/test_v2_acceptance_browser_contract.py
python -m compileall -q tools/acceptance/platform
node --check tools/acceptance/journeys/v2-mission-retirement.mjs
git diff --check
```

Expected: PASS with no whitespace errors or Python/Node syntax errors.

- [ ] **Step 5: Commit**

```bash
git add tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py docs/operations/acceptance-platform.md
git commit -m "test(acceptance): seal stalled build boundaries"
```

[Return to the main plan](2026-09-25-v2-content-aware-final-build.md).
