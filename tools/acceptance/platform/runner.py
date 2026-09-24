"""Generic, fail-closed acceptance runner for product contracts.

Platform health owns Docker/browser capability certification. Product lanes consume a
sealed health fingerprint and may only declare product static checks, controls, and
a journey adapter. The final lane is the sole final-acceptance authority.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compose import (
    BuildLedger,
    SubprocessComposeExecutor,
    build_final,
    cleanup_compose,
    render_task_override,
    resolve_topology,
    run_controls,
    start_no_build,
)
from .contracts import load_product_contract
from .health import run_platform_health, validate_fingerprint
from .model import (
    BrowserProfile,
    BuildLedgerKey,
    Lane,
    Outcome,
    PlatformProfile,
    ProductContract,
)

_REPOSITORY = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RunnerResult:
    exit_code: int
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RunnerInputs:
    lane: Lane
    sha: str
    ref: str
    profile_path: Path
    contract_path: Path
    fingerprint: Path
    evidence_root: Path
    task_root: Path
    ledger_root: Path
    backend_port: int
    frontend_port: int
    browser_session: str
    deployed_origin: str


@dataclass
class RunnerDependencies:
    """Narrow orchestration seams; adapters never receive these authorities."""

    load_profile: Callable[[Path], PlatformProfile] | None = None
    health: Callable[[PlatformProfile, Path], object] | None = None
    validate_health: Callable[[PlatformProfile, Path], object] | None = None
    static: Callable[[ProductContract], None] | None = None
    final_steps: Callable[[RunnerInputs, PlatformProfile, ProductContract], None] | None = None
    browser_card: Callable[[RunnerInputs], None] | None = None
    cleanup: Callable[[object], None] | None = None


def _parse(argv: Sequence[str]) -> RunnerInputs:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, choices=[lane.value for lane in Lane])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--profile", type=Path, default=_REPOSITORY / "tools/acceptance/platform/profiles/default.toml")
    parser.add_argument("--contract", type=Path, default=_REPOSITORY / "tools/acceptance/contracts/v2-mission-retirement.toml")
    parser.add_argument("--fingerprint", type=Path, default=Path("current"))
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--ledger-root", type=Path)
    parser.add_argument("--backend-port", type=int, default=18000)
    parser.add_argument("--frontend-port", type=int, default=15173)
    parser.add_argument("--browser-session", default="")
    parser.add_argument("--deployed-origin", default="")
    parsed = parser.parse_args(list(argv))
    fingerprint = parsed.fingerprint
    evidence_root = parsed.evidence_root.absolute()
    if fingerprint == Path("current"):
        fingerprint = evidence_root / parsed.sha / "fingerprint.json"
    return RunnerInputs(
        lane=Lane(parsed.lane),
        sha=parsed.sha,
        ref=parsed.ref,
        profile_path=parsed.profile.absolute(),
        contract_path=parsed.contract.absolute(),
        fingerprint=fingerprint.absolute(),
        evidence_root=evidence_root,
        task_root=parsed.task_root.absolute(),
        ledger_root=(parsed.ledger_root or parsed.task_root / "build-ledger").absolute(),
        backend_port=parsed.backend_port,
        frontend_port=parsed.frontend_port,
        browser_session=parsed.browser_session,
        deployed_origin=parsed.deployed_origin,
    )


def _load_profile(path: Path) -> PlatformProfile:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    browser = raw.get("browser")
    if not isinstance(browser, dict):
        raise ValueError("platform profile browser descriptor is required")
    return PlatformProfile(
        version=str(raw["version"]),
        checksum=str(raw["checksum"]),
        browser=BrowserProfile(
            store_root=Path(str(browser["store_root"])),
            executable=Path(str(browser["executable"])),
            version=str(browser["version"]),
            byte_size=int(browser["byte_size"]),
            sha256=str(browser["sha256"]),
        ),
    )


def _run_health(profile: PlatformProfile, root: Path) -> object:
    from .health import PlatformHealthExecutor

    return run_platform_health(profile, root, PlatformHealthExecutor(probe=lambda argv: _probe(argv)))


def _probe(argv: tuple[str, ...]) -> str:
    completed = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=15)
    return completed.stdout.strip() or completed.stderr.strip()


def _run_static(contract: ProductContract) -> None:
    for group in contract.static_groups:
        cwd = _REPOSITORY / group.working_directory
        for command in group.commands:
            words = shlex.split(command)
            if words and words[0] in {"lint", "test"}:
                words = ["npm", "run", *words]
            completed = subprocess.run(words, cwd=cwd, check=False)
            if completed.returncode:
                raise ValueError(f"static group {group.name} failed: {command}")


def _request(control: object, inputs: RunnerInputs) -> int:
    path = getattr(control, "path")
    base = f"http://127.0.0.1:{inputs.backend_port}"
    if path == "/":
        base = f"http://127.0.0.1:{inputs.frontend_port}"
    try:
        with urllib.request.urlopen(base + path, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def _verify_browser_card(inputs: RunnerInputs) -> None:
    if not inputs.browser_session.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("final lane requires a platform-supplied loopback browser session")
    if not inputs.deployed_origin.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("final lane requires a deployed origin")


def _run_journey(inputs: RunnerInputs, contract: ProductContract) -> None:
    asset = _REPOSITORY / contract.assets[0]
    if not asset.is_file():
        raise ValueError("declared journey asset is unavailable")
    evidence = inputs.task_root / "adapter-output"
    evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    completed = subprocess.run(
        [
            "node",
            str(_REPOSITORY / contract.journey_adapter),
            "--session", inputs.browser_session,
            "--origin", inputs.deployed_origin,
            "--kml", str(asset),
            "--evidence-dir", str(evidence),
        ],
        cwd=_REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode:
        raise ValueError(f"product journey adapter failed: {completed.stderr or completed.stdout}")


def _final_steps(
    inputs: RunnerInputs,
    profile: PlatformProfile,
    contract: ProductContract,
    browser_card: Callable[[RunnerInputs], None],
) -> tuple[object, SubprocessComposeExecutor]:
    executor = SubprocessComposeExecutor()
    topology = render_task_override(
        _REPOSITORY,
        contract,
        inputs.task_root,
        f"accept-{inputs.sha[:12]}",
        {"starlink-location": inputs.backend_port, "mission-planner": inputs.frontend_port},
    )
    resolve_topology(topology, contract, executor)
    key = BuildLedgerKey(inputs.sha, profile.checksum, contract.checksum)
    ledger = BuildLedger(inputs.ledger_root)
    built = build_final(topology, profile, contract, key, ledger, executor)
    if not built.usable:
        raise ValueError(f"final build is unusable: {built.reason}")
    start_no_build(topology, contract, key, ledger, executor)
    run_controls(contract.controls, lambda control: _request(control, inputs))
    browser_card(inputs)
    _run_journey(inputs, contract)
    return topology, executor


def _cleanup_default(resource: object) -> None:
    topology, executor = resource
    cleanup_compose(topology, executor)


def _outcome_for(error: Exception) -> Outcome:
    return Outcome.ENVIRONMENT_BLOCKED if isinstance(error, _EnvironmentBlocked) else Outcome.FAILED


class _EnvironmentBlocked(ValueError):
    pass


def _manifest(inputs: RunnerInputs, outcome: Outcome, final: bool, primary: str, cleanup: str, cleanup_failed: bool) -> dict[str, Any]:
    return {
        "lane": inputs.lane.value,
        "outcome": outcome.value,
        "final_acceptance": final,
        "maximum_evidence_claim": "final_acceptance" if final else ("diagnostic_only" if inputs.lane is Lane.DIAGNOSTIC else "non_final"),
        "primary": {"outcome": outcome.value, "detail": primary},
        "cleanup": {"outcome": Outcome.FAILED.value if cleanup_failed else Outcome.PASSED.value, "detail": cleanup},
    }


def _write_manifest(inputs: RunnerInputs, manifest: dict[str, Any]) -> None:
    root = inputs.evidence_root / inputs.sha
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / "runner-manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: Sequence[str], *, dependencies: RunnerDependencies | None = None) -> RunnerResult:
    dependencies = dependencies or RunnerDependencies()
    inputs = _parse(argv)
    load_profile = dependencies.load_profile or _load_profile
    profile = load_profile(inputs.profile_path)
    contract = load_product_contract(inputs.contract_path)
    primary = ""
    cleanup_detail = "not required"
    cleanup_failed = False
    outcome = Outcome.FAILED
    final = False
    resource: object | None = None
    try:
        if inputs.lane is Lane.HEALTH:
            inputs.evidence_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            health = (dependencies.health or _run_health)(profile, inputs.evidence_root / inputs.sha)
            health_outcome = getattr(health, "outcome", Outcome.PASSED)
            outcome = health_outcome if isinstance(health_outcome, Outcome) else Outcome(str(health_outcome))
            primary = getattr(health, "reason", "platform health completed")
        else:
            try:
                (dependencies.validate_health or validate_fingerprint)(profile, inputs.fingerprint)
            except ValueError as error:
                raise _EnvironmentBlocked(str(error)) from error
            (dependencies.static or _run_static)(contract)
            if inputs.lane is Lane.DIAGNOSTIC:
                outcome, primary = Outcome.DIAGNOSTIC_ONLY, "static contract diagnostics completed"
            elif inputs.lane is Lane.STATIC:
                outcome, primary = Outcome.PASSED, "static contract checks completed"
            else:
                browser_card = dependencies.browser_card or _verify_browser_card
                if dependencies.final_steps is None:
                    resource = _final_steps(inputs, profile, contract, browser_card)
                else:
                    browser_card(inputs)
                    resource = dependencies.final_steps(inputs, profile, contract)
                outcome, final, primary = Outcome.PASSED, True, "final product contract completed"
    except Exception as error:
        outcome, primary, final = _outcome_for(error), str(error), False
    finally:
        if inputs.lane is Lane.FINAL:
            try:
                if dependencies.cleanup is not None:
                    dependencies.cleanup(resource)
                elif resource is not None:
                    _cleanup_default(resource)
                cleanup_detail = "final lane cleanup completed"
            except Exception as error:
                cleanup_failed, cleanup_detail = True, str(error)
    manifest = _manifest(inputs, outcome, final, primary, cleanup_detail, cleanup_failed)
    _write_manifest(inputs, manifest)
    exit_code = 0 if outcome in {Outcome.PASSED, Outcome.DIAGNOSTIC_ONLY} and not cleanup_failed else (2 if outcome is Outcome.ENVIRONMENT_BLOCKED else 1)
    return RunnerResult(exit_code, manifest)


def main(argv: Sequence[str] | None = None, *, dependencies: RunnerDependencies | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, dependencies=dependencies).exit_code


if __name__ == "__main__":
    raise SystemExit(main())
