# V2 Mission Retirement Acceptance Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task by task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a repository-owned, staged acceptance runner that makes one
fresh exact-SHA V2 retirement runtime/browser journey repeatable without making
a no-cache Docker build the cost of every development iteration.

**Architecture:** A small Python stdlib package owns input validation, bounded
subprocess execution, Compose image/build reconciliation, artifact manifests,
and phase orchestration. A focused Node CDP program owns headed Xvfb/Chrome
viewport proof and the real deployed journey. A minimal shell entry point is
only the stable operator command. Generated overrides, browser profiles, and
evidence live outside tracked repository content.

**Tech Stack:** Python 3.11 stdlib and pytest; Bash; Node 22 ESM with
`@playwright/test`; Docker Compose; Xvfb; pinned Chrome for Testing; SHA-256.

**Spec:**
`docs/superpowers/specs/2026-09-23-v2-mission-retirement-acceptance-runbook-design.md`

## File Structure

- `tools/acceptance/v2_mission_retirement.py` — CLI, phase sequencing, elapsed
  timing, stop classifications, and single cleanup owner.
- `tools/acceptance/model.py` — immutable validated inputs, phase enum, command
  result, image record, and manifest DTOs; no subprocess or filesystem writes.
- `tools/acceptance/preflight.py` — bounded identity/ref/detached-worktree and
  sanitized topology commands.
- `tools/acceptance/compose.py` — task override rendering, config inspection,
  BuildKit parsing/reconciliation, image inspection, controls, and Compose
  cleanup commands.
- `tools/acceptance/artifacts.py` — mode-restricted artifact root, retained
  command records, manifest generation, checksum generation/verification.
- `tools/acceptance/browser/v2-mission-retirement.mjs` — Xvfb/Chrome/CDP
  ownership, neutral viewport card, deployed V2 journey, and bounded evidence.
- `tools/run-v2-mission-retirement-acceptance.sh` — shell entry point that
  executes the Python CLI without pipeline logic.
- `tools/tests/test_v2_acceptance_model.py` — pure input/phase/command tests.
- `tools/tests/test_v2_acceptance_compose.py` — override, BuildKit, image, and
  fake-Docker subprocess contract tests.
- `tools/tests/test_v2_acceptance_artifacts.py` — manifest/path/mode/checksum
  tests.
- `tools/tests/test_v2_acceptance_runner.py` — orchestration and phase-isolation
  tests with injected fakes; no real Docker or browser.
- `tools/tests/test_v2_acceptance_docs.py` — documentation route and command
  contract tests.
- `docs/missions/v2-mission-retirement-acceptance.md` — concise operator
  runbook; link it from `docs/missions/README.md`.

## Global Constraints

- Preserve production application behavior, deployment defaults, Portainer/GHCR
  configuration, CI publishing, credentials, and live deployment unchanged.
- Validate a full 40-character SHA and named ref; never accept/normalize an
  abbreviated or whitespace-modified identifier.
- Default phase is `full`; supported phases are `preflight`, `static`,
  `browser-card`, `runtime-cached`, and `full`.
- `static` and `browser-card` must not invoke Docker. `runtime-cached` must be
  manifest-classified non-final and must not claim final acceptance.
- Use `uv` with both backend requirement manifests. Record Black/Ruff versions,
  then invoke exactly `black --check app tests`, `ruff check app tests`, and
  `pytest -q` from `backend/starlink-location`.
- Do not run a standalone frontend build immediately before configured
  Playwright, whose web server already runs `npm run build`.
- `full` runs exactly one `COMPOSE_BAKE=false docker compose ... build --no-cache
  --progress=plain` under a >=900-second-capable process owner; it never uses
  `up --build`, concurrent/duplicate builds, or a retry after budget exhaustion.
- On wrapper nonzero/timeout, reconcile each expected service’s `exporting`,
  `naming`, `unpacking`, and final `DONE` log evidence against actual named image
  tags/IDs before classifying failure.
- Start only `starlink-location` and `mission-planner` once with `up -d
  --no-build --wait --wait-timeout 180`; do not start Prometheus/Grafana.
- Use an external task override from tracked `.env.example` only. Replace fixed
  root ports/container names, preserve volumes, and never inspect/copy private
  `.env`.
- Browser uses the exact pinned Chrome path from the spec and a task-owned Xvfb,
  profile, CDP port, and process group. No `Emulation.*` metrics/screen override.
- Require pre- and post-journey 1920×1080 page/visual viewport, DPR 1, and
  decoded 1920×1080 PNG evidence. Mismatch stops product actions.
- Positive journey proof is Nginx frontend → real backend UI only: Create New
  Mission → Detail → Add Leg → tracked KML upload → Activate → Overview. No API
  seeding, request interception, or direct pre-created-state navigation.
- Evidence is outside tracked content, mode 0700/0600, SHA-qualified, checksummed
  and verified after cleanup. Cleanup owns only task browser/display,
  containers/networks, and task temporary files; it preserves volumes.
- Keep each new source/test module below the project cohesion guideline (~300
  lines). Documentation is required in this delivery.

## Review Focus

1. A Docker wrapper timeout after valid exports must inspect both tags and IDs
   and proceed exactly once; a missing export/naming/unpack/DONE signal must
   fail closed. Task 2 owns deterministic parser and fake-Docker tests.
2. A root Compose list merge retaining `5173:80`, fixed `container_name`, or
   private `env_file` invalidates isolation. Task 2 owns resolved-config tests.
3. A neutral display declared as 1920×1080 but an actual browser page at
   1920×937 must stop before the product journey. Task 3 owns the metric/raster
   assertion and neutral-card test.
4. A lower-cost phase must never accidentally invoke a no-cache build or write
   a final-pass manifest. Task 4 owns phase-isolation tests.
5. A cleanup error must not erase a primary failed phase, and retained artifacts
   must remain checksum-valid after cleanup. Tasks 1 and 4 own those tests.

---

### Task 1: Pure model and durable artifact contracts

**Files:**
- Create: `tools/acceptance/__init__.py`
- Create: `tools/acceptance/model.py`
- Create: `tools/acceptance/artifacts.py`
- Create: `tools/tests/test_v2_acceptance_model.py`
- Create: `tools/tests/test_v2_acceptance_artifacts.py`

**Interfaces:**
- Produces `AcceptancePhase`, `AcceptanceInputs`, `PhaseResult`, and
  `RunManifest` used by Tasks 2–4.
- Produces `EvidenceWriter(root: Path, sha: str)` with `record_json`,
  `record_text`, `finalize_manifest`, and `verify_checksums` used by Task 4.
- `AcceptanceInputs.from_mapping(mapping)` rejects missing/invalid values before
  side effects. `full` is the default phase.

- [ ] **Step 1: Write failing model and artifact tests**

```python
def test_inputs_require_full_sha_and_named_ref(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="40-character"):
        AcceptanceInputs.from_mapping({"sha": "0437a0bb", "ref": "feat/x"})


def test_runtime_cached_cannot_be_final_result(tmp_path: Path) -> None:
    result = PhaseResult("runtime-cached", "passed", final_acceptance=True)
    with pytest.raises(ValueError, match="non-final"):
        result.validate()


def test_writer_rejects_paths_outside_sha_root(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, "a" * 40)
    with pytest.raises(ValueError, match="outside"):
        writer.record_text(Path("../escape.txt"), "no")
```

- [ ] **Step 2: Run focused tests to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py`

Expected: FAIL during collection because the acceptance modules do not exist.

- [ ] **Step 3: Implement immutable validation and evidence writer**

```python
class AcceptancePhase(StrEnum):
    PREFLIGHT = "preflight"
    STATIC = "static"
    BROWSER_CARD = "browser-card"
    RUNTIME_CACHED = "runtime-cached"
    FULL = "full"


@dataclass(frozen=True)
class AcceptanceInputs:
    sha: str
    ref: str
    evidence_root: Path
    phase: AcceptancePhase = AcceptancePhase.FULL
```

`EvidenceWriter` creates `<root>/<sha>/<run-id>` with mode `0o700`, writes only
relative allowlisted paths with mode `0o600`, records sorted inventory entries,
writes `manifest.json` and `SHA256SUMS`, and verifies checksums with the artifact
root as the checksum working directory. Its manifest records phase classification
and both primary and cleanup outcomes.

- [ ] **Step 4: Add deterministic artifact boundary tests**

```python
def test_manifest_inventory_is_sorted_and_checksum_valid(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, "b" * 40)
    writer.record_text(Path("z/result.txt"), "z")
    writer.record_text(Path("a/result.txt"), "a")
    manifest = writer.finalize_manifest(RunManifest.minimal("b" * 40, "feat/x"))
    assert [item["path"] for item in manifest["artifacts"]] == [
        "a/result.txt", "z/result.txt"
    ]
    writer.verify_checksums()
```

- [ ] **Step 5: Run focused tests to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_model.py tools/tests/test_v2_acceptance_artifacts.py`

Expected: PASS.

- [ ] **Step 6: Commit the independently testable foundation**

```bash
git add tools/acceptance/__init__.py tools/acceptance/model.py \
  tools/acceptance/artifacts.py tools/tests/test_v2_acceptance_model.py \
  tools/tests/test_v2_acceptance_artifacts.py
git commit -m "feat: add acceptance runbook artifact contracts"
```

### Task 2: Isolated Compose and BuildKit reconciliation

**Files:**
- Create: `tools/acceptance/compose.py`
- Create: `tools/tests/test_v2_acceptance_compose.py`

**Interfaces:**
- Consumes `AcceptanceInputs`, `EvidenceWriter`, and `PhaseResult` from Task 1.
- Produces `render_override(inputs) -> str`,
  `parse_buildkit_log(text, expected_tags) -> list[ImageRecord]`, and
  `reconcile_build(result, log, inspect_tag) -> BuildDisposition`.
- Task 4 invokes `build_full`, `start_no_build`, `runtime_controls`, and
  `cleanup_compose` through this module only.

- [ ] **Step 1: Write failing topology and reconciliation tests**

```python
def test_override_replaces_root_fixed_ports_and_private_env_file() -> None:
    override = render_override(_inputs())
    assert "!override" in override
    assert "5173:80" not in override
    assert "container_name:" not in override
    assert "env_file:" not in override
    assert "STARLINK_MODE=simulation" in override


def test_nonzero_wrapper_with_two_completed_images_is_reconciled() -> None:
    log = _complete_log("accept-backend:sha", "accept-frontend:sha")
    disposition = reconcile_build(
        returncode=124,
        log_text=log,
        expected_tags=("accept-backend:sha", "accept-frontend:sha"),
        inspect_tag=lambda tag: "sha256:" + tag,
    )
    assert disposition.usable is True
    assert disposition.wrapper_anomaly is True


def test_missing_unpack_is_not_reconciled() -> None:
    assert reconcile_build(124, _log_without_unpack(), _tags(), _inspect).usable is False
```

- [ ] **Step 2: Run focused tests to verify RED**

Run: `pytest -q tools/tests/test_v2_acceptance_compose.py`

Expected: FAIL during collection because `tools.acceptance.compose` does not
exist.

- [ ] **Step 3: Implement isolated Compose construction and parser**

Render a task-owned override outside the repository. It starts only
`starlink-location` and `mission-planner`; it replaces inherited ports and
container settings, uses task-owned bind paths/volumes, and supplies non-secret
values derived from `.env.example`. Implement a strict BuildKit parser requiring
for both expected tags: exporting, naming, unpacking, final DONE, and successful
`docker image inspect` ID. Return an explicit disposition instead of retrying.

```python
def compose_build_argv(inputs: AcceptanceInputs, compose_files: list[Path]) -> list[str]:
    return [
        "docker", "compose", "--project-name", inputs.project_name,
        *sum((["--file", str(path)] for path in compose_files), []),
        "build", "--no-cache", "--progress=plain",
        "starlink-location", "mission-planner",
    ]
```

- [ ] **Step 4: Add fake-Docker sequencing test**

```python
def test_genuine_build_failure_never_starts_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_fake_docker(monkeypatch, build_returncode=2)
    result = run_full_build(_inputs(), _writer())
    assert result.status == "failed"
    assert all(" up " not in call for call in calls)
```

- [ ] **Step 5: Run focused tests to verify GREEN**

Run: `pytest -q tools/tests/test_v2_acceptance_compose.py`

Expected: PASS.

- [ ] **Step 6: Commit Compose/build boundary**

```bash
git add tools/acceptance/compose.py tools/tests/test_v2_acceptance_compose.py
git commit -m "feat: add isolated acceptance compose controls"
```

### Task 3: Reusable headed Chrome CDP card and real journey

**Files:**
- Create: `tools/acceptance/browser/v2-mission-retirement.mjs`
- Create: `tools/tests/test_v2_acceptance_browser_contract.py`

**Interfaces:**
- Node script consumes JSON input produced by Task 4: browser executable, Xvfb
  display, CDP port, profile path, frontend origin, evidence directory, and
  `neutral` or `journey` mode.
- Emits one JSON result on stdout and writes bounded browser artifacts only under
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

Use `spawn` with retained stdout/stderr and process groups. Poll child status and
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

### Task 4: Staged runner, phase isolation, and cleanup ownership

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

### Task 5: Operator runbook and documentation contract

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

### Task 6: Exact-head static gates and one full scripted acceptance lane

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

Expected: all checksums valid; no task container/network/listener/process remains;
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
