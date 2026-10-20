"""Preview overrides retain canonical policy context and independent X fallback."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import routes_v2
from app.mission.models import Mission
from app.mission.planning.inputs import draft_to_mission_leg
from app.mission.timeline_preparation import prepare_mission_timeline
from app.services.pop.models import PopCatalog, PopSite
from tests.planning.test_policy import START, scenario


@pytest.fixture
def canonical_preview(monkeypatch):
    from app.satellites import catalog

    inputs, draft, context, _, manager, _, _ = scenario(
        monkeypatch,
        seconds=1200,
        ka_outages=[{"id": "manual-ka", "start_time": START, "duration_seconds": 1200}],
    )
    monkeypatch.setattr(catalog, "_catalog", catalog.get_satellite_catalog())
    sites = PopCatalog(
        sites=tuple(
            PopSite(
                id=name,
                city=name,
                country="US",
                latitude=lat,
                longitude=0,
                source="test",
                coordinate_source="test",
            )
            for name, lat in (("south", 10), ("north", 10.01))
        ),
        fingerprint="preview-sites",
    )
    monkeypatch.setattr(
        "app.services.pop.catalog.load_catalog", lambda *args, **kwargs: sites
    )
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="canonical")
    mission = Mission(id="preview", name="Captured policy", legs=[leg])
    original = mission.model_dump_json()
    baseline = prepare_mission_timeline(leg, manager).timeline
    active = [i for i in baseline.call_continuity.intervals if i.transition_ids]
    assert active and all(i.classification == "x_fallback" for i in active)
    assert baseline.call_continuity.planned_communications_outage_seconds == 0
    monkeypatch.setattr(routes_v2, "load_mission_v2", lambda _: mission)
    app = FastAPI()
    app.include_router(routes_v2.router)
    app.dependency_overrides[routes_v2.get_route_manager] = lambda: manager
    app.dependency_overrides[routes_v2.get_poi_manager] = lambda: None
    with TestClient(app) as client:
        yield client, leg, baseline
    assert mission.model_dump_json() == original


@pytest.mark.parametrize("request_kind", ["partial", "legacy", "canonical"])
def test_preview_retains_saved_policy_and_unchanged_fallback(
    canonical_preview, request_kind
):
    client, leg, baseline = canonical_preview
    transports = leg.transports.model_dump(mode="json")
    if request_kind == "partial":
        transports = {"starshield_enabled": True}
    elif request_kind == "legacy":
        for key in ("planning_policy", "planning_inputs", "evaluation_context"):
            transports.pop(key)
    response = client.post(
        "/api/v2/missions/preview/legs/canonical/timeline/preview",
        json={"transports": transports},
    )
    assert response.status_code == 200, response.text
    actual = response.json()
    assert actual["call_continuity"] == baseline.call_continuity.model_dump(mode="json")
    assert actual["segments"] == baseline.model_dump(mode="json")["segments"]


def test_changed_legacy_constraint_cannot_reuse_stale_canonical_context(
    canonical_preview,
):
    client, _, _ = canonical_preview
    response = client.post(
        "/api/v2/missions/preview/legs/canonical/timeline/preview",
        json={
            "transports": {
                "initial_x_satellite_id": "SOUTH",
                "ka_outages": [
                    {
                        "id": "manual-ka",
                        "start_time": START.isoformat(),
                        "duration_seconds": 600,
                    }
                ],
            }
        },
    )
    assert response.status_code >= 400
    assert "rebuild evaluation context" in response.text


def test_explicit_null_context_is_not_restored_from_saved_configuration(
    canonical_preview,
):
    client, _, _ = canonical_preview
    response = client.post(
        "/api/v2/missions/preview/legs/canonical/timeline/preview",
        json={
            "transports": {
                "initial_x_satellite_id": "SOUTH",
                "evaluation_context": None,
            }
        },
    )
    assert response.status_code >= 400
    assert "requires persisted inputs and evaluation context" in response.text


@pytest.mark.parametrize("field", ["evaluation_context", "planning_inputs"])
def test_explicit_policy_clear_can_select_legacy_preview(canonical_preview, field):
    client, _, _ = canonical_preview
    response = client.post(
        "/api/v2/missions/preview/legs/canonical/timeline/preview",
        json={"transports": {"planning_policy": None, field: None}},
    )
    assert response.status_code == 200, response.text
