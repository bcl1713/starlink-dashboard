# Tasks 5–6: Operator runbook, exact-head acceptance, and plan review

Companion to
[2026-09-23-v2-mission-retirement-acceptance-runbook](2026-09-23-v2-mission-retirement-acceptance-runbook.md).

## Task 5: Operator runbook and documentation contract

**Files:**

- Create: `docs/missions/v2-mission-retirement-acceptance.md`
- Modify: `docs/missions/README.md:10-27`
- Create: `tools/tests/test_v2_acceptance_docs.py`

**Interfaces:**

- Documents the exact Task 4 command and every CLI input.
- States final/diagnostic classification rules used by Task 4.
- Links from the mission documentation index without modifying product behavior.

- [ ] **Step 1: Write failing documentation contract tests**

```python
def test_runbook_is_indexed_and_uses_v2_activation_only() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    index = MISSION_INDEX.read_text(encoding="utf-8")
    assert "v2-mission-retirement-acceptance.md" in index
    assert "POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate" in runbook
    assert "POST /api/missions/" not in runbook


def test_runbook_distinguishes_cached_and_final_evidence() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "runtime-cached" in text
    assert "does not replace final exact-SHA" in text
    assert "--no-cache --progress=plain" in text
```

- [ ] **Step 2: Run focused test to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_docs.py`

Expected: FAIL because the runbook does not exist.

- [ ] **Step 3: Write concise operator runbook and index link**

Document a standalone command with explicit placeholders for SHA/ref, evidence
root, unique project/ports, Chrome/CDP/display/profile inputs, and optional
phase. Document expected timing budgets, which phase evidence proves what,
BuildKit wrapper reconciliation, task resource cleanup, artifacts/manifest,
final real journey, and failure classifications. State that no-cache full is
executed once for the candidate selected for acceptance, while lower-cost phases
are intentionally used during iteration.

- [ ] **Step 4: Run documentation contract test to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_docs.py`

Expected: PASS.

- [ ] **Step 5: Run Markdown and relevant tool tests**

Run:

```bash
npx markdownlint-cli2 docs/missions/v2-mission-retirement-acceptance.md \
  docs/missions/README.md
pytest -q tools/tests/test_v2_acceptance_*.py
```

Expected: both commands PASS.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/missions/v2-mission-retirement-acceptance.md docs/missions/README.md \
  tools/tests/test_v2_acceptance_docs.py
git commit -m "docs: add V2 acceptance operator runbook"
```

## Task 6: Exact-head static gates and one full scripted acceptance lane

**Files:**

- Modify: no tracked files.
- Evidence only: task-owned SHA-qualified root outside repository.

**Interfaces:**

- Consumes the committed runner and runbook from Tasks 1–5.
- Produces the exact-head evidence manifest referenced by final review; no
  generated outputs are committed.

- [ ] **Step 1: Verify clean tracked candidate and remote SHA**

Run:

```bash
git status --short
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/feat/v2-mission-retirement
```

Expected: only the known preserved untracked reports, and local/remote full SHA
match. Do not alter the known reports.

- [ ] **Step 2: Run static/frontend gates at final implementation SHA**

Run the Task 4 `static` phase with a new SHA-qualified evidence root.

Expected: pinned backend formatter/linter/tests and frontend clean install/lint/
unit/discovery/configured Chromium results recorded at the final SHA. A failure
blocks full acceptance and is classified from its literal command output.

- [ ] **Step 3: Run browser-card phase before production build**

Run the Task 4 `browser-card` phase with the same candidate SHA and task-owned
resources.

Expected: preflight exact viewport/card evidence and verified browser/display
cleanup. On mismatch, stop before Compose build.

- [ ] **Step 4: Run one full exact-SHA lane**

Run the Task 4 default `full` command once with a fresh task evidence root,
unique project name, ports, CDP port/profile, and display identity.

Expected: one measured no-cache two-service image build, one no-build startup,
all five runtime controls, real deployed V2 journey, pre/post exact viewport
metrics/PNGs, task resource cleanup, and checksum verification after cleanup.

- [ ] **Step 5: Independently read evidence after cleanup**

Run:

```bash
sha256sum -c SHA256SUMS
```

from the retained evidence root, then inspect the manifest identity, image IDs,
phase results, and cleanup result.

Expected: all checksums valid; no task container/network/listener/process
remains;
volumes are preserved. A failed full lane remains a documented failure or
coverage gap, never a success claim.

- [ ] **Step 6: Commit nothing and record evidence path in review package**

No generated evidence is staged or committed. The implementation branch remains
at the final source/docs SHA, while the external evidence manifest is supplied
to the independent final reviewer.

## Plan Self-Review

**Spec coverage:**

- Inputs, full SHA/ref validation, bounded preflight, pinned static commands,
  frontend build ownership, staged-cost policy: Tasks 1 and 4.

- External Compose isolation, one no-cache build, wrapper reconciliation,
  no-build startup, two-service topology, controls, cleanup: Task 2 and Task 4.

- Task-owned Xvfb/Chrome, exact CDP viewport protocol, real UI journey, bounded
  browser evidence: Task 3 and Task 6.

- Mode-restricted artifact manifest/checksums and post-cleanup verification:
  Task 1 and Task 6.

- Deterministic tests, documentation, and one final full candidate run: Tasks
  1–6.

**Completeness scan:** every task requirement has concrete paths, commands, and
expected outcomes; no unfinished implementation markers remain.

**Type consistency:** all downstream tasks consume `AcceptanceInputs`,
`EvidenceWriter`, `PhaseResult`, and the Task 2 build disposition under the same
names defined in Task 1/Task 2.

**Review focus mapping:** the five Review Focus cases are assigned to Tasks 1–4
and have explicit failing/green test steps.

## Documentation Impact

Task 5 adds the required operator runbook and mission-doc index link. No user
product, API, release, or architecture documentation changes are in scope.

[Return to the main
plan](2026-09-23-v2-mission-retirement-acceptance-runbook.md).
