import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.orbital_catalog import router
from app.services.orbital_catalog import OrbitalCatalogService


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(router)
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(503)

    service = OrbitalCatalogService(
        tmp_path, httpx.AsyncClient(transport=httpx.MockTransport(provider))
    )
    app.state.orbital_catalog = service
    with TestClient(app) as client:
        yield client, calls
        client.portal.call(service.aclose)


def test_lease_scoped_catalog_status_has_no_demand(client):
    http, calls = client
    assert http.get("/api/orbital/status").json()["active_viewers"] == 0
    assert (
        http.get("/api/orbital/catalog", params={"viewer_id": "test"}).status_code
        == 409
    )
    assert calls == []
    assert http.put("/api/orbital/viewers/test").status_code == 200
    envelope = http.get("/api/orbital/catalog", params={"viewer_id": "test"}).json()
    assert envelope["objects"] == []
    assert envelope["suspended"] is True
    assert len(calls) == 1
    assert http.delete("/api/orbital/viewers/test").status_code == 204
    assert http.delete("/api/orbital/viewers/test").status_code == 204
    assert http.post("/api/orbital/provider/resume").status_code == 200
    assert len(calls) == 1


def test_lease_capacity_and_invalid_viewer(client):
    http, _ = client
    for i in range(128):
        assert http.put(f"/api/orbital/viewers/{i}").status_code == 200
    assert http.put("/api/orbital/viewers/overflow").status_code == 429
    assert http.put("/api/orbital/viewers/" + "a" * 129).status_code == 422
