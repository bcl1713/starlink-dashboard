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


def test_surviving_resource_cannot_leave_a_passing_summary(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    owner.execute = lambda command, **kwargs: (
        "owned-container\n" if "ps" in command else ""
    )
    summary = {"checksPassed": True}
    with pytest.raises(RuntimeError, match="remain"):
        owner.finalize_summary(summary)
    assert summary["checksPassed"] is False
    assert summary["cleanup"]["remaining"]["containers"] == "owned-container"
    assert "remain" in summary["cleanupError"]


def controls():
    entry = ROOT / "tools/acceptance/customer-briefing/production_controls.py"
    assert entry.exists(), "production ZIP inspection is missing"
    spec = importlib.util.spec_from_file_location("briefing_controls", entry)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("damage", ["htmlPath", "page-5", "different", "only-two"])
def test_cold_preview_proof_requires_three_complete_identical_artifact_sets(damage):
    complete = {"htmlPath": "a" * 64} | {
        f"page-{page}": str(page) * 64 for page in range(1, 6)
    }
    previews = [dict(complete) for _ in range(3)]
    if damage == "only-two":
        previews.pop()
    elif damage == "different":
        previews[2]["page-3"] = "b" * 64
    else:
        for preview in previews:
            preview.pop(damage)
    with pytest.raises(ValueError, match="cold production"):
        controls().verify_cold_previews(previews, 5)


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
    if damage in {"manifest", "manifest-consistent"}:
        manifest["file_structure"]["mission_exports"].remove(pdf_path)
        if damage == "manifest-consistent":
            manifest["statistics"]["total_files"] -= 1
            manifest["statistics"]["mission_export_files"] -= 1
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
    "damage",
    [
        "half-pair",
        "hash",
        "manifest",
        "manifest-consistent",
        "statistics",
        "diagnostics",
    ],
)
def test_download_inspection_rejects_partial_or_unqualified_pair(damage):
    with pytest.raises(ValueError):
        controls().inspect_download(
            download_fixture(damage),
            {"X-Customer-Briefing-Status": "included"},
            "included",
        )


def fault_module():
    entry = ROOT / "tools/acceptance/customer-briefing/production_fault_server.py"
    assert entry.exists(), "isolated failure boundary controls are missing"
    spec = importlib.util.spec_from_file_location("briefing_faults", entry)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("fault", ["pdf", "evidence"])
def test_decode_fault_changes_only_real_render_proof_boundary(fault):
    value = fault_module()
    untouched = {"schemaVersion": 2, "missionId": "m", "legs": []}
    report = json.loads(download_fixture_evidence())
    render = report["render"] | {"schemaVersion": 2, "snapshotFingerprint": "a" * 64}
    serialized = json.dumps(render)
    restore = value.install(fault)
    try:
        assert json.loads(json.dumps(untouched)) == untouched
        actual = json.loads(serialized)
        if fault == "pdf":
            assert actual["artifactHashes"]["pdfPath"] == "0" * 64
        else:
            assert actual["snapshotFingerprint"] == "0" * 64
    finally:
        restore()


def download_fixture_evidence():
    with zipfile.ZipFile(io.BytesIO(download_fixture())) as archive:
        return archive.read("exports/mission/mission-customer-briefing-evidence.json")


def test_publication_fault_preserves_ordinary_legacy_zip_writes():
    restore = fault_module().install("publication")
    stream = io.BytesIO()
    try:
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("mission.json", b"real legacy boundary")
            with pytest.raises(OSError):
                archive.writestr(
                    "exports/mission/mission-customer-briefing-evidence.json",
                    b"pair boundary",
                )
    finally:
        restore()
    with zipfile.ZipFile(stream) as archive:
        assert archive.namelist() == ["mission.json"]
        assert archive.read("mission.json") == b"real legacy boundary"


def legacy_fixture(clock, damage=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mission.json", b'{"id":"m"}')
        archive.writestr(
            "exports/mission/timeline.csv",
            f"Mission,M,Total Legs,1,Generated,{clock}\r\nEvent,unchanged\r\n",
        )
        presentation = io.BytesIO()
        with zipfile.ZipFile(presentation, "w") as pptx:
            pptx.writestr(
                "ppt/slides/slide1.xml", b"slide changed" if damage else b"slide"
            )
            pptx.writestr("ppt/media/image1.png", b"real media")
        archive.writestr("exports/mission/slides.pptx", presentation.getvalue())
    return stream.getvalue()


def test_production_legacy_comparison_excludes_only_combined_csv_generation_clock():
    value = controls()
    assert value.compare_legacy(legacy_fixture("first"), legacy_fixture("second"))[
        "matched"
    ]


def test_production_legacy_comparison_rejects_changed_presentation_member():
    with pytest.raises(ValueError, match="Legacy content differs"):
        controls().compare_legacy(
            legacy_fixture("first"), legacy_fixture("second", True)
        )


@pytest.mark.parametrize(
    "case,count", [("two-page", 2), ("three-page", 3), ("five-leg", 5)]
)
def test_named_page_control_rejects_different_actual_page_count(case, count):
    report = {"status": "included", "pageCount": count - 1, "evidence": {}}
    with pytest.raises(ValueError, match="page count"):
        controls().assert_scenario(case, report)


def test_over_budget_control_requires_the_page_budget_boundary():
    with pytest.raises(ValueError, match="page-budget"):
        controls().assert_scenario(
            "over-budget", {"status": "omitted", "warning": "runtime"}
        )


def test_rendered_request_cannot_pass_without_observed_owner_evidence():
    with pytest.raises(ValueError, match="observations"):
        controls().assert_observations(
            {"observations": {}}, {"observations": {}}, renders=1
        )


def test_spliced_input_cannot_pass_with_the_original_route_end_time():
    report = {
        "status": "included",
        "evidence": {
            "legs": [
                {
                    "legId": "l",
                    "canonical": {
                        "utcBounds": ["2026-10-25T14:00:00Z", "2026-10-25T18:00:00Z"]
                    },
                }
            ],
            "render": {"maps": {"l": {"status": "primary"}}},
        },
    }
    with pytest.raises(ValueError, match="splice timing"):
        controls().assert_scenario("spliced", report)
