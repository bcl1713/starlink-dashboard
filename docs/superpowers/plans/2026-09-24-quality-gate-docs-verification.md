# Quality-Gate Documentation and Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the canonical verification interface and produce exact-head
evidence for the quality-gate contract.

**Architecture:** This plan consumes the runner and CI from the linked
[runner/CI plan](2026-09-24-quality-gate-runner-ci.md). It makes contributor
entry points name only supported commands, distinguishes browser acceptance,
and verifies the pushed PR head against `dev`.

**Tech Stack:** Python 3.13, `uv`, pytest, npm, Markdownlint, Lychee, GitHub
Actions.

**Spec:**
`docs/superpowers/specs/2026-09-24-quality-gate-contract-design.md`

## Global Constraints

- The runner contract is `./tools/verify {static|backend|frontend|all}`.
- Documentation must say static/frontend run root-relative and backend pytest
  intentionally uses `backend/starlink-location`.
- `npm run test:unit`, not the unrelated `test` script, is the frontend test.
- Mention `dev` as the integration branch.
- Browser acceptance is scoped exact-SHA 1920x1080 CDP work, not a generic CI
  substitute or unconditional job.
- Do not change production dependencies, Dockerfiles, or browser product code.

## Review Focus

- Every public contributor entry point names the same four runner tiers.
- Backend focused-test examples remain available alongside the canonical gate.
- Docs do not promise that green CI proves runtime/browser acceptance.
- Exact pushed head, PR base, and the three CI job results are recorded.
- No plan, docs, or workflow edit causes Markdownlint or Lychee regression.

---

### Task 1: Canonical Contributor Documentation

**Files:**

- Create: `docs/contributing/quality-gates.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/contributing/testing-guide.md`
- Modify: `backend/starlink-location/README.md`
- Modify: `backend/starlink-location/docs/TESTING.md`
- Create: `tools/tests/test_docs.py`

**Interfaces:**

- `docs/contributing/quality-gates.md` is the authoritative command reference.
- Other entry points link to it rather than copying a conflicting test suite.

- [ ] **Step 1: Write failing documentation contract tests**

```python
DOCS = {
    Path("docs/contributing/quality-gates.md"),
    Path("CONTRIBUTING.md"),
    Path("docs/contributing/testing-guide.md"),
    Path("backend/starlink-location/README.md"),
    Path("backend/starlink-location/docs/TESTING.md"),
}

def test_quality_gate_docs_name_canonical_contract():
    text = "\n".join(path.read_text() for path in DOCS)
    assert "./tools/verify static" in text
    assert "./tools/verify backend" in text
    assert "./tools/verify frontend" in text
    assert "./tools/verify all" in text
    assert "npm run test:unit" in text
    assert "1920x1080" in text
    assert "dev" in text
```

- [ ] **Step 2: Confirm the documentation test fails**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_docs.py -v
```

Expected: FAIL because the canonical guide does not yet exist.

- [ ] **Step 3: Write the authoritative guide and align entry points**

Use this command block in `docs/contributing/quality-gates.md`:

```bash
./tools/verify static
./tools/verify backend
./tools/verify frontend
./tools/verify all
```

Explain that static runs formatting, linting, filenames, docs formatting, and
links; backend runs the full backend pytest suite from its existing backend
context; frontend runs Vitest and production build. State that normal CI uses
these as separate required jobs.

Add a browser boundary paragraph: browser-relevant changes also require
exact-SHA CDP acceptance at 1920x1080; a green `tools/verify all` does not
substitute for browser/runtime evidence. Link this guide from `CONTRIBUTING.md`
and identify `dev` as the integration branch. Replace stale frontend test
examples with `npm run test:unit`. Retain focused backend `pytest` examples,
but label `./tools/verify backend` as the full canonical backend gate.

- [ ] **Step 4: Run documentation contract and format/link tests**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_docs.py -v
npx markdownlint-cli2 "docs/**/*.md" CONTRIBUTING.md \
  backend/starlink-location/README.md backend/starlink-location/docs/TESTING.md
lychee --no-progress docs/
```

Expected: PASS. The test confirms the four tiers, frontend unit script,
`1920x1080`, and `dev` are all discoverable.

- [ ] **Step 5: Commit documentation alignment**

```bash
git add docs/contributing/quality-gates.md CONTRIBUTING.md \
  docs/contributing/testing-guide.md backend/starlink-location/README.md \
  backend/starlink-location/docs/TESTING.md tools/tests/test_docs.py
git commit -m "docs(quality): document canonical verification gates"
```

### Task 2: Exact-Head Verification and Pull Request Evidence

**Files:**

- Modify: no source files unless an earlier verification exposes a defect.

**Interfaces:**

- Consumes: completed runner/CI plan and Task 1.
- Produces: remotely verified exact head and CI evidence for independent review.

- [ ] **Step 1: Run contract tests**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_verify.py tools/tests/test_quality_gate_workflow.py \
  tools/tests/test_docs.py -v
```

Expected: PASS.

- [ ] **Step 2: Run every canonical tier and nested static invocation**

```bash
./tools/verify static
./tools/verify backend
./tools/verify frontend
./tools/verify all
(cd backend/starlink-location && ../../tools/verify static)
```

Expected: PASS. The nested call emits root-relative static targets; backend
pytest itself runs only from the intentional backend context.

- [ ] **Step 3: Prove production-boundary integrity and branch scope**

```bash
git diff --check origin/dev...HEAD
git diff --name-only origin/dev...HEAD
git diff origin/dev...HEAD -- backend/starlink-location/requirements.txt \
  backend/starlink-location/Dockerfile
```

Expected: no whitespace errors and an empty final diff. If any verification
fails, return to the owning task, write or preserve the failing regression,
repair it, and restart this task at Step 1.

- [ ] **Step 4: Push and read back the exact remote head**

```bash
git push origin HEAD
remote=$(git ls-remote origin "refs/heads/$(git branch --show-current)" \
  | awk '{print $1}')
test "$remote" = "$(git rev-parse HEAD)"
```

Expected: the remote SHA equals local `HEAD`.

- [ ] **Step 5: Create and verify the `dev`-targeting PR**

Create a non-draft PR linking issue #179 and the approved spec. Verify its base
is `dev`, its head SHA equals the pushed SHA, and GitHub reports successful
`Static Quality Gate`, `Backend Test Gate`, and `Frontend Test and Build Gate`
jobs. Record browser/runtime acceptance as not applicable because this PR only
changes verification tooling and documentation.
