# Acceptance Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Establish strict product-contract authority and immutable browser-bundle
verification without executing an installer during branch acceptance.

**Architecture:** Python stdlib models parse TOML into validated product-only
contracts. A separate browser verifier validates a pre-provisioned executable
against a platform profile before any health card may use it.

**Tech Stack:** Python 3.11, `tomllib`, pytest, SHA-256.

**Spec:**
`docs/superpowers/specs/2026-09-24-generic-acceptance-platform-design.md`

## Global Constraints

- Product TOML rejects browser paths, package-manager/install commands, Docker
  command fragments, timeout, Xvfb/CDP, evidence, retry, and cleanup keys.
- Candidate SHA/ref are exact CLI inputs, not mutable TOML fields.
- Browser verification never runs npm, npx, Playwright installation, or PATH-
  resolved installers.
- All new source/test modules remain below 300 lines.

## Review Focus

1. Reject operational TOML authority before resource allocation.
2. Reject browser symlink/root escape/wrong hash/wrong version before launch.
3. Recheck browser identity after a replacement race and before returning a launch
   command.

---

### Task 1: Product contracts and result-strength model

**Files:**

- Create: `tools/acceptance/platform/__init__.py`
- Create: `tools/acceptance/platform/model.py`
- Create: `tools/acceptance/platform/contracts.py`
- Create: `tools/acceptance/contracts/v2-mission-retirement.toml`
- Create: `tools/tests/test_acceptance_platform_model.py`
- Create: `tools/tests/test_acceptance_platform_contracts.py`

**Interfaces:**

- Produces frozen `PlatformProfile`, `ProductContract`, `Lane`, `Outcome`,
  `RunResult`, and `BuildLedgerKey` models.
- Produces `load_product_contract(path: Path) -> ProductContract`.
- Later plans consume parsed models only; no raw TOML parsing elsewhere.

- [ ] **Step 1: Write failing contract and strength tests**

```python
@pytest.mark.parametrize("key", ["chrome_path", "timeout_seconds", "npm_command"])
def test_contract_rejects_operational_authority(tmp_path: Path, key: str) -> None:
    path = _write_contract(tmp_path, extra=f"{key} = 'forbidden'\n")
    with pytest.raises(ValueError, match="platform-owned"):
        load_product_contract(path)


def test_static_result_cannot_claim_final_acceptance() -> None:
    with pytest.raises(ValueError, match="final"):
        RunResult(lane=Lane.STATIC, outcome=Outcome.PASSED, final=True).validate()
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_model.py tools/tests/test_acceptance_platform_contracts.py`

Expected: collection fails because the platform modules do not exist.

- [ ] **Step 3: Implement strict frozen models and TOML parsing**

```python
@dataclass(frozen=True)
class ProductContract:
    name: str
    services: tuple[str, ...]
    static_groups: tuple[StaticGroup, ...]
    controls: tuple[RuntimeControl, ...]
    journey_adapter: Path
    assets: tuple[Path, ...]


def load_product_contract(path: Path) -> ProductContract:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    _reject_operational_keys(raw)
    return _parse_product_contract(raw, path)
```

Reject unknown top-level sections and uncontained repository-relative paths.
Require external CLI input validation to preserve full 40-character SHA/ref
literally; never normalize whitespace or abbreviated IDs.

- [ ] **Step 4: Add V2 product-only contract and assertions**

Declare V2 static groups, `starlink-location`/`mission-planner`, five public
controls, tracked KML, and the journey adapter. It names no operational runtime
settings.

```python
def test_v2_contract_has_only_product_authority() -> None:
    contract = load_product_contract(V2_CONTRACT)
    assert contract.services == ("starlink-location", "mission-planner")
    assert contract.assets == (Path("docs/missions/acceptance-assets/v2-activation-route.kml"),)
```

- [ ] **Step 5: Verify GREEN and commit**

Run: `pytest -q tools/tests/test_acceptance_platform_model.py tools/tests/test_acceptance_platform_contracts.py`

Expected: PASS.

```bash
git add tools/acceptance/platform/__init__.py tools/acceptance/platform/model.py \
  tools/acceptance/platform/contracts.py tools/acceptance/contracts/v2-mission-retirement.toml \
  tools/tests/test_acceptance_platform_model.py tools/tests/test_acceptance_platform_contracts.py
git commit -m "feat(acceptance): add platform product contracts"
```

### Task 2: Immutable browser bundle boundary

**Files:**

- Create: `tools/acceptance/platform/browser_bundle.py`
- Create: `tools/acceptance/platform/profiles/default.toml`
- Create: `tools/tests/test_acceptance_platform_bundle.py`

**Interfaces:**

- Consumes `PlatformProfile`.
- Produces `BrowserBundle` and `verify_browser_bundle(profile) -> BrowserBundle`.
- The health plan receives only a verified absolute executable.

- [ ] **Step 1: Write adversarial bundle tests**

```python
def test_bundle_rejects_symlinked_executable(tmp_path: Path) -> None:
    target = _fake_executable(tmp_path / "target", version="Chrome 124")
    executable = tmp_path / "chrome"
    executable.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        verify_browser_bundle(_profile_for(executable))


def test_bundle_rejects_hash_or_version_mismatch(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path, version="Chrome 123")
    with pytest.raises(ValueError, match="identity"):
        verify_browser_bundle(_profile_for(executable, sha256="0" * 64, version="Chrome 124"))
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tools/tests/test_acceptance_platform_bundle.py`

Expected: collection fails because the bundle verifier does not exist.

- [ ] **Step 3: Implement profile/bundle verification**

Profile browser settings contain platform-store-contained executable path, exact
version, byte size, and SHA-256. Reject symlinks, root escapes, non-regular files,
non-executable files, size/hash mismatch, and version mismatch. Invoke only the
verified absolute executable with `--version` under a 15-second bound.

```python
def verify_browser_bundle(profile: PlatformProfile) -> BrowserBundle:
    executable = _verified_regular_file(profile.browser.executable, profile.browser.store_root)
    if sha256_file(executable) != profile.browser.sha256:
        raise ValueError("browser identity hash mismatch")
    version = run_checked((str(executable), "--version"), timeout_seconds=15)
    if version.stdout.strip() != profile.browser.version:
        raise ValueError("browser identity version mismatch")
    return BrowserBundle(executable, profile.browser.sha256, version.stdout.strip())
```

- [ ] **Step 4: Add post-verification replacement test**

Replace the executable after initial hash through a test hook. The launch command
constructor must stat/hash it again immediately before returning it and reject the
replacement. Assert verifier source contains no installer execution.

- [ ] **Step 5: Verify GREEN and commit**

Run: `pytest -q tools/tests/test_acceptance_platform_bundle.py`

Expected: PASS.

```bash
git add tools/acceptance/platform/browser_bundle.py \
  tools/acceptance/platform/profiles/default.toml tools/tests/test_acceptance_platform_bundle.py
git commit -m "feat(acceptance): verify immutable browser bundles"
```

## Plan Self-Review

Task 1 owns product/operational authority separation and exact input modelling.
Task 2 owns immutable browser identity and prohibits branch installer authority.
All interfaces used by later plans are defined here. No placeholder work remains.
