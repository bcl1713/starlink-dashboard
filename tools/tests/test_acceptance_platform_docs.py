import re
import shlex
import subprocess
import sys
import json
import hashlib
import os
import shutil
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.platform.runner import _parse
from acceptance.platform.evidence import write_artifacts, seal_fingerprint


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DOC = PROJECT_ROOT / "docs/operations/acceptance-platform.md"
EXTERNAL_HOST_DOC = PROJECT_ROOT / "docs/operations/external-host-final-acceptance.md"
V2_DOC = PROJECT_ROOT / "docs/missions/v2-mission-retirement-acceptance.md"
MISSION_INDEX = PROJECT_ROOT / "docs/missions/README.md"
V2_CONTRACT = PROJECT_ROOT / "tools/acceptance/contracts/v2-mission-retirement.toml"

def _bash_block(section: str) -> str:
    text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    return text[text.index(section):].split("```bash", 1)[1].split("```", 1)[0]

def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

def test_checkout_creates_local_ref_required_by_final_wrapper(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    _git(source, "config", "user.email", "fixture@example.org")
    _git(source, "config", "user.name", "Fixture")
    (source / "tools/acceptance/contracts").mkdir(parents=True)
    (source / "tools/acceptance/contracts/v2-mission-retirement.toml").write_text("fixture")
    _git(source, "add", ".")
    _git(source, "commit", "-qm", "fixture")
    _git(source, "branch", "feat/v2-mission-retirement")
    checkout_root = tmp_path / "checkouts"
    checkout_root.mkdir()
    script = _bash_block("## 1. Obtain a fresh")
    script = script.replace("https://github.com/bcl1713/starlink-dashboard.git", str(source))
    result = subprocess.run(["bash", "-e", "-c", script], cwd=tmp_path, text=True,
        capture_output=True, env={**os.environ, "BRANCH": "feat/v2-mission-retirement",
            "REF": "refs/heads/feat/v2-mission-retirement", "CHECKOUT_ROOT": str(checkout_root),
            "CONTRACT": "tools/acceptance/contracts/v2-mission-retirement.toml"})
    assert result.returncode == 0, result.stderr
    checkout = checkout_root / "v2-mission-retirement"
    sha = _git(checkout, "rev-parse", "HEAD")
    assert _git(checkout, "rev-parse", "refs/heads/feat/v2-mission-retirement") == sha
    assert subprocess.run(["git", "-C", str(checkout), "symbolic-ref", "-q", "HEAD"],
        capture_output=True).returncode != 0

def test_final_example_reaches_wrapper_maintenance_only_with_local_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "tools/run-acceptance-platform.sh", repo / "tools")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.email", "fixture@example.org")
    _git(repo, "config", "user.name", "Fixture")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fixture")
    sha = _git(repo, "rev-parse", "HEAD")
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    python = fakebin / "python3"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$MARKER"\nexit 43\n')
    python.chmod(0o755)
    marker = tmp_path / "maintenance-called"
    args = _lane_example("## 8. Run exactly one final lane")
    replacements = {"$SHA": sha, "$REF": "refs/heads/example", "$PROFILE": "profile",
        "$CONTRACT": "contract", "$HEALTH_FINGERPRINT": "health", "$FINAL_EVIDENCE_ROOT": str(tmp_path),
        "$RUNNER_CHECKOUT_ROOT": str(tmp_path), "$FINAL_ATTEMPT_ID": "final-test",
        "$FINAL_TASK_ROOT": str(tmp_path / "task"), "$FINAL_LEDGER_ROOT": str(tmp_path)}
    args = [replacements.get(arg, arg) for arg in args]
    env = {**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}", "MARKER": str(marker)}
    command = [str(repo / "tools/run-acceptance-platform.sh"), *args]
    missing = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
    assert missing.returncode == 2 and not marker.exists(), missing.stderr
    _git(repo, "update-ref", "refs/heads/example", sha)
    reached = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
    assert reached.returncode == 43, reached.stderr
    assert "retention" in marker.read_text()

@pytest.mark.parametrize("tamper", [None, "sha", "ref", "health_fingerprint_sha256", "runner_manifest_sha256"])
def test_static_readback_binds_candidate_envelope(tmp_path: Path, tamper: str | None) -> None:
    sha = "a" * 40
    candidate = tmp_path / "candidates" / sha
    candidate.parent.mkdir()
    runner = json.dumps({"lane": "static", "outcome": "passed", "final_acceptance": False,
        "sha": sha, "ref": "refs/heads/example"}).encode()
    write_artifacts(candidate, {"runner-manifest.json": runner})
    health = tmp_path / "health.json"
    health.write_bytes(b"health fingerprint")
    envelope = {"sha": sha, "ref": "refs/heads/example",
        "health_fingerprint_sha256": hashlib.sha256(health.read_bytes()).hexdigest(),
        "runner_manifest_sha256": hashlib.sha256(runner).hexdigest()}
    if tamper:
        envelope[tamper] = "b" * 40
    seal_fingerprint(candidate, json.dumps(envelope).encode())
    block = _bash_block("## 7. Run the tracked static lane")
    probe = block.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    result = subprocess.run([sys.executable, "-c", probe, str(candidate), sha,
        "refs/heads/example", str(health)], cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "tools")}, capture_output=True, text=True)
    if tamper:
        assert result.returncode != 0, result.stdout
        assert "candidate fingerprint envelope" in result.stderr
    else:
        assert result.returncode == 0, result.stderr

def test_health_and_static_commands_stop_before_stale_readback() -> None:
    for section, boundary in (("## 6. Certify health", "## 7. Run"),
                              ("## 7. Run the tracked static lane", "## 8. Run")):
        text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
        part = text[text.index(section):text.index(boundary)]
        block = part.split("```bash", 1)[1].split("```", 1)[0]
        # Exercise the exact lane command/control flow, replacing only its external runner.
        before_readback = block.split("PYTHONPATH=", 1)[0]
        before_readback = before_readback.replace("./tools/run-acceptance-platform.sh", "false")
        before_readback += "\nprintf 'STALE_READBACK_REACHED\\n'\n"
        result = subprocess.run(["bash", "-c", before_readback], capture_output=True, text=True,
            env={**os.environ, "SHA": "a" * 40, "REF": "refs/heads/example",
                "HOST_STATE": "/nonexistent", "PROFILE": "/nonexistent",
                "CONTRACT": "/nonexistent", "HEALTH_EVIDENCE_ROOT": "/nonexistent",
                "STATIC_EVIDENCE_ROOT": "/nonexistent"})
        assert result.returncode != 0 or "STALE_READBACK_REACHED" not in result.stdout


def _lane_example(section: str) -> list[str]:
    text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    block = text[text.index(section) :].split("```bash", 1)[1].split("```", 1)[0]
    lines = block.splitlines()
    start = next(
        i for i, line in enumerate(lines) if "./tools/run-acceptance-platform.sh \\" in line
    )
    command = []
    for line in lines[start:]:
        command.append(line)
        if not line.rstrip().endswith("\\"):
            break
    tokens = shlex.split(
        "\n".join(command).replace("\\\n", " ").split(" 2>&1 | tee", 1)[0].split(" || exit", 1)[0]
    )
    return tokens[tokens.index("./tools/run-acceptance-platform.sh") + 1 :]


def test_external_host_lane_examples_parse_with_real_runner_cli() -> None:
    sha = "a" * 40
    ids = []
    for section, lane in (
        ("## 6. Certify health", "health"),
        ("## 7. Run the tracked static lane", "static"),
        ("## 8. Run exactly one final lane", "final"),
    ):
        args = _lane_example(section)
        text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
        if lane != "final":
            identity = f"${lane.upper()}_ATTEMPT_ID"
            assert args[args.index("--acceptance-task") + 1] == identity
            assert f'{lane.upper()}_ATTEMPT_ID="{lane}-$SHA-' in text
        if lane == "final":
            wrapper_only = {"--state-root", "--policy", "--checkout-root"}
            args = [
                item
                for index, item in enumerate(args)
                if item not in wrapper_only
                and (index == 0 or args[index - 1] not in wrapper_only)
            ]
        substitutions = {
            "$SHA": sha,
            "$REF": "refs/heads/example",
            "$PROFILE": "/srv/task/profiles/approved.toml",
            "$CONTRACT": str(V2_CONTRACT),
            "$HEALTH_EVIDENCE_ROOT": "/srv/task/evidence/health",
            "$STATIC_EVIDENCE_ROOT": "/srv/task/evidence/static",
            "$FINAL_EVIDENCE_ROOT": "/srv/task/evidence/final",
            "$HEALTH_TASK_ROOT": "/srv/task/tasks/health",
            "$STATIC_TASK_ROOT": "/srv/task/tasks/static",
            "$FINAL_TASK_ROOT": "/srv/task/tasks/final",
            "$FINAL_LEDGER_ROOT": "/srv/task/ledgers/final",
            "$HEALTH_FINGERPRINT": "/srv/task/evidence/health/" + sha + "/fingerprint.json",
            "$HEALTH_ATTEMPT_ID": "health-" + sha,
            "$STATIC_ATTEMPT_ID": "static-" + sha,
            "$FINAL_ATTEMPT_ID": "final-" + sha,
        }
        args = [substitutions.get(arg, arg) for arg in args]
        parsed = _parse(args)
        assert parsed.lane.value == lane
        assert parsed.sha == sha
        assert parsed.ref == "refs/heads/example"
        assert parsed.contract_path == V2_CONTRACT
        assert parsed.fingerprint == Path(substitutions["$HEALTH_FINGERPRINT"])
        ids.append(parsed.task_id)
    assert len(set(ids)) == len(ids)


def test_external_host_preflights_task_owned_python_and_writable_roots() -> None:
    text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    before_static = text[: text.index("## 5. Run static")]
    for required in (
        "uv venv",
        "uv pip install",
        "pytest",
        "PyYAML",
        "export PATH=",
        "import pytest, yaml, acceptance.platform.runner",
        "test -w",
        "CHECKOUT_ROOT",
    ):
        assert required in before_static
    assert "CHECKOUT_ROOT=$HOST_STATE/checkouts" not in text


def test_external_host_verifies_static_candidate_authority_separately() -> None:
    text = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    static = text[text.index("## 7. Run the tracked static lane") : text.index("## 8. Run exactly one final lane")]
    assert "STATIC_CANDIDATE_ROOT=$STATIC_EVIDENCE_ROOT/candidates/$SHA" in static
    assert "verify_manifest(candidate)" in static
    assert 'candidate / "runner-manifest.json"' in static
    for claim in ('"lane"', '"outcome"', '"final_acceptance"', '"sha"', '"ref"'):
        assert claim in static


def _relative_markdown_targets(path: Path) -> list[Path]:
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    targets = []
    for link in links:
        target = link.split("#", maxsplit=1)[0]
        if target and not "://" in target:
            targets.append((path.parent / target).resolve())
    return targets


def test_platform_doc_defines_administrative_browser_authority() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for required in (
        "absolute executable path",
        "revision",
        "bundle identifier",
        "creation time",
        "platform-owned browser-store path",
        "package/runtime provenance",
        "verified before launch",
    ):
        assert required in lowered
    for prohibited in ("`npm`", "`npx`", "playwright installer", "inherited `path`"):
        assert prohibited in lowered


def test_operations_docs_cover_retention() -> None:
    for document in (PLATFORM_DOC, EXTERNAL_HOST_DOC):
        content = document.read_text(encoding="utf-8")
        assert "--maintenance retention" in content
        assert "never delete GHCR" in content


def test_external_host_report_only_retention_pipe_preserves_failure() -> None:
    content = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    retention_section = content[content.index("## 5a. Retention maintenance") :]
    report_only_block = retention_section.split("```bash", maxsplit=1)[1].split(
        "```", maxsplit=1
    )[0]

    assert "set -o pipefail" in report_only_block
    assert report_only_block.index("set -o pipefail") < report_only_block.index("| tee")


def test_external_host_final_command_supplies_wrapper_maintenance_contract() -> None:
    content = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")
    final_section = content[content.index("## 8. Run exactly one final lane") :]
    final_block = final_section.split("```bash", maxsplit=1)[1].split(
        "```", maxsplit=1
    )[0]

    for required in (
        "--state-root",
        "--policy",
        "--checkout-root",
        "--acceptance-task",
    ):
        assert required in final_block


def test_external_host_bootstraps_frontend_before_health() -> None:
    content = EXTERNAL_HOST_DOC.read_text(encoding="utf-8")

    assert "env CI=1 npm ci --ignore-scripts" in content
    assert content.index("env CI=1 npm ci --ignore-scripts") < content.index(
        "## 6. Certify health"
    )


def test_platform_doc_defines_complete_health_fingerprint_validation() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    assert "health fingerprint" in lowered
    assert "environment_blocked" in text
    for required in (
        "docker identity",
        "compose identity",
        "capture timestamp",
        "re-verifies the health card",
        "evidence manifest",
    ):
        assert required in lowered


def test_platform_doc_requires_cleanup_before_sealed_public_authority() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")

    staged = text.index("Stage evidence privately")
    cleaned = text.index("Clean task-owned resources and verify cleanup")
    reverified = text.index("Re-verify staged evidence and checksums after cleanup")
    published = text.index("Seal and atomically publish final authority")
    assert staged < cleaned < reverified < published
    assert "discoverable final authority" in text.lower()


def test_platform_doc_defines_restrictive_candidate_provenance() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for required in (
        "candidate sha and ref",
        "observed utc build start/end timestamps",
        "monotonic elapsed duration",
        "lane",
        "profile and contract checksums",
        "health fingerprint",
        "browser identity",
        "journey-adapter checksum",
        "capture start and end timestamps",
        "controls",
        "journey observations",
        "image identity",
        "primary result",
        "cleanup result",
        "maximum evidence claim",
        "0700",
        "0600",
        "sha-qualified root",
    ):
        assert required in lowered


def test_platform_doc_prescribes_ordered_final_browser_recovery_workflow() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    health = (
        "Run `health` and checksum-verify its sealed fingerprint and evidence manifest."
    )
    static = "Run `static` only after that health validation succeeds."
    final = (
        "Issue `final` through one tracked runner process with a 1800-second "
        "monitored budget and durable stdout and stderr capture."
    )
    runner_ownership = (
        "The runner, not a caller, owns the headed Xvfb and loopback CDP browser "
        "resources, its task-owned profile, and pre-journey native display/card metrics."
    )
    diagnostics = (
        "On failure, inspect the runner's sealed diagnostic logs at "
        "`adapter.stdout.log` and `adapter.stderr.log` in the final evidence root."
    )
    recovery = (
        "After an interruption, inspect the final build ledger, inspected image "
        "identities, and task-owned resources."
    )
    authorization = "obtain explicit authorization from a human operator before one recovery attempt."
    cleanup = "Verify runner cleanup after the attempt without deleting volumes."

    for required in (
        health,
        static,
        final,
        runner_ownership,
        diagnostics,
        recovery,
        authorization,
        cleanup,
        "The tracked runner is the only final-browser operational authority.",
        "Callers must not hand-launch a headless browser as final acceptance evidence.",
    ):
        assert required in guide

    assert (
        guide.index(health)
        < guide.index(static)
        < guide.index(final)
        < guide.index(runner_ownership)
        < guide.index(diagnostics)
        < guide.index(recovery)
        < guide.index(authorization)
        < guide.index(cleanup)
    )


def test_platform_doc_defines_bounded_startup_and_interrupt_cleanup() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    assert (
        "fixed 120-second deadline for `docker compose up -d --no-build --wait`"
        in guide
    )
    assert "retains Compose output and classifies startup as failed" in guide
    assert "classifies `SIGINT` and `SIGTERM` as final-run failures" in guide
    assert "drains Compose resources, browser/Xvfb processes and listeners" in guide
    assert "task browser profile, and the generated task root" in guide


def test_platform_doc_defines_content_aware_final_build_supervision() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    for required in (
        "lockfile inputs are unchanged",
        "exact candidate SHA after dependency installation",
        "`--pull`",
        "600 seconds without meaningful BuildKit progress",
        "1800-second total deadline",
        "`build_stalled`",
        "`build_deadline_exceeded`",
        "neither outcome authorizes automatic retry",
        "fresh health/static and operator approval",
        "never reaches no-build startup or final authority",
    ):
        assert required in guide
    assert "--no-cache" not in guide


def test_v2_doc_is_product_only() -> None:
    text = V2_DOC.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "Create New Mission" in text
    assert "v2-activation-route.kml" in text
    assert "starlink-location" in text
    assert "mission-planner" in text
    for excluded in (
        "chrome",
        "chromium",
        "docker",
        "compose",
        "xvfb",
        "cdp",
        "playwright",
        "npm",
        "npx",
        "inherited `path`",
        "timeout",
        "remote-debugging",
    ):
        assert excluded not in lowered


def test_v2_documentation_separates_route_relative_poi_eligibility_from_eta_timing() -> (
    None
):
    text = " ".join(V2_DOC.read_text(encoding="utf-8").split())

    assert "Upcoming POI visibility derives from active-route position" in text
    assert "separate visible body rows for `KAAA` and `KBBB`" in text
    assert "ETA remains anticipated/estimated metadata" in text
    assert (
        "Before planned departure, anticipated ETA is calendar-based. After a missed "
        "planned departure but before actual departure, planned route durations are "
        "re-anchored at now. Once in flight, ETA is estimated from the current route "
        "position; POI visibility remains route-relative."
    ) in text


def test_platform_and_v2_document_links_and_kml_asset_resolve() -> None:
    for document in (PLATFORM_DOC, V2_DOC, MISSION_INDEX):
        for target in _relative_markdown_targets(document):
            assert target.is_file(), f"broken link in {document}: {target}"

    contract_text = V2_CONTRACT.read_text(encoding="utf-8")
    asset_match = re.search(r'^assets = \["([^"]+)"\]$', contract_text, re.MULTILINE)
    assert asset_match is not None
    asset = PROJECT_ROOT / asset_match.group(1)
    assert asset.is_file()
    assert asset.name == "v2-activation-route.kml"
    assert asset.resolve() in _relative_markdown_targets(V2_DOC)


def test_mission_index_links_v2_acceptance_contract() -> None:
    assert V2_DOC.resolve() in _relative_markdown_targets(MISSION_INDEX)
