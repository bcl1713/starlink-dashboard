"""Optional customer documents share captured inputs and publish atomically."""

import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from typing import IO

from pypdf.errors import PyPdfError

from app.mission.exporter.export_cancel import ExportCancelled, check_cancelled

from .__main__ import export_mission_package
from .snapshot_export import build_snapshot_legacy_package

WARNING_CODES = frozenset(
    {
        "snapshot",
        "data",
        "page-budget",
        "overflow",
        "runtime",
        "deadline",
        "pdf",
        "evidence",
        "cleanup",
        "publication",
        "busy",
    }
)
EXPORT_ERRORS = (
    sqlite3.Error,
    PyPdfError,
    RuntimeError,
    ValueError,
    OSError,
    KeyError,
    TypeError,
    AttributeError,
    LookupError,
    ImportError,
    EOFError,
    zipfile.BadZipFile,
)
PDF_PATH = "exports/mission/mission-customer-briefing-trial.pdf"
EVIDENCE_PATH = "exports/mission/mission-customer-briefing-evidence.json"


@dataclass(frozen=True)
class CustomerBriefingArtifacts:
    pdf: bytes
    evidence: bytes


@dataclass(frozen=True)
class CustomerBriefingOutcome:
    status: str
    warning_code: str | None
    artifacts: CustomerBriefingArtifacts | None


@dataclass(frozen=True)
class MissionPackageDownload:
    stream: IO[bytes]
    briefing: CustomerBriefingOutcome | None


def get_prepared_package(mission_id, route_manager, poi_manager, *, cancel):
    from app.mission.slide_cache.assembly import assemble_customer_pdf
    from app.mission.slide_cache.prepared_export import await_prepared

    snapshot, records = await_prepared(
        mission_id, route_manager, poi_manager, cancel=cancel
    )
    try:
        outcome = assemble_customer_pdf(snapshot, records, cancel=cancel)
    except ExportCancelled:
        raise
    except EXPORT_ERRORS:
        outcome = CustomerBriefingOutcome("omitted", "runtime", None)
    return snapshot, outcome


def _publish_pair(stream, artifacts, cancel):
    result = io.BytesIO()
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as source, zipfile.ZipFile(result, "w") as target:
            manifest = json.loads(source.read("manifest.json"))
            if manifest["version"] != "2.0" or any(
                name in source.namelist() for name in (PDF_PATH, EVIDENCE_PATH)
            ):
                raise ValueError("Unexpected legacy package structure")
            for entry in source.infolist():
                check_cancelled(cancel)
                if entry.filename != "manifest.json":
                    target.writestr(entry, source.read(entry))
            target.writestr(PDF_PATH, artifacts.pdf)
            check_cancelled(cancel)
            target.writestr(EVIDENCE_PATH, artifacts.evidence)
            manifest["file_structure"]["mission_exports"].extend(
                [PDF_PATH, EVIDENCE_PATH]
            )
            manifest["statistics"]["mission_export_files"] += 2
            manifest["statistics"]["total_files"] += 2
            target.writestr("manifest.json", json.dumps(manifest, indent=2))
        check_cancelled(cancel)
        result.seek(0)
        return result
    except BaseException:
        result.close()
        raise


def build_mission_package_download(
    mission_id, route_manager, poi_manager, *, enabled, cancel
):
    check_cancelled(cancel)
    if not enabled:
        stream = export_mission_package(
            mission_id, route_manager, poi_manager, cancel=cancel
        )
        if cancel.is_set():
            stream.close()
            check_cancelled(cancel)
        return MissionPackageDownload(stream, None)
    stream = None
    try:
        try:
            snapshot, outcome = get_prepared_package(
                mission_id, route_manager, poi_manager, cancel=cancel
            )
        except ExportCancelled:
            raise
        except EXPORT_ERRORS:
            check_cancelled(cancel)
            stream = export_mission_package(
                mission_id, route_manager, poi_manager, cancel=cancel
            )
            check_cancelled(cancel)
            return MissionPackageDownload(
                stream, CustomerBriefingOutcome("omitted", "runtime", None)
            )
        check_cancelled(cancel)
        stream = build_snapshot_legacy_package(snapshot, cancel=cancel)
        check_cancelled(cancel)
        if outcome.status != "included" or outcome.artifacts is None:
            code = (
                outcome.warning_code
                if outcome.warning_code in WARNING_CODES
                else "runtime"
            )
            return MissionPackageDownload(
                stream, CustomerBriefingOutcome("omitted", code, None)
            )
        try:
            paired = _publish_pair(stream, outcome.artifacts, cancel)
        except ExportCancelled:
            raise
        except EXPORT_ERRORS:
            check_cancelled(cancel)
            stream.seek(0)
            return MissionPackageDownload(
                stream, CustomerBriefingOutcome("omitted", "publication", None)
            )
        stream.close()
        stream = paired
        return MissionPackageDownload(
            stream, CustomerBriefingOutcome("included", None, outcome.artifacts)
        )
    except BaseException:
        if stream is not None:
            stream.close()
        raise
