<!-- markdownlint-disable MD001 MD013 MD032 MD036 -->

# Forge Frontend Dependency Lifecycle Implementation Plan

> **For Hermes:** Execute this plan inline in the isolated worktree. Brian explicitly prohibited subagent dispatch for this delivery; preserve separate review/verification evidence without delegation.

**Goal:** Make clean Forge acceptance candidates deterministically prepare frontend dependencies before health and final browser/static work, without changing product contracts or duplicating the static-lane installation.

**Architecture:** The external-host runbook prepares the branch checkout once before health. The Python runner performs a final-only preparation step after health validation and before declared static checks; its existing final evidence/cleanup path classifies preparation failure. The shell wrapper's exact cleanup check permits only that task worktree's generated frontend `node_modules` directory.

**Tech Stack:** Bash wrapper, Python 3.11 acceptance platform, pytest, npm/Node 22.12, Forge exact-SHA health/static/final lanes.

**Documentation impact:** Update the external-host operator runbook. Do not change product API, user documentation, Dockerfiles, contracts, CI workflows, or release notes.

---

### Task 1: Make frontend preparation final-only in the Python runner

**Objective:** Preserve the existing install regression seam, but run the safe frontend bootstrap only for a production final invocation after health validation and before static/browser work.

**Files:**
- Modify: `tools/acceptance/platform/runner.py:359-377,470-480,1525-1603`
- Modify: `tools/tests/test_acceptance_platform_runner.py:2247-2267` and the existing final/static ordering tests near `700-800`

**Step 1: Write failing tests**

Replace the current unconditional-static expectation with two focused behaviors:

```python
def test_static_does_not_install_frontend_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    def fake_run(
        words: list[str], **_: object
    ) -> subprocess.CompletedProcess[object]:
        calls.append(words)
        return subprocess.CompletedProcess(words, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._run_static(load_product_contract(CONTRACT))

    assert ["npm", "ci", "--ignore-scripts"] not in calls
    assert calls[-2:] == [["npm", "run", "lint"], ["npm", "run", "test:unit"]]
```

Add a final-order test using `RunnerDependencies` seams. Its preparation seam
appends `"prepare"`; its static seam appends `"static"`; the existing fake
browser/final/cleanup seams append `"browser"`, `"final"`, and `"cleanup"`.
The assertion must be exactly:

```python
assert calls == ["prepare", "static", "browser", "final", "cleanup"]
```

Add a focused test for the concrete preparation helper that asserts one frontend invocation receives the inherited environment plus `CI="1"` and argv:

```python
["npm", "ci", "--ignore-scripts"]
```

**Step 2: Verify RED**

Run:

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_runner.py \
  -k 'static_does_not_install or final_prepares_frontend_dependencies' -q
```

Expected: FAIL because the current static executor invokes `npm ci` unconditionally and no final-only preparation seam exists.

**Step 3: Implement the minimal behavior**

- Add a narrow helper that selects each static group containing a named frontend script (`lint` or `test:*`) and runs `npm ci --ignore-scripts` once in that group’s declared working directory with `CI=1` in a copied environment.
- Keep `_run_static()` limited to the contract-declared commands and its existing named-script-to-`npm run` mapping.
- Add a `RunnerDependencies` preparation seam for test isolation.
- In `run()`, after successful health-fingerprint validation and only for `Lane.FINAL`, invoke the preparation seam before static checks. The default is the new helper; injected static seams must remain usable without touching real npm.
- Preserve fail-closed exception handling so a nonzero preparation subprocess becomes sealed non-final final evidence and no browser/final steps run.

**Step 4: Verify GREEN**

Run the focused tests from Step 2.

Expected: PASS. Confirm the static-lane test does not include `npm ci`; final ordering includes preparation before static/browser work.

**Step 5: Run relevant regression tests**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_contracts.py \
  tools/tests/test_acceptance_platform_runner.py -q
```

If the known adapter-fixture `node_modules` baseline failure recurs, record its exact output and use the focused tests as the local product signal; do not modify the unrelated adapter test.

**Step 6: Commit**

```bash
git add tools/acceptance/platform/runner.py tools/tests/test_acceptance_platform_runner.py
git commit -m "fix(acceptance): prepare final frontend dependencies"
```

---

### Task 2: Permit only final-generated frontend dependencies during wrapper cleanup

**Objective:** Allow the final task worktree to be removed after the runner creates its known frontend `node_modules`, while retaining fail-closed behavior for every other untracked path.

**Files:**
- Modify: `tools/run-acceptance-platform.sh:103-126`
- Modify: `tools/tests/test_acceptance_platform_runner.py:1160-1279` and adjacent final-wrapper cleanup tests

**Step 1: Write failing tests**

Use the existing executable-recording harness to create a final worktree with the owner marker and the generated path. Add one test that asserts cleanup reaches `git worktree remove --force` when the only untracked content is:

```text
frontend/mission-planner/node_modules/
```

Add a companion test that places a distinct untracked file (for example
`unexpected.txt`) and asserts cleanup retains the worktree instead of removing
it.

**Step 2: Verify RED**

Run:

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_runner.py \
  -k 'final_wrapper and node_modules' -q
```

Expected: the generated-node-modules cleanup test fails because the current
`git status --untracked-files=all` check treats it as arbitrary dirty content.

**Step 3: Implement the minimal cleanup exception**

In the wrapper's `git status --porcelain=v1` check, retain the existing marker
exclusion and add exactly one pathspec exclusion for
`frontend/mission-planner/node_modules`. Do not add `git clean`, `rm -rf`, a
wildcard exclusion, a cache cleanup, or an exclusion outside the task worktree.

**Step 4: Verify GREEN**

Re-run the focused tests. Expected: generated frontend dependencies permit
exact worktree removal; arbitrary untracked content still retains it.

**Step 5: Commit**

```bash
git add tools/run-acceptance-platform.sh tools/tests/test_acceptance_platform_runner.py
git commit -m "fix(acceptance): clean final frontend dependencies"
```

---

### Task 3: Make the Forge bootstrap command explicit in operations docs

**Objective:** Turn the existing vague dependency prerequisite into one literal safe command and correct lane ordering.

**Files:**
- Modify: `docs/operations/external-host-final-acceptance.md:45-70`
- Modify: `tools/tests/test_acceptance_platform_docs.py` if its existing doc assertions can be extended without contradicting its platform/product-boundary policy

**Step 1: Write a failing documentation test**

Add a narrowly scoped assertion against the external-host runbook—not the
product-neutral acceptance-platform guide—that requires both the literal
command and its placement before the health section:

```python
assert "env CI=1 npm ci --ignore-scripts" in text
assert text.index("env CI=1 npm ci --ignore-scripts") < text.index("## 6. Certify health")
```

**Step 2: Verify RED**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_docs.py -q
```

Expected: FAIL because the runbook currently says only “approved workflow.”

**Step 3: Implement the minimal documentation change**

After exact detached SHA/ref verification, insert a Forge candidate-bootstrap
subsection that runs from `frontend/mission-planner`:

```bash
env CI=1 npm ci --ignore-scripts
```

State that it prepares the health card, lint, and Vitest dependencies; it is not
a browser installer; and it must complete before health. Keep the existing
administrative browser-provisioning boundary intact.

**Step 4: Verify GREEN**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_docs.py -q
```

Run the repository Markdown command for the changed document if the required
Markdown tooling is available on the execution host.

**Step 5: Commit**

```bash
git add docs/operations/external-host-final-acceptance.md tools/tests/test_acceptance_platform_docs.py
git commit -m "docs: specify Forge frontend bootstrap"
```

---

### Task 4: Consolidate, review, and prove the exact Forge head

**Objective:** Produce a clean, pushed candidate and authoritative Forge proof without retrying an already-spent final lane.

**Files:**
- Modify only if required by review findings from Tasks 1–3.
- Evidence: Forge host state outside the repository.

**Step 1: Run local scope verification**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_contracts.py \
  tools/tests/test_acceptance_platform_docs.py \
  tools/tests/test_acceptance_platform_runner.py -q
ACCEPTANCE_POLICY_BASE_SHA=e0d38ca849ce43f5dea67add57fa51eda8770935 ./tools/verify static
```

Treat the known unrelated local adapter-fixture and pre-existing Prettier
baseline failures as baselines only if they reproduce unchanged from a clean
base comparison; do not claim a full local pass if either remains.

**Step 2: Review the candidate diff**

- Inspect `git diff e0d38ca8..HEAD --check` and added lines for secrets,
  shell injection, broad deletion, unbounded logs, and arbitrary command
  execution.
- Confirm the only operational command added is the literal, fixed npm argv
  with `CI=1` and `--ignore-scripts`.
- Because Brian prohibited subagents, record that independent agent review was
  not performed; perform and retain a controller self-review instead.

**Step 3: Push the exact candidate**

```bash
git push -u origin fix/forge-frontend-dependencies
git ls-remote --heads origin refs/heads/fix/forge-frontend-dependencies
```

Require remote SHA equals local `HEAD`.

**Step 4: Forge candidate bootstrap and health/static**

On a new detached Forge checkout for the pushed SHA/ref:

```bash
cd frontend/mission-planner
env CI=1 npm ci --ignore-scripts
cd ../..
```

Then run the repository’s health lane, checksum-verify its fingerprint and
manifest, and run static with the fingerprint. Stop on any non-passed result.

**Step 5: One authorized Forge final lane**

Only after fresh health/static pass, start exactly one tracked 1800-second
final lane using separate task, evidence, state, ledger, and runner-checkout
roots. Verify candidate and discovery evidence manifests, final authority,
SHA/ref/fingerprint bindings, exact 1920×1080 browser evidence, image identity,
and cleanup. Do not use local Compose, Vite, or standalone Playwright as a
substitute.

**Step 6: Final commit/report state**

Commit any review-only correction using a Conventional Commit, push it, and rerun
fresh Forge health/static/final for the new SHA only with explicit Brian
authorization. Report exact commands, commit IDs, baseline exceptions,
sealed-evidence paths/digests, and whether final acceptance was actually
claimed.
