"""Own blocking export work and ZIP responses through request cancellation."""

import asyncio
import functools
import threading

from fastapi.responses import StreamingResponse

from app.mission.exporter.export_cancel import ExportCancelled

from .customer_artifacts import build_mission_package_download


async def _discard_worker_result(worker):
    # Repeated task cancellation must not abandon an already running thread.
    while not worker.done():
        try:
            await asyncio.gather(asyncio.shield(worker), return_exceptions=True)
        except asyncio.CancelledError:
            continue
    if worker.cancelled() or worker.exception() is not None:
        return
    worker.result().stream.close()


async def run_mission_package_job(
    request, mission_id, route_manager, poi_manager, *, enabled
):
    cancel = threading.Event()
    worker = asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(
            build_mission_package_download,
            mission_id,
            route_manager,
            poi_manager,
            enabled=enabled,
            cancel=cancel,
        ),
    )
    try:
        while not worker.done():
            if await request.is_disconnected():
                cancel.set()
                await _discard_worker_result(worker)
                raise ExportCancelled("Export cancelled")
            await asyncio.wait({worker}, timeout=0.05)
        if await request.is_disconnected():
            cancel.set()
            await _discard_worker_result(worker)
            raise ExportCancelled("Export cancelled")
        return worker.result()
    except BaseException:
        cancel.set()
        await _discard_worker_result(worker)
        raise


class OwnedZipResponse(StreamingResponse):
    def __init__(self, stream, *, headers):
        self.owned_stream = stream
        super().__init__(stream, media_type="application/zip", headers=headers)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.owned_stream.close()
