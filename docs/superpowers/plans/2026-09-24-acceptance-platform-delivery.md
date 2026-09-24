# Acceptance Platform Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Deliver the generic runner, V2 journey adapter, operator documentation,
and one exact-head V2 acceptance run that consumes a certified platform profile.

**Architecture:** Runner owns lane selection, fingerprint gating, result strength,
evidence finalization, and one cleanup path. The V2 adapter receives a platform-
owned browser session and performs product actions only. Documentation keeps
platform operations separate from V2 product semantics.

**Tech Stack:** Python 3.11, pytest, Node ESM, `@playwright/test`, Markdown.

**Spec:**
`docs/superpowers/specs/2026-09-24-generic-acceptance-platform-design.md`

## Global Constraints

- No product command begins without current matching health fingerprint.
- Static and diagnostic lanes never claim final acceptance.
- V2 adapter cannot spawn a browser, Docker, installer, or cleanup process.
- Positive journey is Create Mission -> Detail -> Add Leg -> KML upload ->
  Activate -> Overview through deployed frontend/backend only.
- Preserve pre-existing untracked reports. Remove only the four superseded
  V2-only partial runner files after useful test assertions are migrated.
- Generated evidence is never tracked or committed.

## Review Focus

1. Missing/stale health proof must make runner exit environment-blocked without
   source bootstrap, Docker, or journey invocation.
2. Adapter source must contain no launch/provision/cleanup authority.
3. Product failure plus cleanup failure must retain product failure as primary.
4. Final result requires controls, journey, exact viewport, manifest, checksums,
   and cleanup—not a subset.

---

### Task 1: Generic runner and V2 journey adapter

**Files:**

- Create: `tools/acceptance/platform/runner.py`
- Create: `tools/acceptance/journeys/v2-mission-retirement.mjs`
- Create: `tools/run-acceptance-platform.sh`
- Create: `tools/tests/test_acceptance_platform_runner.py`

**Interfaces:**

- Consumes platform model, health, evidence, and Compose interfaces from earlier
  plans plus V2 TOML.
- Exposes `main(argv: Sequence[str]) -> int` with `health`, `static`,
  `diagnostic`, and `final` lanes.
- Produces a manifest with outcome and maximum evidence claim.

- [ ] **Step 1: Write failing lane and adapter-boundary tests**

```python
@pytest.mark.parametrize("lane", ["static", "diagnostic"])
def test_nonfinal_lanes_cannot_serialize_final_pass(lane: str) -> None:
    manifest = run_with_lane(lane, _current_health())
    assert manifest["final_acceptance"] is False


def test_missing_health_fingerprint_skips_product_executor() -> None:
    calls: list[str] = []
    result = main(_argv(fingerprint="missing", executor=lambda argv: calls.append(argv[0])))
    assert result == 2
    assert calls == []


def test_v2_adapter_has_no_platform_authority() -> None:
    source = V2_ADAPTER.read_text(encoding="utf-8")
    assert "spawn(" not in source
    assert "--remote-debugging-port" not in source
    assert "Create New Mission" in source
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py`

Expected: collection fails because runner/adapter do not exist.

- [ ] **Step 3: Implement runner lanes and one cleanup owner**

`health` invokes only certification. All product lanes validate fingerprint first.
`static` runs contract-declared commands through platform bootstrap; `diagnostic`
is explicitly non-final; `final` executes static, one build ledger, no-build
runtime, public controls, generic browser card, then product adapter. One
`try/finally` finalizes evidence and records primary/cleanup results separately.

- [ ] **Step 4: Implement V2 visible journey adapter**

Accept only platform browser session, deployed origin, evidence writer, and
validated KML path. Drive visible Create New Mission, mission detail, Add Leg,
upload, Activate, Overview. Require browser-observed activation success and
visible active V2 route/context/POIs. Scope polling to navigation context and
wait for `getAnimations({ subtree: true })` settlement before geometry checks.

- [ ] **Step 5: Add final-strength/cleanup regressions**

```python
def test_cleanup_failure_preserves_product_failure() -> None:
    manifest = run_with(build_failure=True, cleanup_failure=True)
    assert manifest["outcome"] == "failed"
    assert manifest["cleanup"]["outcome"] == "failed"


def test_final_requires_every_required_result() -> None:
    manifest = run_with(control_failure=True)
    assert manifest["final_acceptance"] is False
    assert manifest["outcome"] == "failed"
```

- [ ] **Step 6: Verify GREEN and replace partial V2 runner**

Run: `pytest -q tools/tests/test_acceptance_platform_runner.py`

Expected: PASS.

Compare partial untracked V2 runner assertions with new tests. Remove only:

```text
tools/acceptance/preflight.py
tools/acceptance/v2_mission_retirement.py
tools/run-v2-mission-retirement-acceptance.sh
tools/tests/test_v2_acceptance_runner.py
```

- [ ] **Step 7: Commit runner delivery**

```bash
git add tools/acceptance/platform/runner.py tools/acceptance/journeys/v2-mission-retirement.mjs \
  tools/run-acceptance-platform.sh tools/tests/test_acceptance_platform_runner.py
git add -u tools/acceptance/preflight.py tools/acceptance/v2_mission_retirement.py \
  tools/run-v2-mission-retirement-acceptance.sh tools/tests/test_v2_acceptance_runner.py
git commit -m "feat(acceptance): run V2 contract on platform"
```

### Task 2: Platform and V2 documentation

**Files:**

- Create: `docs/operations/acceptance-platform.md`
- Create: `docs/missions/v2-mission-retirement-acceptance.md`
- Modify: `docs/missions/README.md`
- Create: `tools/tests/test_acceptance_platform_docs.py`

**Interfaces:**

- Platform doc explains provisioning boundary, health fingerprint, result types,
  final build state machine, evidence, and cleanup.
- V2 doc explains services, public controls, KML, and visible journey only.

- [ ] **Step 1: Write failing documentation tests**

```python
def test_platform_doc_requires_health_fingerprint() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    assert "health fingerprint" in text.lower()
    assert "environment_blocked" in text
    assert "npm ci" not in text


def test_v2_doc_names_journey_not_browser_settings() -> None:
    text = V2_DOC.read_text(encoding="utf-8")
    assert "Create New Mission" in text
    assert "v2-activation-route.kml" in text
    assert "--remote-debugging-port" not in text
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_docs.py`

Expected: collection fails because docs/test module do not exist.

- [ ] **Step 3: Write platform operations documentation**

Explain administrative browser bundle provisioning separately from branch runs,
health certification/fingerprint inspection, one-build state machine, outcomes,
evidence roots, and cleanup. State cached diagnostics cannot replace final fresh-
image evidence.

- [ ] **Step 4: Write V2 contract documentation and index it**

Describe V2 services, public controls, KML, and visible journey. Link it from
mission docs. Do not duplicate Chrome, npm, Docker, Xvfb, or timeout configuration.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
npx markdownlint-cli2 docs/operations/acceptance-platform.md \
  docs/missions/v2-mission-retirement-acceptance.md docs/missions/README.md
pytest -q tools/tests/test_acceptance_platform_docs.py tools/tests/test_acceptance_platform_*.py
```

Expected: PASS.

```bash
git add docs/operations/acceptance-platform.md docs/missions/v2-mission-retirement-acceptance.md \
  docs/missions/README.md tools/tests/test_acceptance_platform_docs.py
git commit -m "docs: describe acceptance platform contracts"
```

### Task 3: Exact-head health and V2 final evidence

**Files:**

- Modify: no tracked files.
- Evidence: platform health root and candidate root outside repository content.

**Interfaces:**

- Consumes committed platform/profile/V2 contract.
- Produces external health and final evidence manifests only.

- [ ] **Step 1: Verify final candidate identity**

Run independent bounded checks for tracked status, full local SHA, and named
remote feature ref. Preserve named pre-existing reports and ensure partial V2
runner files are absent.

Expected: remote/local exact SHA match and no generated evidence staged.

- [ ] **Step 2: Run and inspect platform health**

Run health for the default profile. Independently inspect fingerprint/manifest for
browser bundle identity, Docker/Compose identity, exact neutral metrics/raster,
profile/card checksums, checksums, and cleanup.

Expected: current pass; otherwise `environment_blocked`, no V2 static/build/
journey, and stop for platform remediation.

- [ ] **Step 3: Run V2 static lane**

Run at final SHA with current fingerprint. Retain exact declared commands and tool
identities. A failure blocks final lane without spending fresh-build budget.

- [ ] **Step 4: Run exactly one final V2 lane**

Verify no prior build-ledger claim for tuple, then run one no-cache build and one
no-build startup. Inspect controls, deployed journey, pre/post viewport raster,
manifest, checksums, and cleanup. If wrapper timeout proves every required image,
verify one no-build start; otherwise retain failure without retry.

- [ ] **Step 5: Independently verify evidence/cleanup; commit nothing**

Validate checksums from each evidence root and inspect candidate SHA/ref, contract
checksum, platform fingerprint, image IDs, outcome, and cleanup. Verify task
containers/networks/listeners/processes are absent and volumes retained. Supply
external manifests/checksums to final independent review; do not commit them.

## Plan Self-Review

Task 1 binds generic execution to certified platform capability and keeps V2
product-only. Task 2 documents the authority split. Task 3 supplies the sole
fresh exact-head evidence lane. Every specification requirement maps to one task
and no placeholder work remains.
