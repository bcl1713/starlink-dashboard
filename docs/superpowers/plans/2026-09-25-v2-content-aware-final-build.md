# Content-Aware Final Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce exact-candidate final images without reinstalling unchanged
dependencies, while failing builds on meaningful-progress stalls rather than a
blind fixed build timeout.

**Architecture:** The task-private Compose topology injects a platform-owned
candidate SHA build argument into each contract service. Dockerfiles consume it
only after lockfile-keyed dependency installation so every candidate
recompiles/repackages application output while unchanged dependency layers
remain reusable. A streaming Compose executor classifies meaningful BuildKit
progress and enforces both a 600-second inactivity window and an 1800-second
total build deadline; the ledger and sealed evidence distinguish stall from
hard-deadline failure.

**Tech Stack:** Python 3.11, pytest, Docker Compose/BuildKit, Dockerfiles, JSON
topology rendering, SHA-256 evidence manifests.

**Spec:**
`docs/superpowers/specs/2026-09-25-v2-content-aware-final-build-design.md`

## Global Constraints

- Final builds must use Docker cache only through content-addressed Docker
  layers keyed by unchanged dependency manifests; no persistent remote cache
  service is introduced.

- Every final candidate must rebuild application source, compilation, packaging,
  and final output image using the platform-owned exact candidate SHA.

- Final Compose build uses `--pull` and must not use blanket `--no-cache`.
- Caller, contract, adapter, and browser inputs must not supply build arguments,
  cache controls, or Compose flags.

- The final build stall window is exactly 600 seconds without qualifying
  BuildKit progress; the hard outer build deadline is exactly 1800 seconds.

- Qualifying progress is a new BuildKit stage/`DONE`, monotonic byte advance, or
  a new command-output line in an active `RUN` stage. Repeated/no-op frames and
  warnings do not reset the stall timer.

- Stall and hard-deadline failures close the build ledger as unusable and block
  startup, controls, and journey execution.

- Evidence remains bounded, redacted, allowlisted, checksum-covered, and records
  supervision details plus last qualifying event.

- Existing platform-owned headed/Xvfb browser, 1920×1080 DPR1/WebGL2 preflight,
  120-second no-build startup cap, cleanup behavior, and
  no-final-authority-on-failure rules remain unchanged.

- Documentation impact is in scope in `docs/operations/acceptance-platform.md`.

## Review Focus

- An unchanged `package-lock.json` or `requirements.txt` must permit
  dependency-layer reuse, but changing either must invalidate its dependency
  layer through normal Docker content hashing.

- An otherwise identical source tree on a new candidate SHA must still rebuild
  source/build/output layers because the private candidate build argument
  changes after dependency installation.

- Repeated BuildKit spinner lines or unchanged byte counts must not keep a stuck
  build alive.

- A new stage, `DONE`, byte advance, or active `RUN` output must reset the
  600-second stall deadline without exceeding the 1800-second total deadline.

- A stream timeout must close the ledger, persist bounded redacted diagnostics
  plus last-progress metadata, and prevent `start_no_build` from running.

---

## Companion documents

- [Tasks 2–4: Build supervision, evidence, and cross-boundary
  verification](2026-09-25-v2-content-aware-final-build-task-2-4.md)

### Task 1: Bind the exact candidate to reusable dependency-layer builds

**Files:**

- Modify: `backend/starlink-location/Dockerfile:6-31`
- Modify: `frontend/mission-planner/Dockerfile:6-16`
- Modify: `tools/acceptance/platform/compose.py:240-320`
- Modify: `tools/tests/test_acceptance_platform_compose.py`
- Create: `tools/tests/test_acceptance_platform_dockerfiles.py`

**Interfaces:**

- Consumes: `BuildLedgerKey.candidate_sha`, `TaskTopology.services`,
  task-private resolved Compose JSON.

- Produces: `render_task_override(..., candidate_sha: str) -> TaskTopology`,
  where `TaskTopology.candidate_sha: str` is immutable and its rendered service
  build mapping contains only `args: {"ACCEPTANCE_CANDIDATE_SHA":
  candidate_sha}` in addition to resolved trusted build fields.

- Produces: Dockerfile declaration `ARG ACCEPTANCE_CANDIDATE_SHA` after
  dependency installation and deterministic candidate-consumption layer before
  source copy/build.

- [ ] **Step 1: Write failing private-build-argument and Dockerfile ordering
  tests**

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

Add the matching backend assertion that `pip install --user --no-cache-dir -r
requirements.txt` precedes the argument and the app copy follows it. Add an
invalid candidate-SHA test that confirms `render_task_override` rejects a
non-40-hex value.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
```

Expected: FAIL because `render_task_override` has no candidate SHA parameter or
rendered build args, and Dockerfiles do not declare the candidate argument.

- [ ] **Step 3: Add the minimal private candidate-binding implementation**

Update `TaskTopology` and `render_task_override` so the platform passes
`inputs.sha` at topology creation and stores it as an immutable, validated
`candidate_sha`. In `resolve_topology`, mutate only each selected service’s
resolved `build` mapping:

```python
build = service.get("build")
if not isinstance(build, dict):
    raise ValueError("contract service has no resolved build mapping")
args = build.get("args")
if args not in (None, {}):
    raise ValueError("resolved service build arguments are not permitted")
build["args"] = {"ACCEPTANCE_CANDIDATE_SHA": topology.candidate_sha}
```

In `build_final`, reject the build before ledger claim unless
`topology.candidate_sha == key.candidate_sha`; this prevents source/output cache
invalidation from being bound to a different candidate. Preserve task-private
ownership and reject any pre-existing resolved build args.

Insert this exact Dockerfile pattern in both Dockerfiles after dependency
installation and before source copy:

```dockerfile
ARG ACCEPTANCE_CANDIDATE_SHA
RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"
```

Do not persist the value with `ENV`, labels, application config, or runtime
environment.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```bash
python -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
```

Expected: PASS, including candidate exactness, invalid SHA rejection, no caller
build args, and both Dockerfile ordering checks.

- [ ] **Step 5: Commit**

```bash
git add backend/starlink-location/Dockerfile frontend/mission-planner/Dockerfile tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_dockerfiles.py
git commit -m "fix(acceptance): bind final builds to candidate SHA"
```
