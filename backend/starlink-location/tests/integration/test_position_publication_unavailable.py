"""Unavailable immutable position values must remain valid JSON."""

import httpx
import pytest

from app.core.metrics.frame_builder import FrameInputs, prepare_unavailable_frame
from tests.integration.test_metrics_http_contracts import publication_http
from tests.unit.test_metrics_frames import prepared

__all__ = ["publication_http"]


@pytest.mark.parametrize(
    "publication", ["uninitialized", "pending", "failed", "unavailable"]
)
async def test_position_table_encodes_unavailable_values(publication_http, publication):
    app, store, _ = publication_http
    if publication != "uninitialized":
        store.publish(store.read(), prepared(store, 7))
    if publication == "pending":
        store.invalidate("source changed")
    elif publication == "failed":
        store.fail(store.read(), "preparation failed")
    elif publication == "unavailable":
        head = store.invalidate("disconnect")
        assert store.publish(head, prepare_unavailable_frame(FrameInputs(head)))
    head = store.read()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/position-table")
    assert response.status_code == 200
    assert response.json()["rows"] == [["starlink-dish", None, None, None]]
    assert response.json()["columns"] == [
        {"text": "aircraft_id", "type": "string"},
        {"text": "latitude", "type": "number"},
        {"text": "longitude", "type": "number"},
        {"text": "altitude", "type": "number"},
    ]
    assert store.read() is head


@pytest.mark.parametrize("unavailable", [float("nan"), float("inf"), float("-inf")])
async def test_position_table_preserves_available_dimensions(
    publication_http, unavailable
):
    from dataclasses import replace

    app, store, _ = publication_http
    frame = prepared(store, 7)
    families = list(frame.families)
    altitude = next(
        i
        for i, definition in enumerate(store.schema)
        if definition.name == "starlink_dish_altitude_feet"
    )
    families[altitude] = (((), unavailable),)
    assert store.publish(store.read(), replace(frame, families=tuple(families)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/position-table")
    assert response.status_code == 200
    assert response.json()["rows"] == [["starlink-dish", 7, 7, None]]
