"""Fail-closed identity and lifecycle controls for the real PoP acceptance runner."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/acceptance/pop-transitions/run.py"


def implementation():
    assert ENTRY.exists(), "PoP production acceptance runner is missing"
    spec = importlib.util.spec_from_file_location("pop_acceptance", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repository(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Acceptance test"], check=True
    )
    (path / "tracked").write_text("candidate")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "candidate"], check=True)
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


@pytest.mark.parametrize("damage", ["dirty", "mismatch", "short"])
def test_rejects_uncommitted_or_mismatched_candidate(tmp_path, damage):
    value = implementation()
    sha = repository(tmp_path)
    if damage == "dirty":
        (tmp_path / "tracked").write_text("changed")
    elif damage == "mismatch":
        sha = "0" * 40
    else:
        sha = sha[:12]
    with pytest.raises(ValueError, match="clean committed full HEAD"):
        value.validate_candidate(tmp_path, sha)


def test_accepts_exact_clean_candidate(tmp_path):
    value = implementation()
    sha = repository(tmp_path)
    value.validate_candidate(tmp_path, sha)


@pytest.mark.parametrize("damage", ["revision", "image", "missing"])
def test_image_identity_must_match_candidate_and_have_content_id(damage):
    value = implementation()
    identity = {
        "Id": "sha256:" + "a" * 64,
        "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
    }
    if damage == "revision":
        identity["Config"]["Labels"]["org.opencontainers.image.revision"] = "c" * 40
    elif damage == "image":
        identity["Id"] = ""
    else:
        identity["Config"]["Labels"] = {}
    with pytest.raises(ValueError, match="image identity"):
        value.validate_image(identity, "b" * 40)


def test_bounded_command_kills_and_reaps_owned_process(tmp_path):
    value = implementation()
    owner = value.ProductionOwner("briefing-pop-timeout-test", tmp_path)
    with pytest.raises(TimeoutError):
        owner.execute(
            [sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.1
        )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["reaped"] and entry["returncode"] is not None
    with pytest.raises(ProcessLookupError):
        os.kill(entry["pid"], 0)


@pytest.mark.parametrize("boundary", ["browser", "pdf"])
def test_failed_qualification_always_removes_runtime_and_retains_failure(
    tmp_path, monkeypatch, boundary
):
    value = implementation()
    sha = repository(tmp_path / "repo")
    removed = []

    class Owner:
        def __init__(self, project, root):
            self.root = Path(root)
            self.root.mkdir()
            self.project = project
            self.ownership = {"cleanup": {}}
            self.env = {}
            self.cleaning = False

        def signal(self, *_):
            raise InterruptedError()

        def compose(self, *_args, **_kwargs):
            return ""

        def finalize_summary(self, summary):
            removed.append(self.project)
            summary["cleanup"] = {"composeRemoved": True, "childrenReaped": True}

    monkeypatch.setattr(value, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(value, "ProductionOwner", Owner)
    monkeypatch.setattr(value, "build_candidate", lambda *_: {})

    def fail(_owner):
        raise RuntimeError(boundary + " failed")

    with pytest.raises(RuntimeError, match=boundary):
        value.run(sha, tmp_path / "evidence", qualify=fail)
    report = json.loads((tmp_path / "evidence/summary.json").read_text())
    assert not report["checksPassed"] and boundary in report["error"]
    assert report["cleanup"]["composeRemoved"] and len(removed) == 1


def geometry():
    entry = ROOT / "tools/acceptance/pop-transitions/pdf_geometry.py"
    assert entry.exists(), "Independent canonical marker geometry check is missing"
    spec = importlib.util.spec_from_file_location("pop_pdf_geometry", entry)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("shift", [0, 6])
def test_actual_pdf_markers_must_align_with_canonical_utc_window(shift):
    value = geometry()
    forecast = {
        "transitions": [
            {
                "window_start_utc": "2026-10-25T14:55:00Z",
                "window_end_utc": "2026-10-25T15:05:00Z",
            }
        ]
    }
    bounds = ["2026-10-25T14:00:00Z", "2026-10-25T18:00:00Z"]
    scale = 921 / 1240
    box = [
        19.5 + (280 + 960 * 55 / 240) * scale + shift,
        200,
        19.5 + (280 + 960 * 65 / 240) * scale + shift,
        216.34,
    ]
    if shift:
        with pytest.raises(ValueError, match="canonical UTC"):
            value.verify_markers([box], forecast, bounds)
    else:
        assert value.verify_markers([box], forecast, bounds)[0]["matched"]
