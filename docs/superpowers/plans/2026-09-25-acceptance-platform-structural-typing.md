# Acceptance Platform Structural Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every candidate-added `type: ignore` directive through structural types while preserving all acceptance-platform behavior and final-evidence guarantees.

**Architecture:** Platform-owned typed failure carriers replace dynamically augmented caught exceptions. Core functions narrow optional resources at the boundary, while tests use typed fixture/adaptor seams rather than invalid construction, method reassignment, or unchecked JSON mutation. A repository policy regression blocks new suppression directives in the candidate delta.

**Tech Stack:** Python 3.13, dataclasses, typing protocols/callables, pytest, Git diff policy check.

**Spec:** `docs/superpowers/specs/2026-09-25-acceptance-platform-structural-typing-design.md`

## Global Constraints

- Remove all 34 `type: ignore` directives added in the `6b96dcc532f4d0728e7cfe41716976e6f795ca1d..HEAD` candidate delta.
- Do not add `type: ignore`, per-file checker exclusions, blanket `Any`, or `cast(Any, ...)` replacements.
- Preserve candidate-SHA binding, content-aware final build policy, browser ownership/flags, 1920×1080 DPR1 WebGL2 acceptance, cleanup semantics, visible route/POI requirements, and explicit degraded-history behavior.
- Preserve bounded artifacts, primary-error causality, and fail-closed cleanup/evidence publication.
- No runtime, Docker, browser, network, or final-lane commands during implementation tasks.
- Documentation impact is limited to this plan/spec; no operator/API/runbook/release-policy changes are needed.

## Review Focus

- A caught ordinary `ValueError` retains `compose.output.log` without changing its causal error classification.
- A supervised build failure retains typed supervision and diagnostics even when ledger metadata is malformed.
- A missing topology override/ledger object fails before dereference and does not reach build/startup.
- Test doubles still provoke each final fail-closed path without mutating immutable production contracts.
- The policy check detects a newly added `type: ignore` in any candidate file, including tests.

---

### Task 1: Typed failure metadata and stream/resource boundaries

**Files:**
- Create: `tools/acceptance/platform/failures.py`
- Modify: `tools/acceptance/platform/health.py:159-245`
- Modify: `tools/acceptance/platform/runner.py:725-780`
- Modify: `tools/acceptance/platform/compose.py:1071-1092`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_acceptance_platform_compose.py`

**Interfaces:**
- Produces `PlatformFailure`: a declared exception carrier with `cause: BaseException`, `platform_artifacts: Mapping[str, bytes]`, optional `platform_cleanup_error: str`, and optional `build_supervision: Mapping[str, object]`.
- Produces `raise_with_platform_metadata(cause, *, artifacts, cleanup_error='', supervision=None) -> NoReturn`, which preserves `cause` through `raise ... from cause`.
- Consumes the existing bounded artifact and supervision projections; does not alter their schemas.

- [ ] **Step 1: Write failing health and runner tests for typed metadata preservation**

Add tests that force health browser-session cleanup failure and final Compose/build failure, then assert the sealing/classification paths receive a `PlatformFailure` with exactly the bounded artifacts and optional metadata.

```python
with pytest.raises(PlatformFailure) as raised:
    raise_with_platform_metadata(ValueError("primary"), artifacts={"compose.output.log": b"x"})
assert isinstance(raised.value.__cause__, ValueError)
assert raised.value.platform_artifacts == {"compose.output.log": b"x"}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py -k 'platform_failure or metadata'`

Expected: FAIL because `PlatformFailure` and the typed failure propagation do not yet exist.

- [ ] **Step 3: Implement the minimal typed carrier and replace dynamic exception attributes**

Create `failures.py`, use it in health and runner exception paths, and replace `error.platform_artifacts = ...` / `error.build_supervision = ...` with a carrier that chains the original exception. Change `_read_compose_stream` to accept `TextIO` (or an equivalent iterable protocol) so its stream iteration is typed without suppression.

```python
@dataclass(frozen=True)
class PlatformFailure(Exception):
    cause: BaseException
    platform_artifacts: Mapping[str, bytes]
    platform_cleanup_error: str = ""
    build_supervision: Mapping[str, object] | None = None
```

- [ ] **Step 4: Run focused suites to verify green behavior**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_compose.py`

Expected: PASS, with all current failure paths retaining diagnostics and no `type: ignore` in the three implementation modules.

- [ ] **Step 5: Commit the typed production-boundary slice**

```bash
git add tools/acceptance/platform/failures.py tools/acceptance/platform/health.py \
  tools/acceptance/platform/runner.py tools/acceptance/platform/compose.py \
  tools/tests/test_acceptance_platform_health.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_acceptance_platform_compose.py
git commit -m "refactor(acceptance): type failure metadata boundaries"
```

### Task 2: Typed test fixtures, optional-resource narrowing, and adversarial adapters

**Files:**
- Modify: `tools/tests/test_acceptance_platform_compose.py:1-720`
- Modify: `tools/tests/test_acceptance_platform_model.py:1-60`
- Modify: `tools/tests/test_acceptance_platform_runner.py:200-1435`
- Modify: `tools/acceptance/platform/runner.py` only if a production signature needs narrowing to expose a typed test seam
- Test: same three test modules

**Interfaces:**
- Consumes `PlatformFailure` from Task 1.
- Produces typed fixture constructors for `BrowserProfile`, `PlatformProfile`, executor callables, rendered topology, build ledger, and JSON payload mutations.
- Produces checked helper functions that return non-optional override paths, ledgers, and nested payload mappings before mutation.

- [ ] **Step 1: Write failing tests that require typed fixtures and guarded optional values**

Add tests that construct an invalid-profile/override/ledger scenario through a typed helper and assert the same fail-closed production result; add a fixture-level assertion that no helper assigns methods after executor construction.

```python
def configured_executor(*, run: ComposeRun) -> SubprocessComposeExecutor:
    return SubprocessComposeExecutor(retain=lambda _: None, run=run)

with pytest.raises(ValueError, match="rendered override"):
    require_override_path(None)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_model.py tools/tests/test_acceptance_platform_runner.py -k 'typed_fixture or require_override_path'`

Expected: FAIL because the typed fixture/narrowing helpers do not yet exist.

- [ ] **Step 3: Replace all invalid construction, reassignment, and unchecked mutation patterns**

Use a real `BrowserProfile` in test profiles. Pass test executor behavior through constructor/dependency seams. Replace immutable-key assignment with a new constructed key. Introduce checked payload-copy helpers and typed ledger/topology adapters. Replace `object()`/untyped lambdas where they feed production signatures with minimal protocol-conforming test doubles.

```python
def require_override_path(topology: RenderedTopology) -> Path:
    if topology.override_path is None:
        raise ValueError("rendered override path is required")
    return topology.override_path
```

- [ ] **Step 4: Run focused suites to verify green behavior**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_compose.py tools/tests/test_acceptance_platform_model.py tools/tests/test_acceptance_platform_runner.py`

Expected: PASS, with all adversarial cases intact and zero `type: ignore` directives in these test modules.

- [ ] **Step 5: Commit the typed test-seam slice**

```bash
git add tools/tests/test_acceptance_platform_compose.py \
  tools/tests/test_acceptance_platform_model.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/acceptance/platform/runner.py
git commit -m "test(acceptance): type adversarial platform fixtures"
```

### Task 3: Candidate suppression policy regression and verification evidence

**Files:**
- Create: `tools/tests/test_acceptance_platform_typing_policy.py`
- Modify: `tools/verify` only if this test requires explicit inclusion in the existing static gate
- Test: `tools/tests/test_acceptance_platform_typing_policy.py`

**Interfaces:**
- Consumes `git diff --unified=0 <base>..HEAD` from a test-controlled base supplied through `ACCEPTANCE_POLICY_BASE_SHA`.
- Produces a test failure containing every file/line that adds `type: ignore`.

- [ ] **Step 1: Write the failing policy regression**

Create a temp Git fixture or injected diff reader containing one added suppression and assert the policy helper returns its file/line; add a candidate-base test that inspects the real working diff when `ACCEPTANCE_POLICY_BASE_SHA` is set.

```python
def test_added_type_ignore_is_rejected() -> None:
    violations = added_type_ignore_lines("+value = 1  # type: ignore[arg-type]\n")
    assert violations == ("value = 1  # type: ignore[arg-type]",)
```

- [ ] **Step 2: Run the policy test to verify it fails**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_typing_policy.py::test_added_type_ignore_is_rejected`

Expected: FAIL before the policy helper/test exists.

- [ ] **Step 3: Implement the bounded diff parser and wire it into static verification**

Parse only unified-diff added lines, exclude file headers, and report every suppression. Do not scan arbitrary history or invoke network commands. Ensure the current candidate base check sees zero violations after Tasks 1–2.

```python
def added_type_ignore_lines(diff: str) -> tuple[str, ...]:
    return tuple(line[1:] for line in diff.splitlines()
                 if line.startswith("+") and not line.startswith("+++")
                 and "type: ignore" in line)
```

- [ ] **Step 4: Run complete acceptance-platform verification**

Run:

```bash
ACCEPTANCE_POLICY_BASE_SHA=6b96dcc532f4d0728e7cfe41716976e6f795ca1d \
python3 -m pytest -q \
  tools/tests/test_acceptance_platform_health.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_acceptance_platform_compose.py \
  tools/tests/test_acceptance_platform_docs.py \
  tools/tests/test_acceptance_platform_dockerfiles.py \
  tools/tests/test_acceptance_platform_typing_policy.py \
  tools/tests/test_v2_acceptance_browser_contract.py

git diff --check 6b96dcc532f4d0728e7cfe41716976e6f795ca1d..HEAD
```

Expected: PASS; policy output identifies zero candidate-added suppressions.

- [ ] **Step 5: Commit the policy gate**

```bash
git add tools/tests/test_acceptance_platform_typing_policy.py tools/verify
git commit -m "test(acceptance): block suppressed typing errors"
```

## Final verification after all tasks

- [ ] Push the reviewed exact head and verify `origin/feat/v2-mission-retirement` equals local `HEAD`.
- [ ] Run fresh health and static acceptance using the platform profile and candidate-qualified evidence root.
- [ ] Run one final lane only after fresh health/static pass; inspect final authority, artifact checksums, and task cleanup.
- [ ] Re-request whole-branch review for `origin/dev...HEAD`; resolve Critical/Important findings before merging PR #183 into `dev`.
- [ ] Verify the merge commit and that `origin/dev` contains the merged head. Do not merge or release to `main`.
