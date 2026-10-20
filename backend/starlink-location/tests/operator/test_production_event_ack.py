"""A supported source writer cannot race a real modeled acknowledgment."""

import pytest


@pytest.mark.parametrize("writer", ["route", "catalog", "leg", "lifecycle"])
def test_real_writer_between_ack_capture_and_commit_is_rejected(
    api, production, clock, monkeypatch, writer
):
    from app.mission import storage
    from tests.operator.api_helpers import BASE, headers

    adapter, publication, state, _config, routes, leg, path = production
    runtime = api.app.state.operator_runtime
    runtime.event_source_adapter, runtime.event_publication = adapter, publication
    snapshot = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    event = next(
        e
        for e in snapshot["events"]
        if e["kind"] == "restriction" and e["transport"] == "X"
    )
    capture = adapter.capture

    def raced(mission_id, *, as_of):
        captured = capture(mission_id, as_of=as_of)
        if writer == "route":
            route = routes.get_route(leg.route_id).model_copy(deep=True)
            route.points[-1].longitude += 1
            routes.add_route(leg.route_id, route)
        elif writer == "catalog":
            import json

            content = json.loads(path.read_text())
            content["sites"][0]["longitude"] += 1
            path.write_text(json.dumps(content))
        elif writer == "leg":
            mission = storage.load_mission_v2(mission_id)
            mission.legs[0].transports.starshield_enabled = False
            storage.save_mission_v2(mission)
        else:
            state["lifecycle"] = "another-run"
        return captured

    monkeypatch.setattr(adapter, "capture", raced)
    response = api.post(
        BASE + "/events/acknowledge",
        headers=headers(api),
        json={
            "schema_version": 1,
            "occurrence_id": event["notification"]["generation"],
            "severity_generation": event["notification"]["severity_generation"],
            "snapshot_token": snapshot["snapshot_token"],
        },
    )
    assert response.status_code == 409, response.text
    with runtime.service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            0,
        )
