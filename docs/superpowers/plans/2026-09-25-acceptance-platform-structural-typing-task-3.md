# Task 3: Candidate suppression policy and verification evidence

Companion to [2026-09-25-acceptance-platform-structural-typing](2026-09-25-acceptance-platform-structural-typing.md).

## Task 3: Candidate suppression policy regression and verification evidence

**Files:**

- Create: `tools/tests/test_acceptance_platform_typing_policy.py`
- Modify: `tools/verify` only if this test requires explicit inclusion in the
  existing static gate

- Test: `tools/tests/test_acceptance_platform_typing_policy.py`

**Interfaces:**

- Consumes `git diff --unified=0 <base>..HEAD` from a test-controlled base
  supplied through `ACCEPTANCE_POLICY_BASE_SHA`.

- Produces a test failure containing every file/line that adds `type: ignore`.

- [ ] **Step 1: Write the failing policy regression**

Create a temp Git fixture or injected diff reader containing one added
suppression and assert the policy helper returns its file/line; add a
candidate-base test that inspects the real working diff when
`ACCEPTANCE_POLICY_BASE_SHA` is set.

```python
def test_added_type_ignore_is_rejected() -> None:
    violations = added_type_ignore_lines("+value = 1  # type: ignore[arg-type]\n")
    assert violations == ("value = 1  # type: ignore[arg-type]",)
```

- [ ] **Step 2: Run the policy test to verify it fails**

Run: `python3 -m pytest -q
tools/tests/test_acceptance_platform_typing_policy.py::test_added_type_ignore_is_rejected`

Expected: FAIL before the policy helper/test exists.

- [ ] **Step 3: Implement the bounded diff parser and wire it into static
  verification**

Parse only unified-diff added lines, exclude file headers, and report every
suppression. Do not scan arbitrary history or invoke network commands. Ensure
the current candidate base check sees zero violations after Tasks 1–2.

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

- [ ] Push the reviewed exact head and verify
  `origin/feat/v2-mission-retirement` equals local `HEAD`.

- [ ] Run fresh health and static acceptance using the platform profile and
  candidate-qualified evidence root.

- [ ] Run one final lane only after fresh health/static pass; inspect final
  authority, artifact checksums, and task cleanup.

- [ ] Re-request whole-branch review for `origin/dev...HEAD`; resolve
  Critical/Important findings before merging PR #183 into `dev`.

- [ ] Verify the merge commit and that `origin/dev` contains the merged head. Do
  not merge or release to `main`.

[Return to the main plan](2026-09-25-acceptance-platform-structural-typing.md).
