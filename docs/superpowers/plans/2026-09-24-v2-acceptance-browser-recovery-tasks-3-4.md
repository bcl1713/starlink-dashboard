# Tasks 3–4: Operator workflow and exact-head evidence

Companion to [2026-09-24-v2-acceptance-browser-recovery](2026-09-24-v2-acceptance-browser-recovery.md).

## Task 3: Operator workflow and regression suite

**Files:**

- Modify: `docs/operations/acceptance-platform.md`
- Modify: `tools/tests/test_acceptance_platform_docs.py`
- Test: `tools/tests/test_acceptance_platform_health.py`
- Test: `tools/tests/test_acceptance_platform_runner.py`
- Test: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**

- Documents final browser ownership, neutral preflight, 900-second monitored
  execution, diagnostic log paths, and recovery authorization/ledger rules.

- Leaves product contracts unchanged and browser operational authority
  platform-owned.

- [ ] **Step 1: Write failing documentation assertions**

Add assertions requiring the operator guide to contain the concepts and literal
terms:

```python
assert "headed Xvfb" in guide
assert "900-second" in guide
assert "adapter.stderr.log" in guide
assert "explicit authorization" in guide
assert "final build ledger" in guide
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_docs.py`

Expected: FAIL because the guide does not yet prescribe the new final-browser
and recovery behavior.

- [ ] **Step 3: Update the operator guide**

Document this concrete order:

1. run and checksum-verify health;
2. run static only after health;
3. issue final through one tracked process, 900-second budget, durable
   stdout/stderr;

4. runner owns headed Xvfb/CDP browser resources and pre-journey native metrics;
5. inspect sealed `adapter.stdout.log`/`adapter.stderr.log` on failure;
6. after interruption, inspect ledger/images/task resources and obtain explicit
   human authorization before a recovery attempt;

7. verify cleanup without deleting volumes.

State explicitly that callers must not hand-launch a headless browser as final
acceptance evidence.

- [ ] **Step 4: Run all platform regression tests and verify GREEN**

Run: `pytest -q tools/tests/test_acceptance_platform_*.py
tools/tests/test_v2_acceptance_browser_*.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/operations/acceptance-platform.md tools/tests/test_acceptance_platform_docs.py
git commit -m "docs(acceptance): document final browser recovery"
```

## Task 4: Exact-head acceptance evidence

**Files:**

- Modify: no tracked files.
- Evidence: external SHA-qualified health, static, final, and report roots only.

**Interfaces:**

- Consumes the published candidate SHA, platform profile, and V2 contract.
- Produces sealed health/static/final evidence and a human-readable report
  attachment.

- [ ] **Step 1: Publish and verify candidate identity**

Push commits, fetch `origin/feat/v2-mission-retirement`, and require exact
local/remote SHA equality. Preserve existing named untracked review reports.
Confirm no task-owned resources are present and final ledger root is absent for
the new `(SHA, profile checksum, contract checksum)` tuple.

- [ ] **Step 2: Run exact-head health and verify its sealed evidence**

Run the repository wrapper from repository root with the provisioned profile.
Verify fingerprint, candidate manifest/discovery authority, browser identity,
native metrics/raster, checksums, and health cleanup.

Expected: health passes before static/build/product work.

- [ ] **Step 3: Run exact-head static and verify its sealed evidence**

Run the declared static lane using the current health fingerprint. Verify every
declared command and static checksums.

Expected: static passes before final issuance.

- [ ] **Step 4: Run exactly one final lane as a monitored process**

Launch the runner as a background tracked process with `notify=true`, a
900-second budget, durable stdout/stderr under the final evidence root, and no
caller-supplied headless browser/CDP setup. The runner itself must own
browser/Xvfb lifecycle. Do not retry the final build.

- [ ] **Step 5: Independently inspect evidence and cleanup**

Verify final manifest outcome, image IDs, control results, browser
metrics/raster, journey pre/post artifacts, adapter diagnostics if failed, all
checksum envelopes, and absence of task
containers/networks/listeners/processes/profile/task root. Retain volumes. Write
and attach the human-readable final report.

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 implement each platform and adapter requirement;
  Task 3 documents the new contract; Task 4 supplies fresh exact-head
  runtime/browser proof.

- **Shared files/interfaces:** Task 1 introduces the final browser lifecycle
  consumed by Task 2’s journey launch and Task 4; Task 2 changes only
  adapter/runner error transport; Task 3 consumes established behavior without
  changing code interfaces; Task 4 changes no tracked files.

- **Placeholder scan:** no omitted implementation or test steps remain.
- **Review focus coverage:** Task 1 covers caller browser authority and viewport
  mismatch; Task 2 covers exit-versus-timeout and diagnostic budgets; Task 1/4
  cover cleanup; Task 3 documents the monitored recovery rule.

[Return to the main plan](2026-09-24-v2-acceptance-browser-recovery.md).
