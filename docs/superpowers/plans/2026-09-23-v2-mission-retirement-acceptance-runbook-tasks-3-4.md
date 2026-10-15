# Tasks 3–4: Headed browser card and staged runner

Companion to
[2026-09-23-v2-mission-retirement-acceptance-runbook](2026-09-23-v2-mission-retirement-acceptance-runbook.md).

## Task 3: Reusable headed Chrome CDP card and real journey

**Files:**

- Create: `tools/acceptance/browser/v2-mission-retirement.mjs`
- Create: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**

- Node script consumes JSON input produced by Task 4: browser executable, Xvfb
  display, CDP port, profile path, frontend origin, evidence directory, and
  `neutral` or `journey` mode.

- Emits one JSON result on stdout and writes bounded browser artifacts only
  under
  the supplied evidence directory.

- Task 4 treats nonzero or invalid JSON as browser-card/journey failure and
  always executes ownership cleanup.

- [ ] **Step 1: Write failing static contract tests**

```python
def test_browser_card_uses_required_cdp_window_protocol() -> None:
    source = BROWSER_SCRIPT.read_text(encoding="utf-8")
    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "1920" in source and "1080" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
    assert "@playwright/test" in source


def test_browser_card_requires_pre_and_post_neutral_metrics() -> None:
    source = BROWSER_SCRIPT.read_text(encoding="utf-8")
    assert source.count("assertExactViewport") >= 2
    assert "Create New Mission" in source
    assert "v2-activation-route.kml" in source
```

- [ ] **Step 2: Run focused test to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_browser_contract.py`

Expected: FAIL because the browser-card script does not exist.

- [ ] **Step 3: Implement owned Xvfb/Chrome/CDP lifecycle**

Use `spawn` with retained stdout/stderr and process groups. Poll child status
and
`/json/version` for 120 seconds. Attach via `chromium.connectOverCDP` imported
from `@playwright/test`; do not import Playwright internals. Record exact Chrome
path/version/SHA, display identity/geometry/PID, process tree, CDP calls, and
probe classes. Avoid `Xvfb -version`; record supported help/log-based evidence.

Implement `assertExactViewport(page, artifactPrefix)` to capture `innerWidth`,
`innerHeight`, visual viewport, DPR, and an intrinsic decoded PNG raster; reject
any value other than 1920, 1080, and 1.

- [ ] **Step 4: Implement neutral and real-journey modes**

`neutral` navigates only a local task-owned neutral page and exits cleanly after
the pre-navigation window protocol and exact viewport assertions. `journey`
uses only the supplied deployed frontend origin, executes the specified visible
UI flow, waits for browser-observed activation 200, and requires active V2
route/context/POIs before final viewport evidence. It retains bounded
screenshots, accessible/DOM contracts, and console/network records.

- [ ] **Step 5: Run focused contract test to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_browser_contract.py`

Expected: PASS.

- [ ] **Step 6: Run neutral card before expensive build**

Run from repository root:

```bash
node tools/acceptance/browser/v2-mission-retirement.mjs \
  --mode neutral --chrome /home/brian/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome \
  --evidence-dir <task-evidence-dir> --cdp-port <unused-port> \
  --display :<task-display> --profile-dir <task-profile>
```

Expected: exact `1920×1080` metrics and decoded neutral PNG, followed by no
owned CDP/display process or listener. If this does not pass, stop before a
production build and retain the classified evidence.

- [ ] **Step 7: Commit browser card**

```bash
git add tools/acceptance/browser/v2-mission-retirement.mjs \
  tools/tests/test_v2_acceptance_browser_contract.py
git commit -m "feat: add headed acceptance browser card"
```

## Task 4: Staged runner, phase isolation, and cleanup ownership

**Files:**

- Create: `tools/acceptance/preflight.py`
- Create: `tools/acceptance/v2_mission_retirement.py`
- Create: `tools/run-v2-mission-retirement-acceptance.sh`
- Create: `tools/tests/test_v2_acceptance_runner.py`

**Interfaces:**

- Consumes all Task 1–3 interfaces.
- Exposes `main(argv: Sequence[str]) -> int` and stable CLI flags documented in
  Task 5.

- Produces an evidence manifest that names one of `passed`, `failed`,
  `infrastructure_blocker`, or `coverage_gap` per phase and only asserts final
  acceptance after `full` succeeds.

- [ ] **Step 1: Write failing phase and cleanup tests**

```python
@pytest.mark.parametrize("phase", ["static", "browser-card"])
def test_lower_cost_phases_never_call_docker(phase: str, monkeypatch: pytest.MonkeyPatch) -> None:
    docker = _forbid_docker(monkeypatch)
    assert main(_argv(phase)) == 0
    assert docker.calls == []


def test_runtime_cached_manifest_is_never_final(monkeypatch: pytest.MonkeyPatch) -> None:
    assert main(_argv("runtime-cached")) == 0
    manifest = _read_manifest()
    assert manifest["final_acceptance"] is False
    assert manifest["classification"] == "cached_diagnostic"


def test_cleanup_failure_does_not_replace_primary_build_failure() -> None:
    result = _run_with(build_returncode=2, cleanup_returncode=1)
    assert result.exit_code != 0
    assert result.manifest["primary_status"] == "failed"
    assert result.manifest["cleanup_status"] == "failed"
```

- [ ] **Step 2: Run focused test to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_runner.py`

Expected: FAIL during collection because the runner modules do not exist.

- [ ] **Step 3: Implement bounded preflight and phase dispatch**

Implement separate retained commands for local identity (15 s), named remote ref
(30 s with one narrow retry), detached checkout (45 s), and sanitized topology
(45 s). Use injected command execution for deterministic tests. Dispatch:

```python
PHASES = {
    AcceptancePhase.PREFLIGHT: run_preflight,
    AcceptancePhase.STATIC: run_static,
    AcceptancePhase.BROWSER_CARD: run_browser_card,
    AcceptancePhase.RUNTIME_CACHED: run_cached_runtime,
    AcceptancePhase.FULL: run_full,
}
```

`run_full` executes preflight → static → browser card → one full build → one
no-build startup → runtime controls → journey. It does not invoke a second build
on any nonzero/timeout outcome. It records separate elapsed times for build,
start, readiness, browser card, and journey.

- [ ] **Step 4: Implement one cleanup path and manifest finalization**

Use `try/finally` in one runner owner. It passes task identity to Compose and
browser cleanup functions, preserves volumes, verifies task containers/networks,
ports, and processes are absent, then calls `EvidenceWriter.verify_checksums()`.
It records a cleanup error without replacing the primary failure.

The shell entry point must contain only strict argument forwarding:

```bash
#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$repo_root/tools/acceptance/v2_mission_retirement.py" "$@"
```

- [ ] **Step 5: Run focused runner tests to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_runner.py`

Expected: PASS.

- [ ] **Step 6: Run all acceptance-tool tests**

Run:

```bash
pytest -q tools/tests/test_v2_acceptance_model.py \
  tools/tests/test_v2_acceptance_artifacts.py \
  tools/tests/test_v2_acceptance_compose.py \
  tools/tests/test_v2_acceptance_browser_contract.py \
  tools/tests/test_v2_acceptance_runner.py
```

Expected: PASS.

- [ ] **Step 7: Commit staged orchestration**

```bash
git add tools/acceptance/preflight.py tools/acceptance/v2_mission_retirement.py \
  tools/run-v2-mission-retirement-acceptance.sh \
  tools/tests/test_v2_acceptance_runner.py
git commit -m "feat: add staged V2 acceptance runner"
```

[Return to the main
plan](2026-09-23-v2-mission-retirement-acceptance-runbook.md).
