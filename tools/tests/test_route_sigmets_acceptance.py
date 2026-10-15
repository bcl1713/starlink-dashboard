"""Acceptance must not turn missing browser or surviving runtime into PASS."""

import importlib.util
import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def runner():
    spec = importlib.util.spec_from_file_location(
        "route_sigmet_acceptance", ROOT / "tools/acceptance/aviation-weather/runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_attention_fixture_uses_fresh_bulletin_series(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "sigmet_fixtures",
        ROOT / "tools/acceptance/aviation-weather/generate_fixtures.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(tmp_path, now=1792060000000)
    capture = json.loads((tmp_path / "attention-sigmets.json").read_text())
    series = {feature["properties"]["seriesId"] for feature in capture["features"]}
    assert {"T1", "T2", "T3", "T4", "B1"} <= series
    assert not {"R1", "R2", "R3", "R4"} & series


def proof():
    return {
        "encounter": {
            key: True
            for key in (
                "altitude_free",
                "time_boundaries",
                "plan_edit_ack_preserved",
                "selected_only_unknown",
                "partial_evidence",
                "two_screen_sync",
                "responsive_details",
                "no_altitude_filter",
                "overlap_screenshots",
                "no_overlap_screenshots",
                "unknown_screenshots",
            )
        },
        "browser": {"passed": 2, "failed": 0, "skipped": 0},
        "route": {
            "elapsed_save_to_display_ms": [10, 7999],
            "assertions_complete": True,
        },
        "real_source": {"replayed": True},
        "attention": {
            key: True
            for key in [
                "quiet_overview",
                "manual_selection",
                "shared_acknowledgement",
                "configuration_relevance",
                "screenshots_complete",
            ]
        },
        "cleanup": {
            "containers": [],
            "networks": [],
            "volumes": [],
            "processes": [],
            "ports_free": True,
            "source_absent": True,
            "errors": [],
        },
    }


@pytest.mark.parametrize(
    "missing",
    [
        "quiet_overview",
        "manual_selection",
        "shared_acknowledgement",
        "configuration_relevance",
        "screenshots_complete",
    ],
)
def test_missing_attention_proof_prevents_pass(missing):
    evidence = proof()
    evidence["attention"][missing] = False
    with pytest.raises(ValueError):
        runner().require_pass(evidence)


@pytest.mark.parametrize("missing", ["browser", "route", "real_source", "cleanup"])
def test_propagation_and_cleanup_evidence_required(missing):
    evidence = proof()
    del evidence[missing]
    with pytest.raises(ValueError):
        runner().require_pass(evidence)


@pytest.mark.parametrize("kind", ["containers", "networks", "volumes", "processes"])
def test_surviving_resource_prevents_pass(kind):
    evidence = proof()
    evidence["cleanup"][kind] = ["owned-survivor"]
    with pytest.raises(ValueError):
        runner().require_pass(evidence)


@pytest.mark.parametrize(
    "change", ["slow", "skipped", "no-assertions", "port", "errors"]
)
def test_incomplete_or_late_browser_evidence_cannot_pass(change):
    evidence = proof()
    if change == "slow":
        evidence["route"]["elapsed_save_to_display_ms"] = [8001]
    elif change == "skipped":
        evidence["browser"]["skipped"] = 1
    elif change == "no-assertions":
        evidence["route"]["assertions_complete"] = False
    elif change == "port":
        evidence["cleanup"]["ports_free"] = False
    else:
        evidence["cleanup"]["errors"] = ["down failed"]
    with pytest.raises(ValueError):
        runner().require_pass(evidence)


def test_complete_evidence_passes():
    runner().require_pass(proof())


def test_candidate_browser_sources_require_same_lock(tmp_path):
    candidate, installed = tmp_path / "candidate", tmp_path / "installed"
    for directory in (candidate, installed):
        (directory / "tests/e2e").mkdir(parents=True)
        (directory / "package-lock.json").write_text("locked")
    (installed / "node_modules").mkdir()
    (candidate / "tests/e2e/route-sigmets-production.spec.ts").write_text("candidate")
    (installed / "tests/e2e/route-sigmets-production.spec.ts").write_text("dirty")
    evidence = runner().bind_browser_source(candidate, installed)
    assert (
        evidence["files"]["tests/e2e/route-sigmets-production.spec.ts"]
        == "dda18a0e21ae47c53b4309434cbc02ae8bf764fa83a6defbb719431242722aa7"
    )
    assert (candidate / "node_modules").resolve() == installed / "node_modules"
    (installed / "package-lock.json").write_text("other")
    with pytest.raises(ValueError, match="candidate lock"):
        runner().bind_browser_source(candidate, installed)


def test_unique_projects_and_reserved_ports(tmp_path):
    module = runner()
    a = module.Runner(ROOT, "a" * 40, Path(sys.executable), output=tmp_path / "a")
    b = module.Runner(ROOT, "a" * 40, Path(sys.executable), output=tmp_path / "b")
    try:
        assert a.project != b.project
        assert set(a.ports).isdisjoint(b.ports)
        for port in (*a.ports, *b.ports):
            with socket.socket() as sock, pytest.raises(OSError):
                sock.bind(("127.0.0.1", port))
        owner = json.loads((a.output / "runtime-owner.json").read_text())
        assert owner["sha"] == "a" * 40
        assert owner["docker_host"] == os.environ.get("DOCKER_HOST")
    finally:
        a.cleanup()
        b.cleanup()


@pytest.mark.parametrize("phase", ["build", "browser", "timeout"])
def test_failed_build_browser_and_timeout_cleanup_real_process_tree(tmp_path, phase):
    module = runner()
    owner = module.Runner(ROOT, "a" * 40, Path(sys.executable), output=tmp_path / phase)
    try:
        with pytest.raises((RuntimeError, TimeoutError)):
            owner.command(
                [
                    sys.executable,
                    "-c",
                    "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    + (
                        "time.sleep(60)"
                        if phase == "timeout"
                        else "time.sleep(.2); sys.exit(1)"
                    ),
                ],
                seconds=0.3 if phase == "timeout" else 5,
                name=phase,
            )
    finally:
        owner.cleanup()
    cleanup = json.loads((owner.output / "cleanup.json").read_text())
    assert cleanup["processes"] == []
    assert cleanup["ports_free"] is True
    assert not owner.source.exists()
    assert not (owner.output / "PASS.json").exists()


def test_image_archive_is_not_polluted_by_browser_dependency_link(tmp_path):
    candidate, installed = tmp_path / "candidate", tmp_path / "installed"
    for path in (candidate, installed):
        path.mkdir()
        (path / "package-lock.json").write_text("locked")
    (installed / "node_modules").mkdir()
    runner().bind_browser_source(candidate, installed, link=False)
    assert not (candidate / "node_modules").exists()


@pytest.mark.parametrize("source_absent", [False, None])
def test_missing_or_failed_source_cleanup_proof_prevents_pass(source_absent):
    evidence = proof()
    if source_absent is not None:
        evidence["cleanup"]["source_absent"] = source_absent
    else:
        del evidence["cleanup"]["source_absent"]
    with pytest.raises(ValueError, match="cleanup"):
        runner().require_pass(evidence)


def test_source_removal_failure_is_recorded_and_cannot_pass(tmp_path, monkeypatch):
    module = runner()
    owner = module.Runner(
        ROOT, "a" * 40, Path(sys.executable), output=tmp_path / "removal"
    )
    real_remove = module.shutil.rmtree

    def denied(path, **kwargs):
        if kwargs.get("ignore_errors"):
            return
        raise PermissionError("injected source removal denied")

    try:
        monkeypatch.setattr(module.shutil, "rmtree", denied)
        owner.cleanup()
        cleanup = json.loads((owner.output / "cleanup.json").read_text())
        assert owner.source.exists()
        assert cleanup["source_absent"] is False
        assert any(
            "injected source removal denied" in error for error in cleanup["errors"]
        )
        evidence = proof()
        evidence["cleanup"] = cleanup
        with pytest.raises(ValueError, match="cleanup"):
            module.require_pass(evidence)
    finally:
        monkeypatch.setattr(module.shutil, "rmtree", real_remove)
        owner.cleanup()
        assert not owner.source.exists()


@pytest.mark.parametrize(
    ("label", "selection", "count"),
    [
        (
            "aviation",
            ["aviation-weather-production.spec.ts", "route-sigmets-production.spec.ts"],
            5,
        ),
        ("gfs", ["gfs-weather-production.spec.ts"], 1),
    ],
)
def test_shared_browser_config_lists_each_stack_owned_selection(
    tmp_path, label, selection, count
):
    module = runner()
    owner = module.Runner(ROOT, "a" * 40, Path(sys.executable), output=tmp_path / label)
    frontend = ROOT / "frontend/mission-planner"
    owner.env.update(
        WEATHER_ACCEPTANCE_BASE_URL="http://127.0.0.1:43210",
        AVIATION_ACCEPTANCE_BROWSER="/unused/list-only-browser",
    )
    try:
        output = owner.command(
            [
                "node",
                str(frontend / "node_modules/@playwright/test/cli.js"),
                "test",
                "--config",
                "playwright.aviation-acceptance.config.ts",
                *selection,
                "--list",
                "--reporter=line",
            ],
            cwd=frontend,
            seconds=60,
            name="list-" + label,
        )
        assert f"Total: {count} test" in output
        assert ("gfs-weather-production.spec.ts" in output) == (label == "gfs")
        assert ("route-sigmets-production.spec.ts" in output) == (label == "aviation")
    finally:
        owner.cleanup()


@pytest.mark.parametrize(
    "missing",
    [
        "altitude_free",
        "time_boundaries",
        "plan_edit_ack_preserved",
        "selected_only_unknown",
        "partial_evidence",
        "two_screen_sync",
        "responsive_details",
        "no_altitude_filter",
    ],
)
def test_missing_encounter_proof_prevents_pass(missing):
    evidence = proof()
    evidence["encounter"] = {
        key: True
        for key in (
            "altitude_free",
            "time_boundaries",
            "plan_edit_ack_preserved",
            "selected_only_unknown",
            "partial_evidence",
            "two_screen_sync",
            "responsive_details",
            "no_altitude_filter",
            "overlap_screenshots",
            "no_overlap_screenshots",
            "unknown_screenshots",
        )
    }
    evidence["encounter"][missing] = False
    with pytest.raises(ValueError):
        runner().require_pass(evidence)


def test_encounter_fixture_has_independent_bulletin_series(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "sigmet_fixtures",
        ROOT / "tools/acceptance/aviation-weather/generate_fixtures.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(tmp_path, now=1792060000000)
    capture = json.loads((tmp_path / "encounter-sigmets.json").read_text())
    assert {f["properties"]["seriesId"] for f in capture["features"]} == {
        "E1",
        "E2",
        "E3",
        "E4",
    }


@pytest.mark.parametrize(
    "missing", ["overlap_screenshots", "no_overlap_screenshots", "unknown_screenshots"]
)
def test_missing_encounter_state_screenshots_prevent_pass(missing):
    evidence = proof()
    evidence["encounter"].update(
        overlap_screenshots=True, no_overlap_screenshots=True, unknown_screenshots=True
    )
    evidence["encounter"][missing] = False
    with pytest.raises(ValueError, match="encounter"):
        runner().require_pass(evidence)
