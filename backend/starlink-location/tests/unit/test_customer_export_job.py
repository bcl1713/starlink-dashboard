"""Blocking exports must not block the loop or outlive their request owner."""

import asyncio
import importlib
import io
import threading
from hashlib import sha256

import pytest
from starlette.requests import ClientDisconnect

from app.mission.package.customer_artifacts import (
    ExportCancelled,
    MissionPackageDownload,
)


def implementation():
    name = "app.mission.package.export_job"
    assert importlib.util.find_spec(name), "Asynchronous export job contract absent"
    return importlib.import_module(name)


class Request:
    def __init__(self):
        self.disconnected = False

    async def is_disconnected(self):
        return self.disconnected


@pytest.mark.asyncio
async def test_worker_runs_outside_event_loop_and_returns_owned_stream(monkeypatch):
    module = implementation()
    loop_thread = threading.get_ident()
    observed = []
    stream = io.BytesIO(b"zip")

    def build(*args, **kwargs):
        observed.append(threading.get_ident())
        assert not kwargs["cancel"].is_set()
        return MissionPackageDownload(stream, None)

    monkeypatch.setattr(module, "build_mission_package_download", build)
    result = await module.run_mission_package_job(
        Request(), "m", None, None, enabled=False
    )
    assert observed[0] != loop_thread
    assert result.stream is stream and not stream.closed
    stream.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["disconnect", "task-cancel"])
async def test_cancellation_waits_for_worker_cleanup_and_closes_late_stream(
    monkeypatch, mode
):
    module = implementation()
    request, entered, cleaned = Request(), threading.Event(), threading.Event()
    stream = io.BytesIO(b"late zip")

    def build(*args, **kwargs):
        entered.set()
        assert kwargs["cancel"].wait(2)
        cleaned.set()
        return MissionPackageDownload(stream, None)

    monkeypatch.setattr(module, "build_mission_package_download", build)
    task = asyncio.create_task(
        module.run_mission_package_job(request, "m", None, None, enabled=True)
    )
    for _ in range(200):
        if entered.is_set():
            break
        await asyncio.sleep(0.005)
    assert entered.is_set()
    if mode == "disconnect":
        request.disconnected = True
    else:
        task.cancel()
    with pytest.raises(
        ExportCancelled if mode == "disconnect" else asyncio.CancelledError
    ):
        await asyncio.wait_for(task, 3)
    assert cleaned.is_set() and stream.closed


@pytest.mark.asyncio
async def test_response_closes_zip_when_sending_fails():
    module = implementation()
    stream = io.BytesIO(b"zip")
    response = module.OwnedZipResponse(stream, headers={})

    async def send(message):
        raise OSError("Disconnected")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert stream.closed


@pytest.mark.asyncio
async def test_zip_blocks_preserve_bytes():
    payload = b"binary\x00\xff\n" * 24000 + b"last"
    stream = io.BytesIO(payload)
    response = implementation().OwnedZipResponse(stream, headers={})
    blocks = []

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            blocks.append(message["body"])

    async def receive():
        return {"type": "http.disconnect"}

    await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert stream.closed
    assert sha256(b"".join(blocks)).digest() == sha256(payload).digest()
    assert all(len(block) == 65536 for block in blocks[:-1])
    assert 0 < len(blocks[-1]) <= 65536


@pytest.mark.asyncio
async def test_response_closes_zip_on_cancelled_send():
    stream = io.BytesIO(b"content" * 20000)
    response = implementation().OwnedZipResponse(stream, headers={})

    async def send(message):
        if message["type"] == "http.response.body":
            raise asyncio.CancelledError()

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(asyncio.CancelledError):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert stream.closed


def test_ready_assembly_preserves_package_contract():
    import json
    import zipfile
    from app.mission.slide_cache.assembly import assemble_customer_pdf
    from app.mission.package import customer_artifacts
    from app.mission.exporter.customer_filename import customer_brief_filename
    from tests.unit.pdf_resource_fixtures import make_pdf_fragments
    from tests.unit.test_customer_package import data_package

    captured, records = make_pdf_fragments()
    outcome = assemble_customer_pdf(captured, records)
    name = customer_brief_filename(json.loads(captured.metadata_json)["name"])
    path = "exports/mission/" + name
    source = data_package()
    with source:
        result = customer_artifacts._publish_pair(source, outcome.artifacts, None, path)
    with result, zipfile.ZipFile(result) as archive:
        assert set(archive.namelist()) == {
            "mission.json", "manifest.json", "exports/mission/mission-timeline.csv",
            path, customer_artifacts.EVIDENCE_PATH,
        }
        assert archive.testzip() is None
        assert all(i.compress_type == zipfile.ZIP_STORED for i in archive.infolist())
        assert archive.read(path) == outcome.artifacts.pdf
        evidence_bytes = archive.read(customer_artifacts.EVIDENCE_PATH)
        assert evidence_bytes == outcome.artifacts.evidence
        evidence = json.loads(evidence_bytes)
        assert evidence["schemaVersion"] == 2
        assert evidence["render"]["artifactHashes"]["pdfPath"] == sha256(archive.read(path)).hexdigest()
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.0"
        assert manifest["statistics"] == {"mission_export_files": 3, "total_files": 5}
