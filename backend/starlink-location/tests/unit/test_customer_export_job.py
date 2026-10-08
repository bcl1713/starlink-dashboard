"""Blocking exports must not block the loop or outlive their request owner."""

import asyncio
import importlib
import io
import threading

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
