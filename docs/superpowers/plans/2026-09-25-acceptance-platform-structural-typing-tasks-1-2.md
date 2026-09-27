# Tasks 1–2: Typed failure metadata and typed test fixtures

Companion to [2026-09-25-acceptance-platform-structural-typing](2026-09-25-acceptance-platform-structural-typing.md).

## Task 1: Typed failure metadata and stream/resource boundaries

**Files:**

- Create: `tools/acceptance/platform/failures.py`
- Modify: `tools/acceptance/platform/health.py:159-245`
- Modify: `tools/acceptance/platform/runner.py:725-780`
- Modify: `tools/acceptance/platform/compose.py:1071-1092`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_acceptance_platform_compose.py`

**Interfaces:**

- Produces `PlatformFailure`: a declared exception carrier with `cause:
  BaseException`, `platform_artifacts: Mapping[str, bytes]`, optional
  `platform_cleanup_error: str`, and optional `build_supervision: Mapping[str,
  object]`.

- Produces `raise_with_platform_metadata(cause, *, artifacts, cleanup_error='',
  supervision=None) -> NoReturn`, which preserves `cause` through `raise ...
  from cause`.

- Consumes the existing bounded artifact and supervision projections; does not
  alter their schemas.

- [ ] **Step 1: Write failing health and runner tests for typed metadata
  preservation**

Add tests that force health browser-session cleanup failure and final
Compose/build failure, then assert the sealing/classification paths receive a
`PlatformFailure` with exactly the bounded artifacts and optional metadata.

```python
with pytest.raises(PlatformFailure) as raised:
    raise_with_platform_metadata(ValueError("primary"), artifacts={"compose.output.log": b"x"})
assert isinstance(raised.value.__cause__, ValueError)
assert raised.value.platform_artifacts == {"compose.output.log": b"x"}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_health.py
tools/tests/test_acceptance_platform_runner.py -k 'platform_failure or
metadata'`

Expected: FAIL because `PlatformFailure` and the typed failure propagation do
not yet exist.

- [ ] **Step 3: Implement the minimal typed carrier and replace dynamic
  exception attributes**

Create `failures.py`, use it in health and runner exception paths, and replace
`error.platform_artifacts = ...` / `error.build_supervision = ...` with a
carrier that chains the original exception. Change `_read_compose_stream` to
accept `TextIO` (or an equivalent iterable protocol) so its stream iteration is
typed without suppression.

```python
@dataclass(frozen=True)
class PlatformFailure(Exception):
    cause: BaseException
    platform_artifacts: Mapping[str, bytes]
    platform_cleanup_error: str = ""
    build_supervision: Mapping[str, object] | None = None
```

- [ ] **Step 4: Run focused suites to verify green behavior**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_health.py
tools/tests/test_acceptance_platform_runner.py
tools/tests/test_acceptance_platform_compose.py`

Expected: PASS, with all current failure paths retaining diagnostics and no
`type: ignore` in the three implementation modules.

- [ ] **Step 5: Commit the typed production-boundary slice**

```bash
git add tools/acceptance/platform/failures.py tools/acceptance/platform/health.py \
  tools/acceptance/platform/runner.py tools/acceptance/platform/compose.py \
  tools/tests/test_acceptance_platform_health.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/tests/test_acceptance_platform_compose.py
git commit -m "refactor(acceptance): type failure metadata boundaries"
```

## Task 2: Typed test fixtures, optional-resource narrowing, and adversarial adapters

**Files:**

- Modify: `tools/tests/test_acceptance_platform_compose.py:1-720`
- Modify: `tools/tests/test_acceptance_platform_model.py:1-60`
- Modify: `tools/tests/test_acceptance_platform_runner.py:200-1435`
- Modify: `tools/acceptance/platform/runner.py` only if a production signature
  needs narrowing to expose a typed test seam

- Test: same three test modules

**Interfaces:**

- Consumes `PlatformFailure` from Task 1.
- Produces typed fixture constructors for `BrowserProfile`, `PlatformProfile`,
  executor callables, rendered topology, build ledger, and JSON payload
  mutations.

- Produces checked helper functions that return non-optional override paths,
  ledgers, and nested payload mappings before mutation.

- [ ] **Step 1: Write failing tests that require typed fixtures and guarded
  optional values**

Add tests that construct an invalid-profile/override/ledger scenario through a
typed helper and assert the same fail-closed production result; add a
fixture-level assertion that no helper assigns methods after executor
construction.

```python
def configured_executor(*, run: ComposeRun) -> SubprocessComposeExecutor:
    return SubprocessComposeExecutor(retain=lambda _: None, run=run)

with pytest.raises(ValueError, match="rendered override"):
    require_override_path(None)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_compose.py
tools/tests/test_acceptance_platform_model.py
tools/tests/test_acceptance_platform_runner.py -k 'typed_fixture or
require_override_path'`

Expected: FAIL because the typed fixture/narrowing helpers do not yet exist.

- [ ] **Step 3: Replace all invalid construction, reassignment, and unchecked
  mutation patterns**

Use a real `BrowserProfile` in test profiles. Pass test executor behavior
through constructor/dependency seams. Replace immutable-key assignment with a
new constructed key. Introduce checked payload-copy helpers and typed
ledger/topology adapters. Replace `object()`/untyped lambdas where they feed
production signatures with minimal protocol-conforming test doubles.

```python
def require_override_path(topology: RenderedTopology) -> Path:
    if topology.override_path is None:
        raise ValueError("rendered override path is required")
    return topology.override_path
```

- [ ] **Step 4: Run focused suites to verify green behavior**

Run: `python3 -m pytest -q tools/tests/test_acceptance_platform_compose.py
tools/tests/test_acceptance_platform_model.py
tools/tests/test_acceptance_platform_runner.py`

Expected: PASS, with all adversarial cases intact and zero `type: ignore`
directives in these test modules.

- [ ] **Step 5: Commit the typed test-seam slice**

```bash
git add tools/tests/test_acceptance_platform_compose.py \
  tools/tests/test_acceptance_platform_model.py \
  tools/tests/test_acceptance_platform_runner.py \
  tools/acceptance/platform/runner.py
git commit -m "test(acceptance): type adversarial platform fixtures"
```

[Return to the main plan](2026-09-25-acceptance-platform-structural-typing.md).
