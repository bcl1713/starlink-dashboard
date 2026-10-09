"""Cached customer documents publish atomically with mission data and CSVs."""

import io
import json
import threading
import zipfile
from dataclasses import replace

import pytest

from app.mission.package import customer_artifacts as module
from tests.unit.test_customer_document import inputs


def data_package():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mission.json", '{"id":"m"}')
        archive.writestr("exports/mission/mission-timeline.csv", b"csv")
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "version": "2.0",
                    "file_structure": {
                        "mission_exports": ["exports/mission/mission-timeline.csv"]
                    },
                    "statistics": {"mission_export_files": 1, "total_files": 3},
                }
            ),
        )
    stream.seek(0)
    return stream


def test_disabled_delivers_data_without_waiting_for_pdf(monkeypatch):
    monkeypatch.setattr(
        module,
        "get_prepared_package",
        lambda *a, **k: pytest.fail("PDF wait while disabled"),
    )
    monkeypatch.setattr(
        module, "export_mission_package", lambda *a, **k: data_package()
    )
    result = module.build_mission_package_download(
        "m", None, None, enabled=False, cancel=threading.Event()
    )
    assert result.briefing is None
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.read("exports/mission/mission-timeline.csv") == b"csv"
        assert not any(n.endswith(".pptx") for n in archive.namelist())


def prepared(monkeypatch, outcome, mission_name="27-02"):
    captured = inputs()[0]
    metadata = json.loads(captured.metadata_json)
    metadata["name"] = mission_name
    captured = replace(captured, metadata_json=json.dumps(metadata).encode())
    monkeypatch.setattr(
        module, "get_prepared_package", lambda *a, **k: (captured, outcome)
    )
    monkeypatch.setattr(
        module, "build_snapshot_legacy_package", lambda *a, **k: data_package()
    )


@pytest.mark.parametrize(
    "mission_name, filename",
    [
        ("27-02", "27-02-brief.pdf"),
        ("Mission Alpha", "Mission Alpha-brief.pdf"),
        ("../27/02\\brief", "27_02_brief-brief.pdf"),
        ("", "mission-brief.pdf"),
        ("A" * 300, "A" * 240 + "-brief.pdf"),
        ("🚀" * 100, "🚀" * 60 + "-brief.pdf"),
    ],
)
def test_enabled_publishes_pdf_evidence_and_manifest_as_pair(
    monkeypatch, mission_name, filename
):
    prepared(
        monkeypatch,
        module.CustomerBriefingOutcome(
            "included",
            None,
            module.CustomerBriefingArtifacts(b"%PDF-qualified", b'{"qualified":true}'),
        ),
        mission_name,
    )
    result = module.build_mission_package_download(
        "m", None, None, enabled=True, cancel=threading.Event()
    )
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert archive.read("exports/mission/" + filename) == b"%PDF-qualified"
        assert archive.read(module.EVIDENCE_PATH) == b'{"qualified":true}'
        assert manifest["statistics"] == {"mission_export_files": 3, "total_files": 5}
        assert manifest["file_structure"]["mission_exports"][-2:] == [
            "exports/mission/" + filename,
            module.EVIDENCE_PATH,
        ]
    assert result.briefing.status == "included"


@pytest.mark.parametrize("boundary", ["pdf", "evidence", "manifest"])
def test_insertion_failure_preserves_data_without_partial_pdf(monkeypatch, boundary):
    prepared(
        monkeypatch,
        module.CustomerBriefingOutcome(
            "included", None, module.CustomerBriefingArtifacts(b"pdf", b"evidence")
        ),
    )
    original = zipfile.ZipFile.writestr

    def fail(archive, name, data, *args, **kwargs):
        filename = getattr(name, "filename", name)
        body = data.decode() if isinstance(data, bytes) else data
        if (
            (boundary == "pdf" and filename == "exports/mission/27-02-brief.pdf")
            or (boundary == "evidence" and filename == module.EVIDENCE_PATH)
            or (
                boundary == "manifest"
                and filename == "manifest.json"
                and "customer-briefing" in body
            )
        ):
            raise OSError("Private publication details")
        return original(archive, name, data, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    result = module.build_mission_package_download(
        "m", None, None, enabled=True, cancel=threading.Event()
    )
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.read("exports/mission/mission-timeline.csv") == b"csv"
        assert "customer-briefing" not in archive.read("manifest.json").decode()
    assert result.briefing.warning_code == "publication"


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
def test_pdf_failure_keeps_data_and_csvs(monkeypatch, code):
    prepared(monkeypatch, module.CustomerBriefingOutcome("omitted", code, None))
    result = module.build_mission_package_download(
        "m", None, None, enabled=True, cancel=threading.Event()
    )
    assert result.briefing.warning_code == code
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.read("exports/mission/mission-timeline.csv") == b"csv"


def test_default_on_and_explicit_environment_opt_out(monkeypatch):
    from app.core.config import ConfigManager
    from app.models.config import SimulationConfig

    assert SimulationConfig().exports.customer_briefing_enabled is True
    monkeypatch.setenv("STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED", "false")
    assert ConfigManager.load_from_dict({}).exports.customer_briefing_enabled is False


def test_cache_failure_does_not_prevent_data_delivery(monkeypatch):
    def failed(*a, **k):
        raise OSError("Private cache error")

    monkeypatch.setattr(module, "get_prepared_package", failed)
    monkeypatch.setattr(
        module, "export_mission_package", lambda *a, **k: data_package()
    )
    result = module.build_mission_package_download(
        "m", None, None, enabled=True, cancel=threading.Event()
    )
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.read("exports/mission/mission-timeline.csv") == b"csv"
    assert result.briefing.status == "omitted"
    assert result.briefing.warning_code == "runtime"
