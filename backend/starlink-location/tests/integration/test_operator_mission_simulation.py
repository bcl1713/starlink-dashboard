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


def test_ordinary_activate_conference_reestablishment_and_phase(
    api, tmp_path, monkeypatch
):
    from datetime import datetime, timedelta, timezone

    import main
    from app.api.operator import router
    from app.mission.storage import load_mission_v2, save_mission_v2

    client, replay, _clocks = api
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(tmp_path / "operator"))
    monkeypatch.setattr(main, "_coordinator", replay.coordinator)
    monkeypatch.setattr(main, "_route_manager", replay.route_manager)
    monkeypatch.setattr(main.app.state, "simulation_run_service", replay, raising=False)
    client.app.include_router(router)
    client.app.state.route_manager = replay.route_manager
    binding = OperatorRuntimeBinding(
        clock=SystemClock(),
        context=main._operator_context,
        mission_journals=True,
        operating_context=main._operator_operating_context,
    )
    client.app.state.operator_binding = binding
    base = "/api/v2/operator"

    def headers():
        health = client.get(base + "/health").json()
        return {
            "Idempotency-Key": str(uuid4()),
            "X-Operator-Store-Epoch": health["api_epoch"],
            "X-Operator-Replay-Id": health.get("operating_context_id")
            or health["replay_run_id"],
        }

    def change(record, payload, leg="leg-1", establish=False):
        now = client.get(base + "/records", params={"mission_id": "mission-1"}).json()[
            "as_of"
        ]
        body = {
            k: record[k]
            for k in (
                "schema_version",
                "record_type",
                "mission_id",
                "scope",
                "leg_id",
                "time",
                "payload",
            )
        }
        body.update(
            expected_version=record["version"],
            scope="leg",
            leg_id=leg,
            time={"occurred_at": now, "precision": "exact", "end_state": "instant"},
            payload={**record["payload"], **payload},
        )
        if establish:
            body["establish_session"] = True
        response = client.put(
            base + "/records/" + record["record_id"], json=body, headers=headers()
        )
        assert response.status_code == 200, response.text
        return response.json()["saved_records"][0]

    try:
        assert (
            client.post("/api/v2/missions/mission-1/legs/leg-1/activate").status_code
            == 200
        )
        assert replay.status().run is None
        context = client.get(base + "/context").json()
        from app.services.flight_state import get_flight_state_manager

        assert context["phase"] == get_flight_state_manager().get_status().phase.value
        assert (
            client.post(
                base + "/provision",
                json={
                    "expected_source_mode": "simulation",
                    "expected_simulation_run_id": "default",
                },
            ).status_code
            == 200
        )
        created = client.post(
            base + "/records",
            headers=headers(),
            json={
                "record_type": "conference",
                "mission_id": "mission-1",
                "scope": "leg",
                "leg_id": "leg-1",
                "time": {},
                "payload": {
                    "entry_type": "conference",
                    "title": "CABLES",
                    "status": "preparing",
                    "configured_transport": "Ka",
                },
            },
        )
        assert created.status_code == 201, created.text
        bridge = created.json()["saved_records"][0]
        assert bridge["provenance"]["replay_run_id"] is None
        assert (
            client.get(base + "/records/" + bridge["record_id"]).json()[
                "operational_current"
            ]
            is True
        )
        call = client.post(
            base + "/records",
            headers=headers(),
            json={
                "record_type": "call",
                "mission_id": "mission-1",
                "scope": "leg",
                "leg_id": "leg-1",
                "time": {
                    "planned_start_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=10)
                    ).isoformat()
                },
                "payload": {
                    "entry_type": "call",
                    "title": "First customer",
                    "conference_id": bridge["record_id"],
                },
            },
        )
        assert call.status_code == 201, call.text
        bridge = change(
            bridge, {"status": "established", "verified_at": None}, establish=True
        )
        now = client.get(base + "/records", params={"mission_id": "mission-1"}).json()[
            "as_of"
        ]
        bridge = change(bridge, {"verified_at": now})
        original = bridge
        assert (
            client.post("/api/v2/missions/mission-1/legs/deactivate").status_code == 200
        )
        mission = load_mission_v2("mission-1")
        mission.legs.append(
            mission.legs[0].model_copy(
                deep=True,
                update={"id": "leg-2", "name": "Second leg", "is_active": False},
            )
        )
        save_mission_v2(mission)
        assert (
            client.post("/api/v2/missions/mission-1/legs/leg-2/activate").status_code
            == 200
        )
        retained = client.get(base + "/records/" + bridge["record_id"]).json()
        assert retained["record"] == original
        assert retained["operational_current"] is False
        bridge = change(
            bridge,
            {"status": "established", "verified_at": None},
            leg="leg-2",
            establish=True,
        )
        assert bridge["record_id"] == original["record_id"]
        assert (
            client.get(base + "/records/" + bridge["record_id"]).json()[
                "operational_current"
            ]
            is True
        )
        assert (
            client.get(base + "/records/" + bridge["record_id"] + "/history").json()[
                "items"
            ][2]["record"]
            == original
        )
        leg2 = "/api/v2/missions/mission-1/legs/leg-2"
        preview = client.post(leg2 + "/simulation/preview", json=PACING)
        assert (
            client.post(
                leg2 + "/activate",
                json={
                    "simulation": {
                        "pacing": PACING,
                        "plan_token": preview.json()["plan_token"],
                    }
                },
            ).status_code
            == 200
        )
        assert (
            client.get(base + "/records/" + bridge["record_id"]).json()[
                "operational_current"
            ]
            is False
        )
        assert client.post(leg2 + "/activate").status_code == 200
        assert (
            client.get(base + "/records/" + bridge["record_id"]).json()[
                "operational_current"
            ]
            is False
        )
        assert (
            client.get(base + "/records/" + bridge["record_id"]).json()["record"]
            == bridge
        )
    finally:
        binding.close()
