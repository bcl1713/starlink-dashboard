"""Production acceptance must own and reap every command, including failed runs."""

import importlib.util
import io
import json
import os
import signal
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/acceptance/customer-briefing/production.py"


def module():
    assert ENTRY.exists(), "production acceptance ownership is missing"
    spec = importlib.util.spec_from_file_location("briefing_production", ENTRY)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_command_ownership_and_output_are_retained_before_cleanup(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    assert json.loads((tmp_path / "ownership.json").read_text())["commands"] == []
    assert (
        owner.execute([sys.executable, "-c", "print('real process')"])
        == "real process\n"
    )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["pid"] > 0 and entry["pgid"] == entry["pid"]
    assert entry["returncode"] == 0 and entry["reaped"]
    with pytest.raises(ProcessLookupError):
        os.kill(entry["pid"], 0)


def test_timeout_reaps_the_owned_process_group(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    with pytest.raises(TimeoutError):
        owner.execute(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1
        )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["reaped"] and entry["returncode"] < 0
    with pytest.raises(ProcessLookupError):
        os.killpg(entry["pgid"], 0)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_marks_cancellation_and_prevents_next_launch(tmp_path, signum):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    with pytest.raises(InterruptedError):
        owner.signal(signum, None)
    with pytest.raises(InterruptedError):
        owner.execute([sys.executable, "-c", "raise Exception('must not run')"])
    assert json.loads((tmp_path / "ownership.json").read_text())["cancelled"]


def test_failed_build_still_removes_owned_runtime_and_temporary_paths(tmp_path):
    value = module()
    owner = value.ProductionOwner("briefing-private-test", tmp_path)
    context = tmp_path / "owned-context"
    context.mkdir()
    owner.ownership["temporaryPaths"].append(str(context))
    with pytest.raises(RuntimeError):
        owner.execute([sys.executable, "-c", "raise SystemExit(2)"])
    # Docker is the external boundary; exercise real ownership/teardown decisions.
    calls = []
    owner.execute = lambda command, **kwargs: calls.append(command) or ""
    cleanup = owner.close()
    assert cleanup["childrenReaped"] and cleanup["composeRemoved"]
    assert not context.exists()
    assert any("down" in command and "--volumes" in command for command in calls)


def test_surviving_resource_blocks_cleanup_success_and_preserves_context(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    context = tmp_path / "owned-context"
    context.mkdir()
    owner.ownership["temporaryPaths"].append(str(context))
    owner.execute = lambda command, **kwargs: (
        "owned-container\n" if "ps" in command else ""
    )
    with pytest.raises(RuntimeError, match="remain"):
        owner.close()
    assert context.exists()
    assert not json.loads((tmp_path / "ownership.json").read_text())["cleanup"][
        "composeRemoved"
    ]


def controls():
    entry = ROOT / "tools/acceptance/customer-briefing/production_controls.py"
    assert entry.exists(), "production ZIP inspection is missing"
    spec = importlib.util.spec_from_file_location("briefing_controls", entry)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def download_fixture(damage=None):
    pdf = b"%PDF-qualified-independent-inspection-follows"
    pdf_path = "exports/mission/mission-customer-briefing-trial.pdf"
    evidence_path = "exports/mission/mission-customer-briefing-evidence.json"
    evidence = {
        "schemaVersion": 2,
        "missionId": "m",
        "snapshotFingerprint": "a" * 64,
        "legs": [
            {
                "legId": "l",
                "mapInputDiagnostics": ["captured reason"],
                "customerRows": [],
            }
        ],
        "pages": [{"page": 1, "legId": "l", "rowIds": []}],
        "render": {
            "status": "success",
            "totalMs": 1234,
            "launchCount": 1,
            "sharedBrowser": True,
            "cleanup": {"success": True},
            "maps": {"l": {"inputDiagnostics": ["captured reason"]}},
            "pdfValidation": {"verified": True, "rows": [], "pageCount": 1},
            "artifactHashes": {"pdfPath": sha256(pdf).hexdigest()},
        },
    }
    entries = {
        "mission.json": b'{"id":"m"}',
        "exports/mission/mission-slides.pptx": b"legacy",
    }
    entries[pdf_path] = pdf
    if damage != "half-pair":
        entries[evidence_path] = json.dumps(evidence).encode()
    manifest = {
        "version": "2.0",
        "mission_id": "m",
        "file_structure": {
            "mission_data": ["mission.json"],
            "mission_exports": list(entries)[1:],
        },
        "statistics": {
            "total_files": len(entries),
            "mission_export_files": len(entries) - 1,
        },
    }
    if damage == "hash":
        entries[pdf_path] += b"changed"
    if damage == "manifest":
        manifest["file_structure"]["mission_exports"].remove(pdf_path)
    if damage == "statistics":
        manifest["statistics"]["total_files"] -= 1
    if damage == "diagnostics":
        evidence["render"]["maps"]["l"]["inputDiagnostics"] = []
        entries[evidence_path] = json.dumps(evidence).encode()
    entries["manifest.json"] = json.dumps(manifest).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


def test_actual_download_pair_manifest_hashes_and_diagnostics_are_consistent():
    report = controls().inspect_download(
        download_fixture(), {"X-Customer-Briefing-Status": "included"}, "included"
    )
    assert report["status"] == "included" and report["pageCount"] == 1


@pytest.mark.parametrize(
    "damage", ["half-pair", "hash", "manifest", "statistics", "diagnostics"]
)
def test_download_inspection_rejects_partial_or_unqualified_pair(damage):
    with pytest.raises(ValueError):
        controls().inspect_download(
            download_fixture(damage),
            {"X-Customer-Briefing-Status": "included"},
            "included",
        )
