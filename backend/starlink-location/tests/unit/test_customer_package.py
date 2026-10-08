"""Optional customer documents publish as a pair or preserve the whole legacy ZIP."""

import importlib
import io
import json
import threading
import zipfile
from unittest.mock import Mock

import pytest

from tests.unit.test_customer_document import inputs


def implementation():
    name = "app.mission.package.customer_artifacts"
    assert importlib.util.find_spec(name), "Atomic customer package contract absent"
    return importlib.import_module(name)


def legacy():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mission.json", '{"id":"m"}')
        archive.writestr("exports/mission/mission-slides.pptx", b"legacy presentation")
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "version": "2.0",
                    "file_structure": {
                        "mission_exports": ["exports/mission/mission-slides.pptx"]
                    },
                    "statistics": {"mission_export_files": 1, "total_files": 3},
                }
            ),
        )
    stream.seek(0)
    return stream


def test_disabled_never_captures_or_launches(monkeypatch):
    module = implementation()
    capture = Mock(side_effect=AssertionError("capture while disabled"))
    render = Mock(side_effect=AssertionError("render while disabled"))
    monkeypatch.setattr(module, "capture_export_snapshot", capture)
    monkeypatch.setattr(module, "render_customer_artifacts", render)
    monkeypatch.setattr(module, "export_mission_package", lambda *a, **k: legacy())
    result = module.build_mission_package_download(
        "m", None, None, enabled=False, cancel=threading.Event()
    )
    assert result.briefing is None
    assert result.stream.read().startswith(b"PK")
    result.stream.close()
    capture.assert_not_called()
    render.assert_not_called()


def test_enabled_captures_once_and_publishes_both_manifest_members(monkeypatch):
    module = implementation()
    captured = inputs()[0]
    capture = Mock(return_value=captured)
    render = Mock(
        return_value=module.CustomerBriefingOutcome(
            "included",
            None,
            module.CustomerBriefingArtifacts(b"%PDF-qualified", b'{"qualified":true}'),
        )
    )
    monkeypatch.setattr(module, "capture_export_snapshot", capture)
    monkeypatch.setattr(module, "render_customer_artifacts", render)
    monkeypatch.setattr(
        module, "build_snapshot_legacy_package", lambda snapshot, **kwargs: legacy()
    )
    result = module.build_mission_package_download(
        captured.mission_id, None, None, enabled=True, cancel=threading.Event()
    )
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        paths = manifest["file_structure"]["mission_exports"]
        assert paths == [
            "exports/mission/mission-slides.pptx",
            "exports/mission/mission-customer-briefing-trial.pdf",
            "exports/mission/mission-customer-briefing-evidence.json",
        ]
        assert archive.read(paths[-2]) == b"%PDF-qualified"
        assert archive.read(paths[-1]) == b'{"qualified":true}'
        assert manifest["version"] == "2.0"
        assert manifest["statistics"] == {"mission_export_files": 3, "total_files": 5}
    assert result.briefing.status == "included"
    capture.assert_called_once()
    render.assert_called_once()


@pytest.mark.parametrize("boundary", ["pdf", "evidence", "manifest"])
def test_insertion_failure_keeps_complete_legacy_without_pair_or_references(
    monkeypatch, boundary
):
    module = implementation()
    captured = inputs()[0]
    monkeypatch.setattr(module, "capture_export_snapshot", lambda *a: captured)
    monkeypatch.setattr(
        module, "build_snapshot_legacy_package", lambda *a, **kwargs: legacy()
    )
    monkeypatch.setattr(
        module,
        "render_customer_artifacts",
        lambda *a, **k: module.CustomerBriefingOutcome(
            "included", None, module.CustomerBriefingArtifacts(b"pdf", b"evidence")
        ),
    )
    original = zipfile.ZipFile.writestr

    def fail(archive, name, data, *args, **kwargs):
        filename = getattr(name, "filename", name)
        pair_failure = "customer-briefing" in filename and (
            (boundary == "pdf" and filename.endswith(".pdf"))
            or (boundary == "evidence" and filename.endswith(".json"))
        )
        body = data.decode() if isinstance(data, bytes) else data
        manifest_failure = (
            boundary == "manifest"
            and filename == "manifest.json"
            and "customer-briefing" in body
        )
        if pair_failure or manifest_failure:
            raise OSError("Private publication details")
        return original(archive, name, data, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    result = module.build_mission_package_download(
        captured.mission_id, None, None, enabled=True, cancel=threading.Event()
    )
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.namelist() == [
            "mission.json",
            "exports/mission/mission-slides.pptx",
            "manifest.json",
        ]
        assert "customer-briefing" not in archive.read("manifest.json").decode()
    assert result.briefing.status == "omitted"
    assert result.briefing.warning_code == "publication"


def test_capture_failure_returns_legacy_with_safe_warning(monkeypatch):
    module = implementation()
    monkeypatch.setattr(
        module,
        "capture_export_snapshot",
        Mock(side_effect=ValueError("Sensitive source details")),
    )
    monkeypatch.setattr(module, "export_mission_package", lambda *a, **k: legacy())
    result = module.build_mission_package_download(
        "m", None, None, enabled=True, cancel=threading.Event()
    )
    assert result.briefing.status == "omitted"
    assert result.briefing.warning_code == "snapshot"
    result.stream.close()


def test_busy_slot_uses_legacy_without_optional_capture(monkeypatch):
    module = implementation()
    capture = Mock(side_effect=AssertionError("busy captured"))
    monkeypatch.setattr(module, "capture_export_snapshot", capture)
    monkeypatch.setattr(module, "export_mission_package", lambda *a, **k: legacy())
    assert module.RENDER_SLOT.acquire(blocking=False)
    try:
        result = module.build_mission_package_download(
            "m", None, None, enabled=True, cancel=threading.Event()
        )
        assert result.briefing.warning_code == "busy"
        result.stream.close()
        capture.assert_not_called()
    finally:
        module.RENDER_SLOT.release()


@pytest.mark.parametrize(
    "code",
    [
        "data",
        "page-budget",
        "overflow",
        "runtime",
        "deadline",
        "pdf",
        "evidence",
        "cleanup",
    ],
)
def test_renderer_omission_keeps_every_legacy_document(monkeypatch, code):
    module = implementation()
    captured = inputs()[0]
    monkeypatch.setattr(module, "capture_export_snapshot", lambda *a: captured)
    monkeypatch.setattr(
        module, "build_snapshot_legacy_package", lambda *a, **kwargs: legacy()
    )
    monkeypatch.setattr(
        module,
        "render_customer_artifacts",
        lambda *a, **k: module.CustomerBriefingOutcome("omitted", code, None),
    )
    result = module.build_mission_package_download(
        captured.mission_id, None, None, enabled=True, cancel=threading.Event()
    )
    assert result.briefing.warning_code == code
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert (
            archive.read("exports/mission/mission-slides.pptx")
            == b"legacy presentation"
        )


def test_default_off_and_environment_override(monkeypatch):
    from app.core.config import ConfigManager
    from app.models.config import SimulationConfig

    config = SimulationConfig()
    assert hasattr(config, "exports"), "Export configuration absent"
    assert config.exports.customer_briefing_enabled is False
    monkeypatch.setenv("STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED", "true")
    assert ConfigManager.load_from_dict({}).exports.customer_briefing_enabled is True


def test_cancellation_between_legacy_stages_stops_before_route_work(monkeypatch):
    from app.mission.exporter.export_cancel import ExportCancelled
    from app.mission.package import __main__ as builder

    cancel = threading.Event()
    captured = inputs()[0]
    from app.mission.exporter.snapshot_views import SnapshotViews

    monkeypatch.setattr(
        builder, "load_mission_v2", lambda *a: SnapshotViews(captured).mission()
    )
    monkeypatch.setattr(
        builder, "_add_mission_metadata_to_zip", lambda *a: cancel.set()
    )
    monkeypatch.setattr(
        builder,
        "_add_route_kmls_to_zip",
        Mock(side_effect=AssertionError("work after cancellation")),
    )
    with pytest.raises(ExportCancelled):
        builder.export_mission_package(captured.mission_id, None, None, cancel=cancel)
