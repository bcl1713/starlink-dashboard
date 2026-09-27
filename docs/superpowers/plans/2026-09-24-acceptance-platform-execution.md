# Acceptance Platform Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Certify platform health independently from product code and implement
isolated Compose execution with a one-build ledger and strict reconciliation.

**Architecture:** The health card verifies a pre-provisioned browser and Docker/
Compose environment, then emits a checksum-bound fingerprint. Compose helpers
are invoked only by the generic runner and enforce isolated topology, one final
build, and no-build startup.

**Tech Stack:** Python 3.11, pytest, Node ESM, `@playwright/test`, Xvfb, Docker
Compose, SHA-256.

**Spec:**
`docs/superpowers/specs/2026-09-24-generic-acceptance-platform-design.md`

## Global Constraints

- Health failure is `environment_blocked` and must stop before a product command.
- Health card runs headed Chrome on task-owned Xvfb and proves native exact
  viewport without `Emulation.*` APIs.
- Compose overrides are external, use tracked example configuration only, and
  start only contract services.
- One final build is allowed per profile checksum/candidate SHA/contract checksum.
- Never use `up --build`, concurrent builds, or a retry final build.

## Review Focus

1. Reject stale profile/card/browser/checksum fingerprint before product work.
2. Reject neutral viewport mismatch before a product runtime is built.
3. Reconcile wrapper timeout only with all image markers and inspected tags.
4. Reject inherited ports, fixed container names, private environment files, and
   unrelated services in resolved topology.

---

### Task 1: Health card and fingerprint authority

**Files:**

- Create: `tools/acceptance/platform/evidence.py`
- Create: `tools/acceptance/platform/health.py`
- Create: `tools/acceptance/browser/platform-card.mjs`
- Create: `tools/tests/test_acceptance_platform_health.py`

**Interfaces:**

- Consumes `PlatformProfile` and `BrowserBundle` from foundation plan.
- Produces `run_platform_health(profile, evidence_root, executor) -> HealthFingerprint`.
- Produces `validate_fingerprint(profile, fingerprint_path) -> HealthFingerprint`.

- [ ] **Step 1: Write failing health/fingerprint tests**

```python
def test_health_fingerprint_rejects_profile_checksum_drift(tmp_path: Path) -> None:
    path = _write_fingerprint(tmp_path, _fingerprint(profile_checksum="a" * 64))
    with pytest.raises(ValueError, match="profile checksum"):
        validate_fingerprint(_profile(checksum="b" * 64), path)


def test_health_failure_blocks_before_product_executor() -> None:
    calls: list[str] = []
    result = run_product_lane(_inputs(), health=lambda: _failed_health(), execute=lambda _: calls.append("product"))
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert calls == []


def test_platform_card_uses_native_window_protocol() -> None:
    source = PLATFORM_CARD.read_text(encoding="utf-8")
    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_health.py`

Expected: collection fails because health modules do not exist.

- [ ] **Step 3: Implement contained evidence/fingerprint writing**

Create evidence only below a verified SHA-qualified root. Reject symlink parents/
targets, create directories `0700` and files `0600`, inventory sorted relative
paths, write manifest/checksums, and verify from artifact root. Fingerprint binds
profile checksum, card checksum, Docker/Compose identity, browser identity,
measured neutral metrics/raster, timestamps, and evidence-manifest hash.

- [ ] **Step 4: Implement the generic Node health card**

Accept only platform-supplied verified executable, display, profile, CDP port,
and evidence paths. Retain stdout/stderr, poll child state and `/json/version`
for 120 seconds, attach through `@playwright/test`, call
`Browser.getWindowForTarget` then `Browser.setContentsSize(1920,1080)`, and
require neutral page inner/visual viewport `1920x1080`, DPR 1, decoded PNG
`1920x1080`. Clean CDP/browser/Xvfb in one `finally` path.

- [ ] **Step 5: Implement health runner and run deterministic tests**

Verify browser bundle before card invocation. Probe Docker/Compose identity with
bounded safe commands. On any fault retain evidence and return
`environment_blocked`; do not create product resources.

Run: `pytest -q tools/tests/test_acceptance_platform_health.py`

Expected: PASS.

- [ ] **Step 6: Run real neutral health certification and commit**

Run platform health against the configured profile. Expected: passing current
fingerprint with exact metrics and cleanup, or classified environment block before
Docker/product work. Do not run V2 runtime in this task.

```bash
git add tools/acceptance/platform/evidence.py tools/acceptance/platform/health.py \
  tools/acceptance/browser/platform-card.mjs tools/tests/test_acceptance_platform_health.py
git commit -m "feat(acceptance): certify platform health"
```

### Task 2: Isolated Compose and one-build ledger

**Files:**

- Create: `tools/acceptance/platform/compose.py`
- Create: `tools/tests/test_acceptance_platform_compose.py`

**Interfaces:**

- Consumes `PlatformProfile`, `ProductContract`, `BuildLedgerKey`, and evidence
  writer.
- Produces `render_task_override`, `resolve_topology`, `reconcile_build`,
  `claim_build_ledger`, `start_no_build`, `run_controls`, and `cleanup_compose`.

- [ ] **Step 1: Write failing topology/reconciliation tests**

```python
def test_duplicate_build_ledger_claim_is_refused(tmp_path: Path) -> None:
    ledger = BuildLedger(tmp_path)
    key = BuildLedgerKey("a" * 40, "b" * 64, "c" * 64)
    ledger.claim(key)
    with pytest.raises(ValueError, match="already claimed"):
        ledger.claim(key)


def test_timeout_with_complete_images_proceeds_once() -> None:
    result = reconcile_build(124, _complete_two_image_log(), _inspect_present)
    assert result.usable is True
    assert result.wrapper_anomaly is True


def test_missing_unpack_or_tag_blocks_startup() -> None:
    assert reconcile_build(124, _missing_unpack_log(), _inspect_missing).usable is False
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_compose.py`

Expected: collection fails because Compose controls do not exist.

- [ ] **Step 3: Implement override and resolved-topology validation**

Generate external override from tracked `.env.example`. Replace ports, container
names, and private environment file; retain only contract services; allocate task
resources. Inspect resolved config without printing secrets. Reject inherited
fixed mappings/names/private env file/undeclared service or resource outside task
namespace.

- [ ] **Step 4: Implement build ledger and reconciliation**

Use profile-owned Docker/Compose argv. Stream retained plain BuildKit output while
preserving exit. On timeout/nonzero require per-tag export/naming/unpack/final
completion and inspected image IDs. A usable anomaly receives exactly one
no-build startup; incomplete build permanently closes ledger tuple.

- [ ] **Step 5: Add sequencing/cleanup tests and verify GREEN**

With injected fake executor assert one `--no-cache --progress=plain` build, no
`up --build`, at most one `--no-build` startup, and no start after real failure.
Assert cleanup removes only named project resources and preserves volumes.

Run: `pytest -q tools/tests/test_acceptance_platform_compose.py`

Expected: PASS.

- [ ] **Step 6: Commit Compose platform boundary**

```bash
git add tools/acceptance/platform/compose.py tools/tests/test_acceptance_platform_compose.py
git commit -m "feat(acceptance): add isolated build ledger"
```

## Plan Self-Review

Task 1 certifies immutable environment capability and blocks branches early. Task
2 owns topology, build, reconciliation, and cleanup mechanics. Product adapters
have no authority in either task. All required failure modes have deterministic
coverage and one real neutral health execution.
