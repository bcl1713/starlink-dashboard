"""API-owned satellite changes invalidate computation and publication."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission.dependencies import get_poi_manager
from app.mission.planning.inputs import resolve_positions
from app.mission.planning.routes import router
from app.satellites.routes import router as satellite_router

from .test_proposals import prepared as prepared_fixture
from .test_proposals import proposal_api
from .test_reviewed_save import confirmed, review
from .test_store import service as service_fixture

service = service_fixture
prepared = prepared_fixture


@pytest.fixture
def configured_client(service):
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.include_router(satellite_router)
    app.dependency_overrides[get_poi_manager] = lambda: service.store.poi_manager
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("change", ["position", "band", "removed", "malformed"])
def test_api_configuration_change_stales_proposal_and_review(
    prepared, configured_client, monkeypatch, change
):
    from app.mission.planning.errors import PlanningFailure
    from app.mission.planning.models import ApplyProposal

    service, view = prepared
    client = configured_client
    assert (
        client.post(
            "/api/satellites",
            json={"satellite_id": "SOUTH", "transport": "X", "longitude": 20},
        ).status_code
        == 201
    )
    service, view = confirmed((service, view))
    saved = service.save_reviewed(view.mission.id, "card-1", review(view))
    api, view, request = proposal_api((service, saved), monkeypatch)
    proposal = api.generate(view.mission.id, "card-1", request)
    assert resolve_positions(["SOUTH"], service.store.poi_manager)[0].longitude == 20
    if change == "removed":
        assert client.delete("/api/satellites/SOUTH").status_code == 204
    else:
        payload = (
            {"longitude": 40}
            if change == "position"
            else {"transport": "invalid" if change == "malformed" else "Ka"}
        )
        assert client.put("/api/satellites/SOUTH", json=payload).status_code == 200
    if change in {"band", "malformed"}:
        with pytest.raises(ValueError):
            resolve_positions(["SOUTH"], service.store.poi_manager)
    else:
        assert resolve_positions(["SOUTH"], service.store.poi_manager)[0].longitude == (
            40 if change == "position" else 0
        )
    current = service.store.read(view.mission.id)
    assert current.expected_legs[0].leg.review is None
    assert "review_dependencies_changed" in {e.code for e in current.errors}
    assert api.get(view.mission.id, "card-1", proposal.id).state == "stale"
    before = service.store._load(view.mission.id)[1].storage_record()
    with pytest.raises(PlanningFailure):
        api.apply(
            view.mission.id,
            "card-1",
            ApplyProposal(
                expected_revision=view.revision,
                input_identity=request.input_identity,
                proposal_id=proposal.id,
            ),
        )
    assert service.store._load(view.mission.id)[1].storage_record() == before


def test_configured_position_changed_during_solver_discards_result(
    prepared, configured_client, monkeypatch
):
    from app.mission.planning.errors import PlanningFailure

    service, view = prepared
    client = configured_client
    assert (
        client.post(
            "/api/satellites",
            json={"satellite_id": "SOUTH", "transport": "X", "longitude": 20},
        ).status_code
        == 201
    )
    api, view, request = proposal_api((service, view), monkeypatch)
    before = service.store._load(view.mission.id)[1].storage_record()

    def interleaved(fn, args, seconds):
        result = fn(*args)
        assert (
            client.put("/api/satellites/SOUTH", json={"longitude": 40}).status_code
            == 200
        )
        return result

    monkeypatch.setattr("app.mission.planning.proposals.run_bounded", interleaved)
    with pytest.raises(PlanningFailure):
        api.generate(view.mission.id, "card-1", request)
    assert service.store._load(view.mission.id)[1].storage_record() == before


@pytest.mark.parametrize("transport", [" ", "invalid"])
def test_malformed_or_removed_api_satellite_has_no_implicit_position(
    configured_client, service, transport
):
    client = configured_client
    assert (
        client.post(
            "/api/satellites",
            json={
                "satellite_id": "CUSTOM",
                "transport": transport or "X",
                "longitude": -40,
            },
        ).status_code
        == 201
    )
    assert (
        client.put("/api/satellites/CUSTOM", json={"transport": transport}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/satellites",
            json={"satellite_id": "VALID", "transport": "X", "longitude": -42},
        ).status_code
        == 201
    )
    options = service.satellite_options().satellites
    assert not any(s.id == "CUSTOM" for s in options)
    assert next(s for s in options if s.id == "VALID").eligible
    with pytest.raises(ValueError):
        resolve_positions(["CUSTOM"], service.store.poi_manager)
    assert client.delete("/api/satellites/CUSTOM").status_code == 204
    with pytest.raises(ValueError):
        resolve_positions(["CUSTOM"], service.store.poi_manager)


def test_api_position_changed_before_review_commit_does_not_publish(
    prepared, configured_client, monkeypatch
):
    from app.mission.planning import review as review_module
    from app.mission.planning.errors import PlanningFailure

    service, view = confirmed(prepared)
    client = configured_client
    assert (
        client.post(
            "/api/satellites",
            json={"satellite_id": "SOUTH", "transport": "X", "longitude": 20},
        ).status_code
        == 201
    )
    original = review_module.prepare_mission_timeline
    before = service.store._load(view.mission.id)[1].storage_record()

    def interleaved(*args, **kwargs):
        result = original(*args, **kwargs)
        assert (
            client.put("/api/satellites/SOUTH", json={"longitude": 40}).status_code
            == 200
        )
        return result

    monkeypatch.setattr(review_module, "prepare_mission_timeline", interleaved)
    with pytest.raises(PlanningFailure):
        service.save_reviewed(view.mission.id, "card-1", review(view))
    assert service.store._load(view.mission.id)[1].storage_record() == before
    assert service.store.read(view.mission.id).mission.legs == []


@pytest.mark.parametrize("longitude", [None, 200, float("nan")])
def test_invalid_position_has_operator_configuration_guidance(longitude):
    from types import SimpleNamespace

    from app.mission.planning.satellites import satellite_options

    catalog = SimpleNamespace(
        list_all=lambda: [
            SimpleNamespace(satellite_id="BAD", transport="X", longitude=longitude),
            SimpleNamespace(satellite_id="GOOD", transport="X", longitude=0),
        ]
    )
    options = {s.id: s for s in satellite_options(None, catalog)}
    assert options["GOOD"].eligible
    bad = options["BAD"]
    assert not bad.eligible
    assert bad.error.code == "satellite_position_missing"
    assert bad.error.action == "edit_satellite"
    assert (
        bad.error.message
        == "Configure a valid latitude and longitude for this satellite."
    )


def test_duplicate_satellite_has_operator_configuration_guidance():
    from types import SimpleNamespace

    from app.mission.planning.satellites import satellite_options

    poi = SimpleNamespace(
        name="DUP",
        category="satellite",
        mission_id=None,
        route_id=None,
        icon="X",
        latitude=0,
        longitude=1,
    )
    options = satellite_options(
        SimpleNamespace(list_pois=lambda: [poi, poi]),
        SimpleNamespace(list_all=list),
    )
    assert not options[0].eligible
    assert (
        options[0].error.message
        == "Remove duplicate satellite identifiers in satellite configuration."
    )
