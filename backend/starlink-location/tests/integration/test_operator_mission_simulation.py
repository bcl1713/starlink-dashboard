"""Normal replay/mission APIs share a durable journal without training overrides."""

from uuid import uuid4

from app.operator.clock import SystemClock
from app.operator.runtime import OperatorRuntimeBinding

from tests.integration.test_simulation_run_api import PACING, api, start

__all__ = ["api"]


def test_normal_replay_and_leg_activation_keep_mission_journal(
    api, tmp_path, monkeypatch
):
    from app.api.operator import router
    from app.mission.storage import load_mission_v2, save_mission_v2

    client, replay, _clocks = api
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(tmp_path / "operator"))
    client.app.include_router(router)
    client.app.state.route_manager = replay.route_manager
    context = lambda: (
        "simulation",
        replay.status().run.run_id if replay.status().run else None,
    )
    binding = OperatorRuntimeBinding(
        clock=SystemClock(), context=context, mission_journals=True
    )
    client.app.state.operator_binding = binding
    try:
        assert start(client).status_code == 200
        first_run = replay.status().run.run_id
        active = client.get("/api/v2/operator/context").json()
        assert (active["mission_id"], active["leg_id"]) == ("mission-1", "leg-1")
        provisioned = client.post(
            "/api/v2/operator/provision",
            json={
                "expected_source_mode": "simulation",
                "expected_simulation_run_id": "default",
            },
        )
        assert provisioned.status_code == 200, provisioned.text
        health = provisioned.json()
        headers = {
            "Idempotency-Key": str(uuid4()),
            "X-Operator-Store-Epoch": health["api_epoch"],
            "X-Operator-Replay-Id": first_run,
        }
        note = {
            "record_type": "journal_entry",
            "mission_id": "mission-1",
            "scope": "leg",
            "leg_id": "leg-1",
            "time": {},
            "payload": {
                "entry_type": "note",
                "title": "Leg-one operational note",
                "note": "Retain through replay and next leg",
            },
        }
        created = client.post("/api/v2/operator/records", headers=headers, json=note)
        assert created.status_code == 201, created.text
        saved = created.json()["saved_records"][0]
        assert start(client).status_code == 200
        assert replay.status().run.run_id != first_run
        records = client.get(
            "/api/v2/operator/records", params={"mission_id": "mission-1"}
        ).json()["items"]
        assert records[0]["record"]["record_id"] == saved["record_id"]
        assert records[0]["operational_current"] is False
        mission = load_mission_v2("mission-1")
        mission.legs.append(
            mission.legs[0].model_copy(
                deep=True,
                update={"id": "leg-2", "name": "Second leg", "is_active": False},
            )
        )
        save_mission_v2(mission)
        leg2 = "/api/v2/missions/mission-1/legs/leg-2"
        preview = client.post(leg2 + "/simulation/preview", json=PACING)
        assert preview.status_code == 200, preview.text
        activated = client.post(
            leg2 + "/activate",
            json={
                "simulation": {
                    "pacing": PACING,
                    "plan_token": preview.json()["plan_token"],
                }
            },
        )
        assert activated.status_code == 200, activated.text
        assert client.get("/api/v2/operator/context").json()["leg_id"] == "leg-2"
        assert (
            client.get("/api/v2/operator/health").json()["store_id"]
            == health["store_id"]
        )
        retained = client.get("/api/v2/operator/records/" + saved["record_id"]).json()[
            "record"
        ]
        assert retained["leg_id"] == "leg-1"
        binding.close()
        binding = OperatorRuntimeBinding(
            clock=SystemClock(),
            context=lambda: ("simulation", None),
            mission_journals=True,
        )
        client.app.state.operator_binding = binding
        assert (
            client.get("/api/v2/operator/health").json()["store_id"]
            == health["store_id"]
        )
        assert (
            client.get("/api/v2/operator/records/" + saved["record_id"]).status_code
            == 200
        )
    finally:
        binding.close()
