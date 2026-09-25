# Content-Aware Final Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce exact-candidate final images without reinstalling unchanged dependencies, while failing builds on meaningful-progress stalls rather than a blind fixed build timeout.

**Architecture:** The task-private Compose topology injects a platform-owned candidate SHA build argument into each contract service. Dockerfiles consume it only after lockfile-keyed dependency installation so every candidate recompiles/repackages application output while unchanged dependency layers remain reusable. A streaming Compose executor classifies meaningful BuildKit progress and enforces both a 600-second inactivity window and an 1800-second total build deadline; the ledger and sealed evidence distinguish stall from hard-deadline failure.

**Tech Stack:** Python 3.11, pytest, Docker Compose/BuildKit, Dockerfiles, JSON topology rendering, SHA-256 evidence manifests.

**Spec:** `docs/superpowers/specs/2026-09-25-v2-content-aware-final-build-design.md`

## Global Constraints

- Final builds must use Docker cache only through content-addressed Docker layers keyed by unchanged dependency manifests; no persistent remote cache service is introduced.
- Every final candidate must rebuild application source, compilation, packaging, and final output image using the platform-owned exact candidate SHA.
- Final Compose build uses `--pull` and must not use blanket `--no-cache`.
- Caller, contract, adapter, and browser inputs must not supply build arguments, cache controls, or Compose flags.
- The final build stall window is exactly 600 seconds without qualifying BuildKit progress; the hard outer build deadline is exactly 1800 seconds.
- Qualifying progress is a new BuildKit stage/`DONE`, monotonic byte advance, or a new command-output line in an active `RUN` stage. Repeated/no-op frames and warnings do not reset the stall timer.
- Stall and hard-deadline failures close the build ledger as unusable and block startup, controls, and journey execution.
- Evidence remains bounded, redacted, allowlisted, checksum-covered, and records supervision details plus last qualifying event.
- Existing platform-owned headed/Xvfb browser, 1920×1080 DPR1/WebGL2 preflight, 120-second no-build startup cap, cleanup behavior, and no-final-authority-on-failure rules remain unchanged.
- Documentation impact is in scope in `docs/operations/acceptance-platform.md`.

## Review Focus

- An unchanged `package-lock.json` or `requirements.txt` must permit dependency-layer reuse, but changing either must invalidate its dependency layer through normal Docker content hashing.
- An otherwise identical source tree on a new candidate SHA must still rebuild source/build/output layers because the private candidate build argument changes after dependency installation.
- Repeated BuildKit spinner lines or unchanged byte counts must not keep a stuck build alive.
- A new stage, `DONE`, byte advance, or active `RUN` output must reset the 600-second stall deadline without exceeding the 1800-second total deadline.
- A stream timeout must close the ledger, persist bounded redacted diagnostics plus last-progress metadata, and prevent `start_no_build` from running.

---

### Task 1: Bind the exact candidate to reusable dependency-layer builds

**Files:**
- Modify: `backend/starlink-location/Dockerfile:6-31`
- Modify: `frontend/mission-planner/Dockerfile:6-16`
- Modify: `tools/acceptance/platform/compose.py:240-320`
- Modify: `tools/tests/test_acceptance_platform_compose.py`
- Create: `tools/tests/test_acceptance_platform_dockerfiles.py`

**Interfaces:**
- Consumes: `BuildLedgerKey.candidate_sha`, `TaskTopology.services`, task-private resolved Compose JSON.
- Produces: `render_task_override(..., candidate_sha: str) -> TaskTopology`, where `TaskTopology.candidate_sha: str` is immutable and its rendered service build mapping contains only `args: {"ACCEPTANCE_CANDIDATE_SHA": candidate_sha}` in addition to resolved trusted build fields.
- Produces: Dockerfile declaration `ARG ACCEPTANCE_CANDIDATE_SHA` after dependency installation and deterministic candidate-consumption layer before source copy/build.

- [ ] **Step 1: Write failing private-build-argument and Dockerfile ordering tests**

```python
def test_final_topology_binds_every_contract_service_to_the_exact_candidate_sha(tmp_path):
    topology = render_task_override(
        REPOSITORY, CONTRACT, tmp_path, "accept-sha", PORTS,
        candidate_sha="a" * 40,
    )
    resolve_topology(topology, CONTRACT, FakeExecutor())
    rendered = json.loads(topology.override_path.read_text())
    assert {
        name: rendered["services"][name]["build"]["args"]
        for name in CONTRACT.services
    } == {name: {"ACCEPTANCE_CANDIDATE_SHA": "a" * 40} for name in CONTRACT.services}


def test_frontend_dockerfile_consumes_candidate_only_after_npm_ci():
    source = FRONTEND_DOCKERFILE.read_text()
    assert source.index("RUN npm ci") < source.index("ARG ACCEPTANCE_CANDIDATE_SHA")
    assert source.index("ARG ACCEPTANCE_CANDIDATE_SHA") < source.index("COPY . .")
```

Add the matching backend assertion that `pip install --user --no-cache-dir -r requirements.txt` precedes the argument and the app copy follows it. Add an invalid candidate-SHA test that confirms `render_task_override` rejects a non-40-hex value.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
```

Expected: FAIL because `render_task_override` has no candidate SHA parameter or rendered build args, and Dockerfiles do not declare the candidate argument.

- [ ] **Step 3: Add the minimal private candidate-binding implementation**

Update `TaskTopology` and `render_task_override` so the platform passes `inputs.sha` at topology creation and stores it as an immutable, validated `candidate_sha`. In `resolve_topology`, mutate only each selected service’s resolved `build` mapping:

```python
build = service.get("build")
if not isinstance(build, dict):
    raise ValueError("contract service has no resolved build mapping")
args = build.get("args")
if args not in (None, {}):
    raise ValueError("resolved service build arguments are not permitted")
build["args"] = {"ACCEPTANCE_CANDIDATE_SHA": topology.candidate_sha}
```

In `build_final`, reject the build before ledger claim unless `topology.candidate_sha == key.candidate_sha`; this prevents source/output cache invalidation from being bound to a different candidate. Preserve task-private ownership and reject any pre-existing resolved build args.

Insert this exact Dockerfile pattern in both Dockerfiles after dependency installation and before source copy:

```dockerfile
ARG ACCEPTANCE_CANDIDATE_SHA
RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"
```

Do not persist the value with `ENV`, labels, application config, or runtime environment.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
```

Expected: PASS, including candidate exactness, invalid SHA rejection, no caller build args, and both Dockerfile ordering checks.

- [ ] **Step 5: Commit**

```bash
git add backend/starlink-location/Dockerfile frontend/mission-planner/Dockerfile tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
git commit -m "fix(acceptance): bind final builds to candidate SHA"
```

### Task 2: Stream and classify BuildKit progress under bounded supervision

**Files:**
- Modify: `tools/acceptance/platform/compose.py:21-117, 350-397`
- Modify: `tools/tests/test_acceptance_platform_compose.py`

**Interfaces:**
- Consumes: combined plain BuildKit output bytes from `SubprocessComposeExecutor.run`.
- Produces: `BuildProgressEvent(kind: Literal["stage", "done", "bytes", "run_output"], elapsed_seconds: float, detail: str)` and `BuildSupervisionFailure(kind: Literal["build_stalled", "build_deadline_exceeded"], last_event: BuildProgressEvent | None, output: str)`.
- Produces: `BuildReconciliation(..., reason: str, supervision: Mapping[str, object])`, with closed ledger records carrying a bounded supervision summary.

- [ ] **Step 1: Write failing progress-classification and bounded-supervision tests**

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

Add tests for a new stage, `DONE`, monotonically increased transfer bytes, and distinct active `RUN` output resetting the stall clock. Add a continuously progressing sequence that reaches exactly the 1800-second outer limit and raises `build_deadline_exceeded` rather than `build_stalled`.

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py -k 'progress or stall or deadline'
```

Expected: FAIL because the current executor buffers output until process completion and uses only the fixed 1200-second timeout.

- [ ] **Step 3: Implement streaming monitoring without weakening retained diagnostics**

Replace `process.communicate(timeout=...)` for final-build execution with a line-streaming loop using the already imported subprocess process group semantics. Retain every line through `BoundedComposeDiagnostics.retain` while passing it to `BuildProgressMonitor.observe`.

Use exact constants:

```python
_FINAL_BUILD_STALL_SECONDS = 600.0
_FINAL_BUILD_HARD_DEADLINE_SECONDS = 1800.0
```

Terminate the process on the first exceeded bound, wait five seconds, then kill if necessary. Raise `BuildSupervisionFailure` containing only the failure kind, bounded last event, and collected output. In `build_final`, close the claim with an unusable `BuildReconciliation` and a reason beginning exactly `build_stalled:` or `build_deadline_exceeded:`.

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

Expected: PASS, including original build reconciliation, timeout/ledger, startup, redaction, and new progress/deadline behavior.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py
git commit -m "fix(acceptance): supervise final build progress"
```

### Task 3: Seal supervision metadata and document the operator contract

**Files:**
- Modify: `tools/acceptance/platform/runner.py:688-715, 922-958`
- Modify: `tools/tests/test_acceptance_platform_runner.py`
- Modify: `tools/tests/test_acceptance_platform_docs.py`
- Modify: `docs/operations/acceptance-platform.md:70-105`

**Interfaces:**
- Consumes: a `BuildSupervisionFailure` and the `BuildReconciliation.supervision` mapping from Task 2.
- Produces: final runner manifest `build_supervision` object with exactly `policy_version`, `stall_window_seconds`, `hard_deadline_seconds`, `elapsed_seconds`, `last_progress_kind`, and `last_progress_elapsed_seconds` keys; all string values remain bounded to 128 UTF-8 bytes.

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

Add a byte-limit test using a 129-byte event detail and assert the manifest retains no unbounded detail. Add docs-source contracts requiring `--pull`, lockfile-keyed dependency reuse, `600`-second stall, `1800`-second hard deadline, `build_stalled`, and `build_deadline_exceeded`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py
```

Expected: FAIL because final manifests have no `build_supervision` object and operations documentation still describes a fixed 1200-second no-cache build.

- [ ] **Step 3: Add bounded manifest projection and operator documentation**

Have `_final_steps` attach a strictly typed, allowlisted `build_supervision` mapping to the raised build failure. Extend `_manifest` to serialize it only after validating exact keys, numeric bounds, allowed progress kinds, and maximum string size. A failure to validate supervision metadata must fail final evidence publication rather than serialize arbitrary values.

Replace the fixed no-cache build documentation with this operational sequence:

```markdown
Final builds reuse content-addressed dependency layers only when their lockfile inputs are unchanged. The runner injects the exact candidate SHA after dependency installation so application/output layers rebuild for every candidate. Build supervision stops after 600 seconds without meaningful BuildKit progress or at the 1800-second total deadline, recording `build_stalled` or `build_deadline_exceeded` in sealed evidence.
```

State explicitly that neither outcome authorizes automatic retry and that a later final requires fresh health/static and operator approval.

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

### Task 4: Verify end-to-end non-final build classification

**Files:**
- Modify: `tools/tests/test_acceptance_platform_compose.py`
- Modify: `tools/tests/test_acceptance_platform_runner.py`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**
- Consumes: the Task 1 private candidate binding, Task 2 streaming supervisor, Task 3 manifest projection.
- Produces: an executable test contract proving final build argv, topology build args, ledger closure, startup blocking, manifest sealing, and documentation agree.

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

Include assertions that the exact candidate SHA appears in the private rendered override, `--pull` is present, `--no-cache` is absent, and the candidate build ledger is closed.

- [ ] **Step 2: Run the cross-boundary test to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_runner.py -k 'stalled_candidate_build'
```

Expected: FAIL until all Task 1–3 interfaces are wired consistently.

- [ ] **Step 3: Implement only the wiring needed for the cross-boundary contract**

Pass the candidate SHA and validated `BuildSupervisionFailure` metadata through the existing `render_task_override` → `build_final` → `_final_steps` → `_manifest` path. Do not add a second cache policy, alternate launch path, caller input, or a non-final build retry.

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
