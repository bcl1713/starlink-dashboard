"""The health diagnostic follows completed exposition, not request start order."""

import asyncio
from threading import Event, Lock

import httpx
import pytest

from app.api import metrics_export
from tests.integration.test_metrics_http_contracts import publication_http
from tests.unit.test_metrics_frames import prepared

__all__ = ["publication_http"]


@pytest.mark.parametrize("finish_order", [(0, 1), (1, 0)])
async def test_overlapping_failed_and_successful_exposition(
    publication_http, monkeypatch, finish_order
):
    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 7))
    head = store.read()
    entered = [Event(), Event()]
    release = [Event(), Event()]
    assignment = Lock()
    requests_started = 0
    prepare = metrics_export._prepare_metrics

    def controlled_prepare(*args):
        nonlocal requests_started
        with assignment:
            index = requests_started
            requests_started += 1
        entered[index].set()
        assert release[index].wait(5)
        if index == 0:
            raise RuntimeError("controlled collector failure")
        return prepare(*args)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        tasks = []
        with monkeypatch.context() as controlled:
            controlled.setattr(metrics_export, "_prepare_metrics", controlled_prepare)
            try:
                for index in range(2):
                    tasks.append(asyncio.create_task(client.get("/metrics")))
                    assert await asyncio.to_thread(entered[index].wait, 3)
                for index in finish_order:
                    release[index].set()
                    response = await asyncio.wait_for(asyncio.shield(tasks[index]), 3)
                    assert response.status_code == (503 if index == 0 else 200)
                    data = (await client.get("/health")).json()
                    assert data["status"] == ("degraded" if index == 0 else "ok")
                    assert data["metrics_publication"]["exposition_error"] == (
                        "RuntimeError" if index == 0 else None
                    )
                    assert data["prometheus_last_scrape"] is not None
            finally:
                for event in release:
                    event.set()
                await asyncio.gather(*tasks, return_exceptions=True)
        assert store.read() is head
        assert (await client.get("/metrics")).status_code == 200
        assert (await client.get("/health")).json()["status"] == "ok"
